import json
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.utils.timezone import now
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.db.models import Q
from .models import Property, ChatMessage, Conversation, User
from .serializers import PropertySerializer, ChatMessageSerializer, ConversationSerializer, UserSerializer
import logging

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')

class ChatMessageViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer

    @method_decorator(csrf_exempt)
    @action(detail=False, methods=['post'])
    def chat(self, request):
        """
        Handles chat with OpenAI and stores conversation history.
        """
        user = request.user if request.user.is_authenticated else None
        if not user:
            chat_logger.warning(f"Chat request missing user data")
            return Response({"error": "User is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        user_message = request.data.get("message", "")
        conversation_id = request.data.get("conversation_id", None)

        if not user_message:
            chat_logger.warning(f"Chat request missing message data from user: {user}")
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

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

            # Get AI response
            bot_reply = ChatMessage.objects.get_ai_response(conversation)

            # Store bot response
            ChatMessage.objects.store_message(conversation, None, bot_reply, "bot")
            chat_logger.info(f"AI Response: '{bot_reply}' in Conversation {conversation.id}")

            return Response({
                "message": bot_reply,
                "conversation_id": conversation.id
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.error(f"Chat request failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

        try:
            if conversation_id:
                logger.info(f"Fetching prompts for conversation {conversation_id}")
                conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
                prompts = ChatMessage.objects.get_sample_prompts(conversation)
            else:
                logger.info("Fetching default prompts")
                prompts = ChatMessage.objects.get_sample_prompts()
                
            return Response({"prompts": prompts}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching sample prompts: {str(e)}")
            return Response(
                {"error": f"Failed to fetch sample prompts: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            logger.info(f"[{now()}] User {user.username} logged in successfully")
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            logger.warning(f"[{now()}] Failed login attempt: {email}")
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new user and return token.
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Return current user's data.
        """
        if request.user.is_authenticated:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        return Response(status=status.HTTP_401_UNAUTHORIZED)
