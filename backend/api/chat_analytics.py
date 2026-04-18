from django.db.models import Count, Avg, F, ExpressionWrapper, fields, Q, FloatField
from django.utils import timezone
from datetime import timedelta
import json
from openai import OpenAI
from collections import Counter
import numpy as np
from .models import (
    Conversation, ChatMessage, Property, User
)

class ChatAnalytics:
    def __init__(self, client=None):
        self.client = client or OpenAI()
    
    def get_basic_metrics(self, time_period=30):
        """Get basic conversation metrics for the specified time period (days)"""
        cutoff_date = timezone.now() - timedelta(days=time_period)
        
        metrics = {
            'total_users': User.objects.count(),
            'total_conversations': Conversation.objects.filter(started_at__gte=cutoff_date).count(),
            'active_conversations': Conversation.objects.filter(status='active').count(),
            'avg_messages_per_conversation': ChatMessage.objects.filter(
                conversation__started_at__gte=cutoff_date
            ).values('conversation').annotate(
                count=Count('id')
            ).aggregate(avg=Avg('count'))['avg'] or 0,
            'avg_response_time': self._calculate_avg_response_time(cutoff_date),
            'feedback_metrics': self._calculate_feedback_metrics(cutoff_date),
            'conversations_by_day': self._get_conversations_by_day(time_period),
            'peak_usage_hours': self._get_peak_usage_hours(cutoff_date),
            'chats_by_location': self._get_chats_by_location(cutoff_date),
        }
        
        return metrics
    
    def _calculate_avg_response_time(self, cutoff_date):
        """Calculate average response time between user message and bot response"""
        conversations = Conversation.objects.filter(started_at__gte=cutoff_date)

        total_delta = timedelta()
        pair_count = 0

        for conv in conversations[:50]:
            messages = list(
                ChatMessage.objects.filter(conversation=conv, timestamp__gte=cutoff_date)
                .order_by('timestamp')
                .values_list('sender', 'timestamp')
            )
            for i in range(len(messages) - 1):
                if messages[i][0] == 'user' and messages[i + 1][0] == 'bot':
                    total_delta += messages[i + 1][1] - messages[i][1]
                    pair_count += 1

        if pair_count == 0:
            return 0
        return round(total_delta.total_seconds() / pair_count, 2)
    
    def _calculate_feedback_metrics(self, cutoff_date):
        """Calculate feedback metrics for bot responses"""
        feedback_stats = ChatMessage.objects.filter(
            sender='bot',
            timestamp__gte=cutoff_date
        ).values('feedback').annotate(
            count=Count('id')
        )
        
        feedback_dict = {item['feedback']: item['count'] for item in feedback_stats}
        
        total_feedback = sum(count for feedback, count in feedback_dict.items() if feedback != 'none')
        
        if total_feedback > 0:
            positive_rate = (feedback_dict.get('like', 0) / total_feedback) * 100
        else:
            positive_rate = 0
            
        return {
            'like_count': feedback_dict.get('like', 0),
            'dislike_count': feedback_dict.get('dislike', 0),
            'no_feedback_count': feedback_dict.get('none', 0),
            'positive_rate': positive_rate
        }
    
    def _get_conversations_by_day(self, days):
        """Get conversation count by day for trending analysis"""
        result = {}
        now = timezone.now()
        
        for i in range(days):
            date = (now - timedelta(days=i)).date()
            count = Conversation.objects.filter(
                started_at__date=date
            ).count()
            result[date.strftime('%Y-%m-%d')] = count
            
        return result
    
    def _get_peak_usage_hours(self, cutoff_date):
        """Identify peak usage hours based on message volume"""
        messages = ChatMessage.objects.filter(
            timestamp__gte=cutoff_date
        ).extra({'hour': "EXTRACT(hour FROM timestamp)"})

        hourly_counts = messages.values('hour').annotate(count=Count('id'))
        return {int(item['hour']): item['count'] for item in hourly_counts}

    def _get_chats_by_location(self, cutoff_date):
        """Summarize conversation share by user location for dashboard display."""
        location_counts = list(
            Conversation.objects.filter(
                started_at__gte=cutoff_date,
                user__address__city__isnull=False,
                user__address__state__isnull=False,
            )
            .values('user__address__city', 'user__address__state')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        total_conversations = sum(item['count'] for item in location_counts)
        if not total_conversations:
            return []

        return [
            {
                'location': f"{item['user__address__city']}, {item['user__address__state']}",
                'percentage': round((item['count'] / total_conversations) * 100, 1),
            }
            for item in location_counts
        ]
    
    def get_topic_trends(self, time_period=30):
        """Analyze conversation topics and extract trends using AI"""
        cutoff_date = timezone.now() - timedelta(days=time_period)
        
        # Get sample of recent conversations (limit to reasonable amount)
        recent_conversations = Conversation.objects.filter(
            started_at__gte=cutoff_date
        ).order_by('-started_at')[:50]  # Limit to 50 conversations for API efficiency
        
        topics = []
        for conversation in recent_conversations:
            messages = ChatMessage.objects.filter(conversation=conversation).order_by('timestamp')
            if messages.count() > 2:  # Only analyze conversations with meaningful exchanges
                topics.append(self._analyze_conversation_topic(messages))
        
        # Count topic occurrences
        topic_counter = Counter([topic for topic in topics if topic])
        return dict(topic_counter.most_common(10))
    
    def _analyze_conversation_topic(self, messages):
        """Use OpenAI to analyze the topic of a conversation"""
        if not self.client:
            return "AI client not configured"
            
        conversation_text = "\n".join([
            f"{msg.sender}: {msg.text}" for msg in messages[:10]  # First 10 messages for context
        ])
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Analyze this real estate chat conversation. Identify the main topic in 1-3 words only."},
                    {"role": "user", "content": conversation_text}
                ],
                max_tokens=15  # Keep response concise
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            print(f"Error analyzing conversation topic: {str(e)}")
            return None
    
    def get_property_interest_analysis(self):
        """Analyze which properties are generating most interest in conversations"""
        # Get properties mentioned in conversations, with count
        property_mentions = ChatMessage.objects.values('properties').annotate(
            mention_count=Count('id')
        ).filter(properties__isnull=False).order_by('-mention_count')[:20]
        
        property_ids = [item['properties'] for item in property_mentions]
        
        # This would need to be adjusted based on your Property model structure
        # Assuming Property model has fields like 'title', 'type', 'price_range', 'location'
        top_properties = Property.objects.filter(id__in=property_ids).values(
            'id', 'title', 'property_type__name', 'price', 'address__city', 'address__state'
        )
        
        # Map mention counts to property details
        property_interest = []
        for prop in top_properties:
            for mention in property_mentions:
                if mention['properties'] == prop['id']:
                    prop_with_count = prop.copy()
                    prop_with_count['mention_count'] = mention['mention_count']
                    property_interest.append(prop_with_count)
                    break
        
        return property_interest
    
    def generate_user_intent_clusters(self, time_period=30):
        """Use AI to cluster user intents from conversations"""
        cutoff_date = timezone.now() - timedelta(days=time_period)
        
        # Get recent user messages
        user_messages = ChatMessage.objects.filter(
            sender='user',
            timestamp__gte=cutoff_date
        ).order_by('-timestamp')[:500]  # Limit to 500 messages
        
        # Prepare messages for analysis
        message_texts = [msg.text for msg in user_messages]
        
        if not self.client or not message_texts:
            return {"error": "No messages or AI client not configured"}
        
        # Use OpenAI to classify messages into intent clusters
        try:
            sample_size = min(len(message_texts), 100)  # Analyze a sample for efficiency
            sampled_messages = message_texts[:sample_size]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": 
                     "Analyze these user messages from a real estate chatbot. Identify 5-8 common user intents/categories. "
                     "Return JSON with format: {\"intents\": [{\"name\": \"intent_name\", \"description\": \"short description\"}]}"},
                    {"role": "user", "content": json.dumps(sampled_messages)}
                ],
                response_format={"type": "json_object"}
            )
            
            intents = json.loads(response.choices[0].message.content)
            
            # Now classify each message into one of these intents
            intent_counts = self._classify_messages_by_intent(message_texts, intents['intents'])
            
            return {
                "intent_clusters": intents['intents'],
                "intent_distribution": intent_counts
            }
            
        except Exception as e:
            print(f"Error generating intent clusters: {str(e)}")
            return {"error": str(e)}
    
    def _classify_messages_by_intent(self, messages, intents):
        """Classify messages into identified intent categories"""
        if not self.client or not messages:
            return {}
            
        intent_names = [intent['name'] for intent in intents]
        intent_counts = {name: 0 for name in intent_names}
        
        # Process in batches to avoid API limits
        batch_size = 20
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            
            try:
                # Use AI to classify each message batch
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": 
                         f"Classify each message into one of these intent categories: {', '.join(intent_names)}. "
                         "Return JSON with format: {\"classifications\": [\"intent_name\", ...]}"},
                        {"role": "user", "content": json.dumps(batch)}
                    ],
                    response_format={"type": "json_object"}
                )
                
                classifications = json.loads(response.choices[0].message.content)
                
                # Update counts
                for classification in classifications['classifications']:
                    if classification in intent_counts:
                        intent_counts[classification] += 1
                    
            except Exception as e:
                print(f"Error classifying message batch: {str(e)}")
        
        return intent_counts
    
    def generate_admin_dashboard_summary(self):
        """Generate an AI-powered summary of key insights for the admin dashboard"""
        # Gather the basic metrics
        basic_metrics = self.get_basic_metrics()
        topic_trends = self.get_topic_trends()
        
        # Prepare data for summary generation
        dashboard_data = {
            "basic_metrics": basic_metrics,
            "topic_trends": topic_trends,
            "timestamp": timezone.now().isoformat()
        }
        
        if not self.client:
            return "AI summary unavailable - client not configured"
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": 
                     "You are a data analyst for a real estate chatbot platform. "
                     "Generate a concise 2-paragraph executive summary of the current chat analytics. "
                     "Focus on key trends, changes from previous periods, and actionable insights."},
                    {"role": "user", "content": json.dumps(dashboard_data)}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error generating dashboard summary: {str(e)}")
            return "Unable to generate AI summary due to an error."
