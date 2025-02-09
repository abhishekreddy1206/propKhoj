from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, ChatMessageViewSet, ConversationViewSet, UserViewSet, UserProfileView

router = DefaultRouter()
router.register(r'properties', PropertyViewSet)
# router.register(r'chats', ChatMessageViewSet, basename="chats")
router.register(r'conversations', ConversationViewSet)
router.register(r'users', UserViewSet)
router.register(r'profile', UserProfileView, basename='profile')

urlpatterns = [
    path('', include(router.urls)),
    path('chats/chat/', ChatMessageViewSet.as_view({'post': 'chat'}), name="chat"),
    path('chats/sample-prompts/', ChatMessageViewSet.as_view({'get': 'sample_prompts'}), name="sample-prompts"),
]
