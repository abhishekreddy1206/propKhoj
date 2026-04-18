from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, ChatMessageViewSet, ConversationViewSet, UserViewSet, UserProfileView
from .analytics_views import (
    AnalyticsDashboardView, 
    ConversationMetricsView,
    TopicTrendsView,
    PropertyInterestView,
    UserIntentClustersView,
    DashboardSummaryView
)

router = DefaultRouter()
router.register(r'properties', PropertyViewSet)
# router.register(r'chats', ChatMessageViewSet, basename="chats")
router.register(r'conversations', ConversationViewSet, basename='conversations')
router.register(r'users', UserViewSet)
router.register(r'profile', UserProfileView, basename='profile')

urlpatterns = [
    path('', include(router.urls)),
    path('chats/chat/', ChatMessageViewSet.as_view({'post': 'chat'}), name="chat"),
    path('chats/sample-prompts/', ChatMessageViewSet.as_view({'get': 'sample_prompts'}), name="sample-prompts"),
    path('chats/feedback/<int:chat_id>/', ChatMessageViewSet.as_view({'post': 'message_feedback'}), name="message-feedback"),

    # Analytics Dashboard
    path('admin/analytics/', AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    
    # Analytics API Endpoints
    path('analytics/metrics/', ConversationMetricsView.as_view(), name='api_metrics'),
    path('analytics/topics/', TopicTrendsView.as_view(), name='api_topics'),
    path('analytics/properties/', PropertyInterestView.as_view(), name='api_properties'),
    path('analytics/intents/', UserIntentClustersView.as_view(), name='api_intents'),
    path('analytics/summary/', DashboardSummaryView.as_view(), name='api_summary'),
]
