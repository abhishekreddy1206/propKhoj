import json
from openai import OpenAI
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Count
from .models import Property, ChatMessage, Conversation, User
from .serializers import PropertySerializer, ChatMessageSerializer, ConversationSerializer, UserSerializer
import logging

# Initialize loggers
logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')
access_logger = logging.getLogger('django.request')

# Initialize OpenAI client using your method
client = OpenAI()

class ChatMessageViewSet(viewsets.ModelViewSet):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer

    @action(detail=False, methods=['post'])
    def chat(self, request):
        """
        Chat with OpenAI and store the conversation history.
        """
        user = request.user if request.user.is_authenticated else None
        user_message = request.data.get("message", "")
        conversation_id = request.data.get("conversation_id", None)

        if not user_message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve or create conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response({"error": "Invalid conversation ID"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            conversation = Conversation.objects.create(user=user)

        # Store user message
        ChatMessage.objects.create(conversation=conversation, user=user, text=user_message, sender="user")

        # Prepare chat history for OpenAI
        chat_history = ChatMessage.objects.filter(conversation=conversation).order_by('timestamp')
        openai_messages = [{"role": "system", "content": "You are a helpful real estate expert and assistant named Propkhoj that extracts real estate search parameters from queries and generates response messages."}]

        for msg in chat_history:
            role = "user" if msg.sender == "user" else "assistant"
            openai_messages.append({"role": role, "content": msg.text})

        # Get AI response from OpenAI API
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=openai_messages
            )
            bot_reply = response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return Response({"error": "AI service unavailable"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Store bot response
        ChatMessage.objects.create(conversation=conversation, text=bot_reply, sender="bot")

        return Response({"message": bot_reply, "conversation_id": conversation.id}, status=status.HTTP_200_OK)


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new conversation for the user.
        """
        user = request.user if request.user.is_authenticated else None
        conversation = Conversation.objects.create(user=user)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all()
    serializer_class = PropertySerializer

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', None)
        if query:
            properties = Property.objects.filter(
                Q(title__icontains=query) | Q(location__icontains=query)
            )
            serializer = self.get_serializer(properties, many=True)
            return Response(serializer.data)
        return Response({"error": "No query provided"}, status=400)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['post'])
    def login(self, request):
        """
        Authenticate user login.
        """
        email = request.data.get('email')
        password = request.data.get('password')

        user = authenticate(username=email, password=password)
        if user:
            return Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
