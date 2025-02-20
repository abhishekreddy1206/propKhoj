from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse
from .models import Conversation, ChatMessage
from .chat_analytics import ChatAnalytics
from openai import OpenAI

client = OpenAI()  # Initialize OpenAI client with your API key from settings

@method_decorator(staff_member_required, name='dispatch')
class AnalyticsDashboardView(TemplateView):
    """Admin analytics dashboard view"""
    template_name = 'admin/analytics_dashboard.html'


class BaseAnalyticsAPIView(View):
    """Base class for all analytics API views"""
    
    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_time_period(self):
        """Get time period from request GET parameters"""
        return int(self.request.GET.get('days', 30))
    
    def get_analytics(self):
        """Get analytics instance with OpenAI client"""
        return ChatAnalytics(client=client)


class ConversationMetricsView(BaseAnalyticsAPIView):
    """API endpoint for conversation metrics"""
    
    def get(self, request, *args, **kwargs):
        analytics = self.get_analytics()
        time_period = self.get_time_period()
        metrics = analytics.get_basic_metrics(time_period=time_period)
        return JsonResponse(metrics)


class TopicTrendsView(BaseAnalyticsAPIView):
    """API endpoint for conversation topic trends"""
    
    def get(self, request, *args, **kwargs):
        analytics = self.get_analytics()
        time_period = self.get_time_period()
        trends = analytics.get_topic_trends(time_period=time_period)
        return JsonResponse({"topic_trends": trends})


class PropertyInterestView(BaseAnalyticsAPIView):
    """API endpoint for property interest analysis"""
    
    def get(self, request, *args, **kwargs):
        analytics = self.get_analytics()
        property_interest = analytics.get_property_interest_analysis()
        return JsonResponse({"property_interest": property_interest})


class UserIntentClustersView(BaseAnalyticsAPIView):
    """API endpoint for user intent clustering"""
    
    def get(self, request, *args, **kwargs):
        analytics = self.get_analytics()
        time_period = self.get_time_period()
        clusters = analytics.generate_user_intent_clusters(time_period=time_period)
        return JsonResponse(clusters)


class DashboardSummaryView(BaseAnalyticsAPIView):
    """API endpoint for AI-generated dashboard summary"""
    
    def get(self, request, *args, **kwargs):
        analytics = self.get_analytics()
        summary = analytics.generate_admin_dashboard_summary()
        return JsonResponse({"summary": summary})
