from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from pgvector.django import VectorField
from django.contrib.postgres.fields import ArrayField
from django.utils.timezone import now
from openai import OpenAI
import logging, json

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')

client = OpenAI()


class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
        ('admin', 'Admin'),
        ('agent', 'Agent'),
    ]

    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='buyer')
    phone_number = models.CharField(max_length=15, unique=True)
    device_info = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    groups = models.ManyToManyField(Group, related_name="api_users", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="api_user_permissions", blank=True)

    def __str__(self):
        return f"{self.username} ({self.user_type})"

class Property(models.Model):
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
    ]

    PRICE_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('one_time', 'One Time'),
    ]

    PROPERTY_TYPE_CHOICES = [
        ('house_rent', 'House for Rent'),
        ('house_sale', 'House for Sale'),
        ('apartment_rent', 'Apartment for Rent'),
        ('apartment_sale', 'Apartment for Sale'),
    ]

    property_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    price = models.FloatField()
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    price_type = models.CharField(max_length=10, choices=PRICE_TYPE_CHOICES, default='one_time')
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
    parking_spaces = models.IntegerField(null=True, blank=True)
    furnished = models.BooleanField(default=False)
    availability = models.BooleanField(default=True)
    amenities = models.TextField()  # Can be a comma-separated list or JSON in the future
    size = models.FloatField(null=True, blank=True)
    property_type = models.CharField(max_length=50, choices=PROPERTY_TYPE_CHOICES, default='house_sale')
    maps_url = models.URLField(max_length=500, blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)

    # Vector Embedding for AI-powered search
    embedding = VectorField(dimensions=1536, db_index=True)

    def __str__(self):
        return f"{self.title} ({self.property_type}) - {self.price} {self.currency}"

    class Meta:
        verbose_name_plural = "Properties"


class ConversationManager(models.Manager):
    def get_or_create_conversation(self, user, conversation_id=None):
        """
        Retrieve an existing conversation or create a new one.
        """
        if conversation_id:
            try:
                return self.get(id=conversation_id)
            except Conversation.DoesNotExist:
                raise ValueError("Invalid conversation ID")
        return self.create(user=user)


class ChatMessageManager(models.Manager):
    def store_message(self, conversation, user, text, sender):
        """
        Store a new chat message.
        """
        return self.create(conversation=conversation, user=user, text=text, sender=sender)

    def get_chat_history(self, conversation):
        """
        Retrieve chat history in OpenAI format.
        """
        chat_history = self.filter(conversation=conversation).order_by("timestamp")
        formatted_messages = [{"role": "system", "content": "You are a helpful real estate AI assistant."}]

        for msg in chat_history:
            role = "user" if msg.sender == "user" else "assistant"
            formatted_messages.append({"role": role, "content": msg.text})

        return formatted_messages

    def get_ai_response(self, conversation):
        """
        Call OpenAI API and return a response.
        """
        messages = self.get_chat_history(conversation)

        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "I'm currently unable to fetch responses. Please try again later."
    
    def get_sample_prompts(self, conversation=None):
        """
        Get AI-generated sample prompts for the chat interface.
        If conversation is provided, generates follow-up prompts based on chat history.
        """
        if not conversation:
            # Initial prompts for new conversations
            messages = [
                {"role": "system", "content": "You are a helpful real estate AI assistant. Generate 4 sample questions that users might ask about real estate. Return them as a JSON array of strings."},
                {"role": "user", "content": "Generate 4 sample prompts"}
            ]
        else:
            # Get conversation history and generate relevant follow-ups
            chat_history = self.get_chat_history(conversation)
            
            system_prompt = """You are a helpful real estate AI assistant. Based on the conversation history provided, 
            generate 4 relevant follow-up questions that the user might want to ask. These should be natural continuations 
            of the conversation and relate to previously discussed topics. Return them as a JSON array of strings."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                *chat_history[1:],  # Skip the initial system message
                {"role": "user", "content": "Based on this conversation, what are 4 relevant follow-up questions I might want to ask?"}
            ]

        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                response_format={ "type": "json_object" }
            )
            prompts = json.loads(response.choices[0].message.content)
            return prompts.get("prompts", [])
        except Exception as e:
            logger.error(f"Error generating sample prompts: {str(e)}")
            # Fallback prompts
            if not conversation:
                return [
                    "Find me a 2BHK apartment in Bangalore",
                    "Show me commercial office spaces under ₹50L",
                    "What are the best areas to invest in Mumbai?",
                    "List luxury villas in Delhi"
                ]
            else:
                return [
                    "Can you tell me more about the property?",
                    "What are the nearby amenities?",
                    "How is the connectivity to the city center?",
                    "What are the payment terms?"
                ]


class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('closed', 'Closed')], default='active')

    objects = ConversationManager()  # Assign custom manager

    def __str__(self):
        return f"Conversation {self.id} - {self.user.username if self.user else 'Guest'}"


class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('user', 'User'),
        ('bot', 'Bot'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    text = models.TextField()
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    properties = models.ManyToManyField(Property, blank=True)

    objects = ChatMessageManager()

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}..."
    
    class Meta:
        ordering = ['-timestamp']
