from rest_framework import serializers
from dj_rest_auth.serializers import UserDetailsSerializer
from .models import User, Property, ChatMessage, Conversation, Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'
        read_only_fields = ['formatted_address', 'is_verified', 'latitude', 'longitude']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'user_type', 'phone_number', 'device_info', 'address', 'profile_completed']


class CustomUserSerializer(UserDetailsSerializer):
    """Extend default user serializer to include additional fields"""
    address = AddressSerializer()

    class Meta(UserDetailsSerializer.Meta):
        model = User
        fields = UserDetailsSerializer.Meta.fields + ('phone_number', 'device_info', 'address', 'profile_completed')
    
    def create(self, validated_data):
        if 'address' in validated_data:
            address_data = validated_data.pop('address')
            address = Address.objects.create(**address_data)
            user = User.objects.create(address=address, **validated_data)
        else:
            user = User.objects.create(**validated_data)
        return user

    def update(self, instance, validated_data):
        if 'address' in validated_data:
            address_data = validated_data.pop('address')
            if instance.address:
                address_serializer = AddressSerializer(instance.address, data=address_data, partial=True)
                address_serializer.is_valid(raise_exception=True)
                address_serializer.save()
            else:
                address = Address.objects.create(**address_data)
                instance.address = address
        return super().update(instance, validated_data)


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        exclude = ['embedding', 'embedding_updated_at']
    
    def create(self, validated_data):
        address_data = validated_data.pop('address')
        address = Address.objects.create(**address_data)
        property_instance = Property.objects.create(address=address, **validated_data)
        return property_instance

    def update(self, instance, validated_data):
        if 'address' in validated_data:
            address_data = validated_data.pop('address')
            address_serializer = AddressSerializer(instance.address, data=address_data, partial=True)
            address_serializer.is_valid(raise_exception=True)
            address_serializer.save()
        return super().update(instance, validated_data)


class ChatMessageSerializer(serializers.ModelSerializer):
    properties = PropertySerializer(many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'conversation', 'user', 'text', 'sender', 'timestamp', 'properties']


class ConversationSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'user', 'started_at', 'last_updated', 'status', 'messages']
