from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, ChatMessageViewSet, ConversationViewSet, UserViewSet

router = DefaultRouter()
router.register(r'properties', PropertyViewSet)
router.register(r'chats', ChatMessageViewSet)
router.register(r'conversations', ConversationViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
