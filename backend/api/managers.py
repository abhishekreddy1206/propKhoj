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
