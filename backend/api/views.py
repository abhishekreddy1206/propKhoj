from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Count
from django.utils.timezone import now
from .models import Property, ChatMessage, Conversation, User
from .serializers import PropertySerializer, ChatMessageSerializer, ConversationSerializer, UserSerializer
import logging

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')
access_logger = logging.getLogger('django.request')


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


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new conversation for a user.
        """
        user = request.user if request.user.is_authenticated else None
        conversation = Conversation.objects.create(user=user)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class ChatMessageViewSet(viewsets.ModelViewSet):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer

    def create(self, request, *args, **kwargs):
        """
        Store user messages and responses from the bot, linking to a conversation.
        """
        user = request.user if request.user.is_authenticated else None
        conversation_id = request.data.get('conversation_id', None)
        text = request.data.get('text', '')
        sender = request.data.get('sender', 'user')

        if not text or not conversation_id:
            access_logger.warning(f"[{now()}] Failed chat request: Missing text or conversation_id")
            return Response({'error': 'Text and conversation ID are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            access_logger.warning(f"[{now()}] Invalid conversation ID: {conversation_id}")
            return Response({'error': 'Invalid conversation ID'}, status=status.HTTP_400_BAD_REQUEST)

        chat_message = ChatMessage.objects.create(
            conversation=conversation,
            user=user,
            text=text,
            sender=sender
        )

        conversation.last_updated = chat_message.timestamp
        conversation.save()

        chat_logger.info(f"[{now()}] {user} sent message: '{text}' in Conversation {conversation_id}")

        return Response(ChatMessageSerializer(chat_message).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """
        Generate chat analytics.
        """
        total_messages = ChatMessage.objects.count()
        user_messages = ChatMessage.objects.filter(sender='user').count()
        bot_messages = ChatMessage.objects.filter(sender='bot').count()
        most_active_users = ChatMessage.objects.values('user').annotate(count=Count('id')).order_by('-count')[:5]
        total_conversations = Conversation.objects.count()
        active_conversations = Conversation.objects.filter(status='active').count()

        analytics_data = {
            "total_messages": total_messages,
            "user_messages": user_messages,
            "bot_messages": bot_messages,
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "most_active_users": list(most_active_users),
        }

        return Response(analytics_data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new user account.
        """
        username = request.data.get('username')
        email = request.data.get('email')
        phone_number = request.data.get('phone_number')

        if User.objects.filter(email=email).exists():
            logger.warning(f"[{now()}] Failed registration: Email {email} already in use")
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create(
            username=username,
            email=email,
            phone_number=phone_number
        )
        user.set_password(request.data.get('password'))
        user.save()

        logger.info(f"[{now()}] New user registered: {username} ({email})")

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def login(self, request):
        """
        Authenticate user login.
        """
        email = request.data.get('email')
        password = request.data.get('password')

        user = authenticate(username=email, password=password)
        if user:
            logger.info(f"[{now()}] User {user.username} logged in successfully")
            return Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
        else:
            logger.warning(f"[{now()}] Failed login attempt: {email}")
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
