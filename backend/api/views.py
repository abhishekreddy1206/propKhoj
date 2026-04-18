import json
from django.contrib.auth import authenticate
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.throttling import ScopedRateThrottle
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Q
from .models import Property, ChatMessage, Conversation, User
from .serializers import PropertySerializer, ChatMessageSerializer, ConversationSerializer, CustomUserSerializer, UserSerializer
import logging

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')


def user_is_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or user.user_type == 'admin'
            or user.groups.filter(name='Admin').exists()
        )
    )


def user_can_manage_properties(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user_is_admin(user)
            or user.user_type == 'agent'
            or user.groups.filter(name='Agent').exists()
        )
    )


class IsAdminUserViewPermission(BasePermission):
    def has_permission(self, request, view):
        return user_is_admin(request.user)


class IsAdminOrAgentWritePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return user_can_manage_properties(request.user)

class ChatMessageViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer

    throttle_scope = 'chat'

    @action(detail=False, methods=['post'])
    def chat(self, request):
        """
        Handles chat with OpenAI and stores conversation history.
        """
        user = request.user if request.user.is_authenticated else None
        if not user:
            chat_logger.warning("Chat request missing user data")
            return Response({"error": "User is required"}, status=status.HTTP_400_BAD_REQUEST)

        user_message = request.data.get("message", "")
        conversation_id = request.data.get("conversation_id", None)

        if not user_message:
            chat_logger.warning(f"Chat request missing message data from user: {user}")
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        if len(user_message) > 5000:
            return Response({"error": "Message too long (max 5000 characters)"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Retrieve or create a conversation
            if conversation_id:
                # ✅ Retrieve existing conversation instead of creating a new one
                conversation = get_object_or_404(Conversation, id=conversation_id, user=user)
            else:
                # ✅ Create a new conversation only if no ID is provided
                conversation = Conversation.objects.get_or_create_conversation(user, conversation_id)
            ChatMessage.objects.store_message(conversation, user, user_message, "user")
            chat_logger.info(f"User {user} sent: '{user_message}' in Conversation {conversation.id}")

            # Determine if this is a new search or a conversational follow-up
            if Property.objects.is_search_query(user_message):
                # 🔍 New search: extract filters + RAG similarity search
                chat_logger.info(f"Search query detected: '{user_message}'")
                filters = Property.objects.extract_search_filters(user_message)
                property_results = Property.objects.search_by_similarity(user_message, limit=5, filters=filters)
                property_data = PropertySerializer(property_results, many=True).data
                property_texts = [p.embedding_text or Property.objects.generate_property_text(p) for p in property_results]
            else:
                # 💬 Follow-up: reuse properties from last bot message (skip 2 API calls)
                chat_logger.info(f"Follow-up detected, reusing previous properties: '{user_message}'")
                last_bot_msg = ChatMessage.objects.filter(
                    conversation=conversation, sender='bot'
                ).order_by('-timestamp').first()
                if last_bot_msg and last_bot_msg.properties.exists():
                    property_results = list(last_bot_msg.properties.all())
                    property_data = PropertySerializer(property_results, many=True).data
                    property_texts = [p.embedding_text or Property.objects.generate_property_text(p) for p in property_results]
                else:
                    property_results = []
                    property_data = []
                    property_texts = []

            # Get AI response with property context
            bot_reply = ChatMessage.objects.get_ai_response(conversation, property_context=property_texts if property_texts else None)

            # Store bot response
            bot_message = ChatMessage.objects.store_message(conversation, None, bot_reply, "bot")
            bot_message.properties.set(property_results)
            chat_logger.info(f"AI Response: '{bot_reply}' in Conversation {conversation.id}")

            return Response({
                "message": bot_reply,
                "conversation_id": conversation.id,
                "message_id": bot_message.id,
                "properties": property_data 
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.error(f"Chat request failed: {str(e)}")
            return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            chat_logger.error(f"Chat processing error: {str(e)}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def sample_prompts(self, request):
        """
        Returns AI-generated sample prompts for the chat interface.
        Generates follow-up prompts if conversation_id is provided.
        """
        conversation_id = request.query_params.get('conversation_id')
        user = request.user if request.user.is_authenticated else None

        try:
            if conversation_id:
                logger.info(f"Fetching prompts for conversation {conversation_id}")
                conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
                prompts = ChatMessage.objects.get_sample_prompts(conversation=conversation, user=user)
            else:
                logger.info("Fetching default prompts")
                prompts = ChatMessage.objects.get_sample_prompts(user=user)
                
            return Response({"prompts": prompts}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching sample prompts: {str(e)}")
            return Response(
                {"error": "Failed to fetch sample prompts"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def message_feedback(self, request, chat_id):
        try:
            message = ChatMessage.objects.get(
                id=chat_id,
                sender='bot',
                conversation__user=request.user,
            )
            message.feedback = request.data.get('feedback')
            message.feedback_timestamp = timezone.now()
            message.save()
            return Response({'status': 'success'})
        except ChatMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=404)


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Create a new conversation for the user.
        """
        conversation = Conversation.objects.create(user=request.user)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    permission_classes = [IsAdminOrAgentWritePermission]

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', None)
        if query:
            properties = Property.objects.filter(
                Q(title__icontains=query) | Q(address__city__icontains=query) | Q(address__state__icontains=query) | Q(address__zip_code__icontains=query)
            )
            serializer = self.get_serializer(properties, many=True)
            return Response(serializer.data)
        return Response({"error": "No query provided"}, status=400)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'login':
            return [AllowAny()]
        if self.action == 'me':
            return [IsAuthenticated()]
        return [IsAdminUserViewPermission()]

    @method_decorator(ensure_csrf_cookie)
    @action(detail=False, methods=['post'])
    def login(self, request):
        """
        Authenticate user and return token.
        """
        email = request.data.get('email')
        password = request.data.get('password')

        user = authenticate(username=email, password=password)
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            logger.info(f"[{timezone.now()}] User {user.username} logged in successfully")
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            logger.warning(f"[{timezone.now()}] Failed login attempt: {email}")
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Return current user's data.
        """
        if request.user.is_authenticated:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        return Response(status=status.HTTP_401_UNAUTHORIZED)


class UserProfileView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retrieve logged-in user's profile"""
        user = request.user
        return Response(CustomUserSerializer(user).data)

    @action(detail=False, methods=['post'])
    def update_profile(self, request):
        """Update user's profile"""
        user = request.user
        data = request.data.copy()
    
        # If username is provided and it's the same as current username, remove it to avoid validation
        if 'username' in data and data['username'] == user.username:
            del data['username']
        
        serializer = CustomUserSerializer(user, data=data, partial=True)

        if serializer.is_valid():
            serializer.save(profile_completed=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
