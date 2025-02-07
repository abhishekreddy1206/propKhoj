from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, ChatMessageViewSet, ConversationViewSet, UserViewSet

router = DefaultRouter()
router.register(r'properties', PropertyViewSet)
router.register(r'chats', ChatMessageViewSet, basename="chats")
router.register(r'conversations', ConversationViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('chats/chat/', ChatMessageViewSet.as_view({'post': 'chat'}), name="chat"),
    path('chats/sample-prompts/', ChatMessageViewSet.as_view({'get': 'sample_prompts'}), name="sample-prompts"),
]
