import hashlib, logging, uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils import timezone
from pgvector.django import VectorField
from .managers import ChatMessageManager, ConversationManager, PropertyManager
from googlemaps import Client

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')


class Address(models.Model):
    street_address = models.CharField(max_length=255, blank=True, null=True, help_text="Street number and name")
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
        # Only geocode if address fields changed
        if self.pk:
            try:
                old = Address.objects.get(pk=self.pk)
                address_changed = (
                    old.street_address != self.street_address or
                    old.city != self.city or
                    old.state != self.state or
                    old.zip_code != self.zip_code
                )
            except Address.DoesNotExist:
                address_changed = True
        else:
            address_changed = True

        if address_changed:
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
    profile_image = models.URLField(max_length=500, blank=True, null=True)

    groups = models.ManyToManyField(Group, related_name="api_users", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="api_user_permissions", blank=True)
    profile_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.user_type})"


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} - {self.name}"


class PropertyType(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ListingStatus(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Listing Statuses"

    def __str__(self):
        return self.name


class Amenity(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # For UI icons
    category = models.CharField(max_length=50, blank=True)  # e.g., 'security', 'comfort', 'luxury'
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Amenities"

    def __str__(self):
        return self.name


class PropertyImage(models.Model):
    IMAGE_TYPE_CHOICES = [
        ('primary', 'Primary Image'),
        ('exterior', 'Exterior'),
        ('interior', 'Interior'),
        ('floor_plan', 'Floor Plan'),
        ('other', 'Other')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey('Property', on_delete=models.CASCADE, related_name='property_images')
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES, default='other')
    image_url = models.URLField(max_length=500)
    storage_path = models.CharField(max_length=500)  # Path in Supabase storage
    title = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'uploaded_at']
        indexes = [
            models.Index(fields=['property', 'image_type']),
            models.Index(fields=['property', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.property.property_id} - {self.image_type} Image"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary image per property
            PropertyImage.objects.filter(property=self.property, is_primary=True).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)


class Property(models.Model):
    PRICE_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('one_time', 'One Time'),
    ]

    # Basic Information
    property_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(null=True, blank=True, max_length=255)
    description = models.TextField(null=True, blank=True)
    address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True)

    # Pricing Information
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    price_type = models.CharField(max_length=10, choices=PRICE_TYPE_CHOICES, default='one_time')
    price_per_sqft = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Property Details
    property_type = models.ForeignKey(PropertyType, on_delete=models.PROTECT)
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
    parking_spaces = models.IntegerField(null=True, blank=True)
    total_floors = models.IntegerField(null=True, blank=True)
    floor_number = models.IntegerField(null=True, blank=True)

    # Property Features
    furnished = models.BooleanField(default=False)
    furnishing_details = models.JSONField(null=True, blank=True) 
    amenities = models.JSONField(default=list)

    # Building Features
    year_built = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1900), MaxValueValidator(2026)])
    construction_status = models.CharField(max_length=50, null=True, blank=True)

    # Area Information
    size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Size in square feet")
    carpet_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    plot_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Media
    maps_url = models.URLField(max_length=500, blank=True)
    virtual_tour_url = models.URLField(max_length=500, blank=True, null=True)

    # Additional Details
    building_name = models.CharField(max_length=255, null=True, blank=True)
    landmark = models.CharField(max_length=255, null=True, blank=True)
    possession_date = models.DateField(null=True, blank=True)

    # SEO and Search
    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    tags = models.JSONField(default=list)

    # Listing Status
    availability = models.BooleanField(default=True)
    listing_status = models.ForeignKey(ListingStatus, on_delete=models.PROTECT)
    listed_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Vector Embedding for AI-powered search
    embedding = VectorField(dimensions=1536, null=True, db_index=False)
    embedding_updated_at = models.DateTimeField(null=True, blank=True)
    embedding_content_hash = models.CharField(max_length=64, blank=True, null=True)
    embedding_text = models.TextField(null=True, blank=True)

    objects = PropertyManager()
    
    def save(self, *args, **kwargs):
        if self.size and self.price:
            self.price_per_sqft = self.price / self.size

        # Smart embedding: only regenerate if content changed
        skip_embedding = kwargs.pop('skip_embedding', False)
        if not skip_embedding:
            try:
                text = Property.objects.generate_property_text(self)
                content_hash = hashlib.sha256(text.encode()).hexdigest()
                if content_hash != self.embedding_content_hash:
                    self.embedding = Property.objects.generate_embedding(text)
                    self.embedding_updated_at = timezone.now()
                    self.embedding_content_hash = content_hash
                    self.embedding_text = text
            except Exception as e:
                logger.error(f"Error generating embedding during save: {str(e)}")
                raise

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} ({self.property_type}) - {self.price} {self.currency}"
    
    @property
    def primary_image(self):
        return self.property_images.filter(is_primary=True).first()

    @property
    def all_images(self):
        return self.property_images.all()

    def get_images_by_type(self, image_type):
        return self.property_images.filter(image_type=image_type)
    
    class Meta:
        verbose_name_plural = "Properties"
        indexes = [
            models.Index(fields=['property_id']),
        ]


class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('closed', 'Closed')], default='active')
    summary = models.TextField(null=True, blank=True)
    summary_message_count = models.IntegerField(default=0)

    objects = ConversationManager()  # Assign custom manager

    def __str__(self):
        return f"Conversation {self.id} - {self.user.username if self.user else 'Guest'}"


class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('user', 'User'),
        ('bot', 'Bot'),
    ]

    FEEDBACK_CHOICES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
        ('none', 'None')
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    text = models.TextField()
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    properties = models.ManyToManyField(Property, blank=True)
    feedback = models.CharField(max_length=10, choices=FEEDBACK_CHOICES, default='none')
    feedback_timestamp = models.DateTimeField(null=True, blank=True)

    objects = ChatMessageManager()

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}..."
    
    class Meta:
        ordering = ['-timestamp']
