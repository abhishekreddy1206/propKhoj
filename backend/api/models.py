from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from pgvector.django import VectorField
import logging
from .managers import ChatMessageManager, ConversationManager

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')


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
    profile_completed = models.BooleanField(default=False)

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
