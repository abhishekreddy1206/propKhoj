from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from .models import User, Property, Conversation, ChatMessage, Address, Currency, PropertyType, ListingStatus


class TestHelperMixin:
    """Shared helpers for creating test data."""

    def create_user(self, email='test@example.com', password='testpass123', user_type='buyer', username='testuser'):
        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            user_type=user_type,
            phone_number=f'+1{hash(email) % 10**9:09d}',
        )

    def create_auth_client(self, user=None):
        if user is None:
            user = self.create_user()
        token, _ = Token.objects.get_or_create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client, user

    @patch.object(Address, 'geocode_address', return_value=None)
    def create_property(self, mock_geocode):
        currency = Currency.objects.get_or_create(code='INR', defaults={'name': 'Indian Rupee', 'symbol': '\u20b9'})[0]
        prop_type = PropertyType.objects.get_or_create(slug='apartment', defaults={'name': 'Apartment'})[0]
        listing_status = ListingStatus.objects.get_or_create(slug='active', defaults={'name': 'Active'})[0]
        address = Address.objects.create(city='Bangalore', state='KA', zip_code='560001')

        return Property.objects.create(
            title='Test Property',
            description='A test property',
            address=address,
            price=5000000,
            currency=currency,
            property_type=prop_type,
            listing_status=listing_status,
            bedrooms=3,
            bathrooms=2,
            size=1500,
            embedding=[0.0] * 1536,
            embedding_updated_at=timezone.now(),
            skip_embedding=True,
        )


class ChatEndpointTests(TestHelperMixin, TestCase):
    """Test chat endpoint requires auth and validates input."""

    def test_chat_requires_authentication(self):
        client = APIClient()
        response = client.post('/api/chats/chat/', {'message': 'hello'})
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_chat_rejects_empty_message(self):
        client, user = self.create_auth_client()
        response = client.post('/api/chats/chat/', {'message': ''}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_chat_rejects_long_message(self):
        client, user = self.create_auth_client()
        response = client.post('/api/chats/chat/', {'message': 'x' * 5001}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.managers.get_openai_client')
    def test_chat_returns_response(self, mock_openai):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Test AI response'
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        mock_openai.return_value.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.0] * 1536)]
        )

        client, user = self.create_auth_client()
        response = client.post('/api/chats/chat/', {'message': 'Find me a house'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('conversation_id', response.data)


class ConversationAccessTests(TestHelperMixin, TestCase):
    """Test that users can only access their own conversations."""

    def test_user_cannot_see_other_conversations(self):
        user_a = self.create_user(email='a@test.com', username='usera')
        user_b = self.create_user(email='b@test.com', username='userb')

        Conversation.objects.create(user=user_a)
        Conversation.objects.create(user=user_b)

        client_a, _ = self.create_auth_client(user_a)
        response = client_a.get('/api/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for conv in response.data:
            self.assertEqual(conv['user'], user_a.id)

    def test_unauthenticated_cannot_list_conversations(self):
        client = APIClient()
        response = client.get('/api/conversations/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class PropertySearchTests(TestHelperMixin, TestCase):
    """Test property search uses correct fields."""

    def test_search_by_city(self):
        prop = self.create_property()
        client, user = self.create_auth_client()
        response = client.get('/api/properties/search/', {'q': 'Bangalore'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)

    def test_search_by_title(self):
        prop = self.create_property()
        client, user = self.create_auth_client()
        response = client.get('/api/properties/search/', {'q': 'Test Property'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)

    def test_search_no_query_returns_error(self):
        client, user = self.create_auth_client()
        response = client.get('/api/properties/search/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PropertySerializerTests(TestHelperMixin, TestCase):
    """Test that embedding is excluded from API responses."""

    def test_embedding_not_in_response(self):
        prop = self.create_property()
        client, user = self.create_auth_client()
        response = client.get(f'/api/properties/{prop.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('embedding', response.data)
        self.assertNotIn('embedding_updated_at', response.data)


class PropertyManagerTests(TestHelperMixin, TestCase):
    """Test property text generation and embedding."""

    def test_generate_property_text(self):
        prop = self.create_property()
        text = Property.objects.generate_property_text(prop)
        self.assertIn('Test Property', text)
        self.assertIn('Bangalore', text)
        self.assertIn('3 bedrooms', text)

    @patch('api.managers.get_openai_client')
    def test_generate_embedding_returns_vector(self, mock_openai):
        mock_openai.return_value.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        embedding = Property.objects.generate_embedding('test text')
        self.assertEqual(len(embedding), 1536)


class ProfileTests(TestHelperMixin, TestCase):
    """Test profile update flow."""

    @patch.object(Address, 'geocode_address', return_value=None)
    def test_update_profile(self, mock_geocode):
        client, user = self.create_auth_client()
        response = client.post('/api/profile/update_profile/', {
            'first_name': 'John',
            'last_name': 'Doe',
            'address': {
                'city': 'Sacramento',
                'state': 'CA',
                'zip_code': '95814',
            }
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'John')
        self.assertTrue(user.profile_completed)

    def test_profile_requires_auth(self):
        client = APIClient()
        response = client.get('/api/profile/me/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class PropertyViewSetPermissionTests(TestHelperMixin, TestCase):
    """Test property CRUD permissions."""

    def test_unauthenticated_can_read_properties(self):
        prop = self.create_property()
        client = APIClient()
        response = client.get('/api/properties/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_create_property(self):
        client = APIClient()
        response = client.post('/api/properties/', {'title': 'New'}, format='json')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
