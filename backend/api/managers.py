from datetime import timezone
from django.db import models
from django.core.cache import cache
from openai import OpenAI
import logging, json, hashlib, re
from .models import *

logger = logging.getLogger('django')
chat_logger = logging.getLogger('chat')

_openai_client = None


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


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


SYSTEM_PROMPT = """You are PropKhoj, an expert real estate AI assistant. Your role is to help users find and understand properties.

When property data is provided to you:
- Reference specific properties by name, price, and location
- Compare properties when the user asks
- Highlight key features relevant to the user's stated preferences
- Provide honest assessments including potential drawbacks

When no property data is available:
- Provide general real estate advice
- Ask clarifying questions about the user's needs (budget, location, property type, bedrooms)

Response guidelines:
- Be conversational but professional
- Use markdown formatting for readability (bold for property names, bullet lists for features)
- Keep responses under 300 words unless the user asks for detailed comparisons
- Always suggest next steps (schedule a visit, compare with another property, etc.)
"""


class ChatMessageManager(models.Manager):
    def store_message(self, conversation, user, text, sender):
        """
        Store a new chat message.
        """
        return self.create(conversation=conversation, user=user, text=text, sender=sender)

    MAX_RECENT_MESSAGES = 10  # Keep last 5 turns (user + bot pairs)

    def get_chat_history(self, conversation):
        """
        Retrieve chat history in OpenAI format with sliding window.
        For long conversations, older messages are summarized to cap token usage.
        """
        chat_history = list(self.filter(conversation=conversation).order_by("timestamp"))
        total_messages = len(chat_history)
        formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if total_messages > self.MAX_RECENT_MESSAGES:
            # Summarize older messages if summary is stale
            older_count = total_messages - self.MAX_RECENT_MESSAGES
            if conversation.summary_message_count < older_count:
                older_messages = chat_history[:older_count]
                self._update_conversation_summary(conversation, older_messages, older_count)

            if conversation.summary:
                formatted_messages.append({
                    "role": "system",
                    "content": f"Summary of earlier conversation: {conversation.summary}"
                })

            # Only include recent messages
            recent_messages = chat_history[-self.MAX_RECENT_MESSAGES:]
        else:
            recent_messages = chat_history

        for msg in recent_messages:
            role = "user" if msg.sender == "user" else "assistant"
            formatted_messages.append({"role": role, "content": msg.text})

        return formatted_messages

    def _update_conversation_summary(self, conversation, older_messages, older_count):
        """
        Generate a summary of older conversation messages and store it.
        """
        try:
            summary_input = "\n".join(
                f"{msg.sender}: {msg.text}" for msg in older_messages
            )
            response = get_openai_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Summarize this real estate conversation in 2-3 sentences. Preserve the user's preferences, budget, desired location, property type, and any specific properties discussed."},
                    {"role": "user", "content": summary_input}
                ],
                max_tokens=150
            )
            if response.usage:
                chat_logger.info(f"OpenAI usage [conversation_summary]: {response.usage.prompt_tokens}p/{response.usage.completion_tokens}c tokens")

            conversation.summary = response.choices[0].message.content
            conversation.summary_message_count = older_count
            conversation.save(update_fields=['summary', 'summary_message_count'])
            chat_logger.info(f"Updated summary for conversation {conversation.id} ({older_count} messages summarized)")
        except Exception as e:
            logger.error(f"Error generating conversation summary: {str(e)}")

    def get_ai_response(self, conversation, property_context=None):
        """
        Call OpenAI API and return a response.
        Optionally injects property search results into the conversation context.
        """
        messages = self.get_chat_history(conversation)

        if property_context:
            context_text = "Here are relevant properties from our database matching the user's query:\n\n"
            for i, prop_text in enumerate(property_context, 1):
                context_text += f"{i}. {prop_text}\n\n"
            context_text += "Use these properties in your response. Reference them by name and provide specific details. If none match well, say so and ask clarifying questions."

            # Append property context after the user's question for proper RAG grounding
            messages.append({"role": "system", "content": context_text})

        try:
            response = get_openai_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=800
            )
            if response.usage:
                chat_logger.info(f"OpenAI usage [get_ai_response]: {response.usage.prompt_tokens}p/{response.usage.completion_tokens}c tokens")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "I'm currently unable to fetch responses. Please try again later."

    def get_sample_prompts(self, conversation=None, user=None):
        """
        Get AI-generated sample prompts for the chat interface.
        If conversation is provided, generates follow-up prompts based on chat history.
        """
        city = user.address.city if user and user.address and user.address.city else "Sacramento"
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

        # Check cache for default prompts (no conversation)
        if not conversation:
            cache_key = f"sample_prompts_{city}"
            cached = cache.get(cache_key)
            if cached:
                return cached

        try:
            system_prompt = f"""You are a helpful real estate AI assistant. Generate 4 sample questions that users might ask about real estate.
            Use these as examples but not the same: {json.dumps(sample_prompts)}.
            Also generate these prompts for the city the user is in which is: {city}.
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
                # Only use the last 6 messages for follow-up generation to save tokens
                recent_history = chat_history[1:][-6:]
                messages = [
                    {"role": "system", "content": system_prompt},
                    *recent_history,
                    {"role": "user",
                     "content": f"""Based on this conversation, what are 4 relevant follow-up questions I might want to ask?
                                    Use these as examples but not the same: {json.dumps(sample_prompts_followup)}"""}
                ]

            logger.info(f"Sending {len(messages)} messages to OpenAI for sample prompts")

            response = get_openai_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=200
            )
            if response.usage:
                chat_logger.info(f"OpenAI usage [get_sample_prompts]: {response.usage.prompt_tokens}p/{response.usage.completion_tokens}c tokens")

            content = response.choices[0].message.content
            logger.info(f"OpenAI sample prompts response received ({len(content)} chars)")

            prompts = json.loads(content)
            result = prompts.get("prompts", [])

            # Cache default prompts for 1 hour
            if not conversation:
                cache.set(cache_key, result, timeout=3600)

            return result

        except Exception as e:
            logger.error(f"Error in get_sample_prompts: {str(e)}", exc_info=True)
            # Return fallback prompts
            return sample_prompts if not conversation else sample_prompts_followup


class PropertyManager(models.Manager):
    # Property-related keywords for search intent detection
    SEARCH_KEYWORDS = re.compile(
        r'\b('
        r'bhk|bedroom|bathroom|apartment|flat|house|villa|plot|office|commercial|residential|'
        r'rent|buy|purchase|sell|lease|invest|'
        r'lakh|lac|crore|cr|budget|under|above|below|between|price|cost|afford|'
        r'sqft|sq\s*ft|square\s*feet|area|size|'
        r'furnished|unfurnished|semi-furnished|parking|amenit|'
        r'bangalore|mumbai|delhi|pune|hyderabad|chennai|kolkata|gurgaon|noida|'
        r'sacramento|san\s*francisco|los\s*angeles|new\s*york|austin|seattle|'
        r'find|search|show|list|looking\s+for|suggest|recommend'
        r')\b',
        re.IGNORECASE
    )
    # Pattern for numeric property specs like "2BHK", "3 bed", "$500k"
    NUMERIC_SPEC = re.compile(r'\d+\s*(?:bhk|bed|bath|lakh|lac|cr|crore|k|m|l)', re.IGNORECASE)
    # Currency patterns
    CURRENCY_PATTERN = re.compile(r'[$₹€£]\s*\d+|\d+\s*[$₹€£]')

    def is_search_query(self, message):
        """
        Determine if a message is a new property search query vs a conversational follow-up.
        Returns True if the message likely contains search intent.
        """
        text = message.strip()
        # Check for numeric property specs (e.g., "2BHK", "3 bed")
        if self.NUMERIC_SPEC.search(text):
            return True
        # Check for currency amounts
        if self.CURRENCY_PATTERN.search(text):
            return True
        # Check for property-related keywords
        if self.SEARCH_KEYWORDS.search(text):
            return True
        return False

    def generate_embedding(self, text, use_cache=False):
        """
        Generate OpenAI embedding for given text.
        If use_cache=True, checks Django cache first (for query embeddings).
        """
        if use_cache:
            cache_key = f"qemb:{hashlib.md5(text.strip().lower().encode()).hexdigest()}"
            cached = cache.get(cache_key)
            if cached:
                logger.info("Query embedding cache hit")
                return cached

        try:
            response = get_openai_client().embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embedding = list(response.data[0].embedding)

            if use_cache:
                cache.set(cache_key, embedding, timeout=86400)

            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def generate_property_text(self, property_instance):
        """
        Generate semantically rich text from property instance for embeddings and RAG context.
        """
        parts = []

        # Title and description
        if property_instance.title:
            parts.append(property_instance.title)
        if property_instance.description:
            parts.append(property_instance.description)

        # Natural language summary
        try:
            summary = f"This is a {property_instance.property_type.name}"
            if property_instance.bedrooms:
                summary += f" with {property_instance.bedrooms} bedrooms"
            if property_instance.bathrooms:
                summary += f" and {property_instance.bathrooms} bathrooms"
            if property_instance.address:
                summary += f" located in {property_instance.address.city}, {property_instance.address.state}"
                if property_instance.address.zip_code:
                    summary += f" (ZIP: {property_instance.address.zip_code})"
            summary += f". Listed at {property_instance.price} {property_instance.currency.code}"
            if property_instance.price_type != 'one_time':
                summary += f" ({property_instance.price_type})"
            parts.append(summary)
        except Exception:
            pass

        # Size info
        if property_instance.size:
            parts.append(f"Total area: {property_instance.size} sq ft")
            if property_instance.price_per_sqft:
                parts.append(f"Price per sq ft: {property_instance.price_per_sqft}")

        # Features
        if property_instance.furnished:
            parts.append("This property is furnished")
        if property_instance.year_built:
            parts.append(f"Built in {property_instance.year_built}")
        if property_instance.parking_spaces:
            parts.append(f"{property_instance.parking_spaces} parking spaces")
        if property_instance.building_name:
            parts.append(f"Located in {property_instance.building_name}")
        if property_instance.landmark:
            parts.append(f"Near {property_instance.landmark}")

        # Amenities
        if property_instance.amenities and isinstance(property_instance.amenities, list):
            parts.append(f"Amenities include: {', '.join(property_instance.amenities)}")

        # Furnishing details
        if property_instance.furnishing_details:
            details = property_instance.furnishing_details.get('details', [])
            if isinstance(details, list) and details:
                parts.append(f"Furnishing: {', '.join(details)}")

        # Tags
        if property_instance.tags and isinstance(property_instance.tags, list):
            parts.append(f"Tags: {', '.join(property_instance.tags)}")

        return ". ".join(filter(None, parts))

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
            query_embedding = self.generate_embedding(query, use_cache=True)

            # Start with base query
            queryset = self.get_queryset()

            # Apply any additional filters
            if filters:
                queryset = queryset.filter(**filters)

            # Use the correct vector comparison syntax based on your DB backend
            queryset = queryset.annotate(
                similarity=models.expressions.RawSQL(
                    "embedding <=> %s::vector",
                    (query_embedding,)
                )
            ).order_by('similarity')[:limit]

            return queryset

        except Exception as e:
            logger.error(f"Error in search_by_similarity: {str(e)}")
            raise

    def extract_search_filters(self, query):
        """
        Use OpenAI function calling to extract structured filters from natural language query.
        Falls back to empty filters on failure.
        """
        try:
            response = get_openai_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract real estate search filters from the user query. Only include filters that are clearly stated."},
                    {"role": "user", "content": query}
                ],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "search_properties",
                        "description": "Search for properties with filters",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "min_price": {"type": "number", "description": "Minimum price"},
                                "max_price": {"type": "number", "description": "Maximum price"},
                                "bedrooms": {"type": "integer", "description": "Number of bedrooms"},
                                "city": {"type": "string", "description": "City name"},
                                "property_type": {"type": "string", "description": "Type of property"},
                            }
                        }
                    }
                }],
                tool_choice="auto",
                max_tokens=100
            )

            if response.usage:
                chat_logger.info(f"OpenAI usage [extract_search_filters]: {response.usage.prompt_tokens}p/{response.usage.completion_tokens}c tokens")

            if response.choices[0].message.tool_calls:
                args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
                django_filters = {}
                if 'min_price' in args and args['min_price']:
                    django_filters['price__gte'] = args['min_price']
                if 'max_price' in args and args['max_price']:
                    django_filters['price__lte'] = args['max_price']
                if 'bedrooms' in args and args['bedrooms']:
                    django_filters['bedrooms'] = args['bedrooms']
                if 'city' in args and args['city']:
                    django_filters['address__city__icontains'] = args['city']
                return django_filters

            return {}

        except Exception as e:
            logger.error(f"Error extracting search filters: {str(e)}")
            return {}

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
