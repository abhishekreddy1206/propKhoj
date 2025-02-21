from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Property, Conversation, 
    ChatMessage, Address, Amenity, Currency,
    ListingStatus, PropertyType
)
from .chat_analytics import ChatAnalytics


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('street_address', 'unit', 'city', 'state', 'zip_code', 'latitude', 'longitude', 'is_verified')
    search_fields = ('street_address', 'city', 'state', 'zip_code')
    list_filter = ('state', 'is_verified')
    ordering = ('city', 'state')

    def has_add_permission(self, request):
        return request.user.groups.filter(name__in=['Agent', 'Admin']).exists()

    def has_view_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Agent', 'Admin']).exists()

    def has_delete_permission(self, request, obj=None):
        return request.user.groups.filter(name='Admin').exists()


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'phone_number', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone_number')
    list_filter = ('user_type', 'is_active', 'is_staff')
    ordering = ('username',)
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'phone_number', 'device_info', 'address')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'phone_number', 'device_info', 'address')}),
    )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'property_type', 'price', 'currency', 'availability', 
        'address', 
        'bedrooms', 'bathrooms', 'size', 'building_name', 'landmark'
    )
    search_fields = ('title', 'property_id', 'address__street_address', 'address__city')
    list_filter = ('property_type', 'currency', 'availability', 'address__state')
    ordering = ('title',)
    readonly_fields = ('embedding',)

    def has_add_permission(self, request):
        # Allow adding if the user is in the 'Agent' or 'Admin' group
        return request.user.groups.filter(name__in=['Agent', 'Admin']).exists()

    def has_delete_permission(self, request, obj=None):
        # Allow deleting only if the user is in the 'Admin' group
        return request.user.groups.filter(name='Admin').exists()


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'started_at', 'last_updated', 'status', 'message_count')
    list_filter = ('status', 'started_at', 'last_updated')
    search_fields = ('user__username', 'id')
    
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'sender', 'timestamp')
    search_fields = ('conversation__id', 'user__username', 'text')
    list_filter = ('sender', 'timestamp')


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol')
    search_fields = ('code', 'name')


@admin.register(ListingStatus)
class ListingStatusAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Optional: Registering models manually if @admin.register is not used
# admin.site.register(User, CustomUserAdmin)
# admin.site.register(Property, PropertyAdmin)
# admin.site.register(Conversation, ConversationAdmin)
# admin.site.register(ChatMessage, ChatMessageAdmin)
