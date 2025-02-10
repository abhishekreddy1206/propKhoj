from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser, Group, Permission
from pgvector.django import VectorField
import logging
from .managers import ChatMessageManager, ConversationManager
from googlemaps import Client

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')


class Address(models.Model):
    street_address = models.CharField(max_length=255, help_text="Street number and name")
    unit = models.CharField(max_length=50, blank=True, null=True, help_text="Apartment, suite, unit, etc.")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, help_text="Two-letter state code")
    zip_code = models.CharField(max_length=10, help_text="ZIP or ZIP+4 code")
    county = models.CharField(max_length=100, blank=True, null=True)
    
    # Geo coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    formatted_address = models.CharField(max_length=512, blank=True, null=True, help_text="Google-formatted complete address")
    place_id = models.CharField(max_length=255, blank=True, null=True, help_text="Google Places ID for this address")
    is_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Addresses"
        indexes = [
            models.Index(fields=['zip_code']),
            models.Index(fields=['city', 'state']),
        ]

    def clean(self):
        if not hasattr(settings, 'GOOGLE_MAPS_API_KEY'):
            raise ValidationError("Google Maps API key is not configured")
        
        self.geocode_address()

    def geocode_address(self):
        """
        Use Google's Geocoding API to verify and enhance the address data
        """
        try:
            gmaps = Client(key=settings.GOOGLE_MAPS_API_KEY)
            address_str = self.__str__()
            
            # Geocode the address
            result = gmaps.geocode(address_str)
            
            if result and len(result) > 0:
                location = result[0]['geometry']['location']
                self.latitude = location['lat']
                self.longitude = location['lng']
                self.formatted_address = result[0]['formatted_address']
                self.place_id = result[0]['place_id']
                self.is_verified = True
            else:
                self.is_verified = False
                
        except Exception as e:
            logger.error(f"Geocoding error for address {address_str}: {str(e)}")
            self.is_verified = False
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        base = f"{self.street_address}"
        if self.unit:
            base += f" {self.unit}"
        return f"{base}, {self.city}, {self.state} {self.zip_code}"


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
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)

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
    address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True)
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
