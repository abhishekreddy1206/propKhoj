from datetime import timezone
from django.db import models
from openai import OpenAI
import logging, json
from .models import *

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')

client = OpenAI()


class ConversationManager(models.Manager):
    def get_or_create_conversation(self, user, conversation_id=None):
        """
        Retrieve an existing conversation or create a new one.
        """
        if conversation_id:
            try:
                return self.get(id=conversation_id)
            except Conversation.DoesNotExist:
                raise ValueError("Invalid conversation ID")
        return self.create(user=user)


class ChatMessageManager(models.Manager):
    def store_message(self, conversation, user, text, sender):
        """
        Store a new chat message.
        """
        return self.create(conversation=conversation, user=user, text=text, sender=sender)

    def get_chat_history(self, conversation):
        """
        Retrieve chat history in OpenAI format.
        """
        chat_history = self.filter(conversation=conversation).order_by("timestamp")
        formatted_messages = [{"role": "system", "content": "You are a helpful real estate AI assistant."}]

        for msg in chat_history:
            role = "user" if msg.sender == "user" else "assistant"
            formatted_messages.append({"role": role, "content": msg.text})

        return formatted_messages

    def get_ai_response(self, conversation):
        """
        Call OpenAI API and return a response.
        """
        messages = self.get_chat_history(conversation)

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "I'm currently unable to fetch responses. Please try again later."
    
    def get_sample_prompts(self, conversation=None):
        """
        Get AI-generated sample prompts for the chat interface.
        If conversation is provided, generates follow-up prompts based on chat history.
        """
        sample_prompts = [
            "Find me a 2BHK apartment in Bangalore",
            "Show me commercial office spaces under ₹50L",
            "What are the best areas to invest in Mumbai?",
            "List luxury villas in Delhi"
        ]
        
        sample_prompts_followup = [
            "Can you tell me more about the property?",
            "What are the nearby amenities?",
            "How is the connectivity to the city center?",
            "What are the payment terms?"
        ]
        
        try:
            system_prompt = f"""You are a helpful real estate AI assistant. Generate 4 sample questions that users might ask about real estate. 
            Use these as examples but not the same: {json.dumps(sample_prompts)}
            Return them in this exact JSON format:
            {{
                "prompts": [
                    "question 1",
                    "question 2",
                    "question 3",
                    "question 4"
                ]
            }}"""
            
            if not conversation:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate 4 sample prompts"}
                ]
            else:
                chat_history = self.get_chat_history(conversation)
                messages = [
                    {"role": "system", "content": system_prompt},
                    *chat_history[1:],
                    {"role": "user", 
                     "content": f"""Based on this conversation, what are 4 relevant follow-up questions I might want to ask? 
                                    Use these as examples but not the same: {json.dumps(sample_prompts_followup)}"""}
                ]

            logger.info(f"Sending messages to OpenAI: {json.dumps(messages)}")
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            logger.info(f"OpenAI response content: {content}")
            
            prompts = json.loads(content)
            return prompts.get("prompts", [])
            
        except Exception as e:
            logger.error(f"Error in get_sample_prompts: {str(e)}", exc_info=True)
            # Return fallback prompts
            return sample_prompts if not conversation else sample_prompts_followup


class PropertyManager(models.Manager):
    def generate_embedding(self, text):
        """
        Generate OpenAI embedding for given text
        """
        try:
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return list(response.data[0].embedding)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def generate_property_text(self, property_instance):
        """
        Generate searchable text from property instance
        """
        texts = [
            property_instance.title,
            property_instance.description,
            f"Property type: {property_instance.property_type.name}",
            f"Location: {property_instance.address.city}, {property_instance.address.state}",
            f"Price: {property_instance.price} {property_instance.currency.code}",
        ]

        # Add optional fields
        optional_fields = {
            'bedrooms': 'bedrooms',
            'bathrooms': 'bathrooms',
            'size': 'square feet',
            'building_name': 'Building',
            'landmark': 'Landmark'
        }

        for field, suffix in optional_fields.items():
            value = getattr(property_instance, field)
            if value:
                texts.append(f"{field.replace('_', ' ').title()}: {value} {suffix}")

        # Add amenities (handling as JSON array)
        if property_instance.amenities:
            if isinstance(property_instance.amenities, list):
                amenity_text = ", ".join(property_instance.amenities)
                texts.append(f"Amenities: {amenity_text}")

        # Add furnishing details if present
        if property_instance.furnishing_details:
            if isinstance(property_instance.furnishing_details.get('details', []), list):
                furnishing_text = ", ".join(property_instance.furnishing_details.get('details', []))
                texts.append(f"Furnishing: {furnishing_text}")

        # Add tags
        if property_instance.tags and isinstance(property_instance.tags, list):
            texts.append("Tags: " + ", ".join(property_instance.tags))

        return " ".join(filter(None, texts))

    def update_embedding(self, property_instance):
        """
        Update embedding for a property instance
        """
        try:
            text = self.generate_property_text(property_instance)
            embedding = self.generate_embedding(text)
            
            property_instance.embedding = embedding
            property_instance.embedding_updated_at = timezone.now()
            property_instance.save(update_fields=['embedding', 'embedding_updated_at'])
            
            logger.info(f"Successfully updated embedding for property {property_instance.property_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating embedding for property {property_instance.property_id}: {str(e)}")
            return False

    def search_by_similarity(self, query, limit=10, filters=None):
        """
        Search properties using vector similarity
        """
        try:
            query_embedding = self.generate_embedding(query)
            
            # Start with base query
            queryset = self.get_queryset()
            
            # Apply any additional filters
            if filters:
                queryset = queryset.filter(**filters)
            
            # Order by similarity
            results = queryset.order_by(
                models.F('embedding').cosine_distance(query_embedding)
            )[:limit]
            
            return results
            
        except Exception as e:
            logger.error(f"Error in search_by_similarity: {str(e)}")
            raise

    def bulk_update_embeddings(self, queryset=None):
        """
        Bulk update embeddings for multiple properties
        """
        if queryset is None:
            queryset = self.get_queryset()

        success_count = 0
        error_count = 0

        for property_instance in queryset:
            try:
                if self.update_embedding(property_instance):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error in bulk update for property {property_instance.property_id}: {str(e)}")

        return {'success': success_count, 'errors': error_count}
