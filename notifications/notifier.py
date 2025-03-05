import requests
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from openai import OpenAI

from config import SLACK_WEBHOOK_URL, ENABLE_SLACK_NOTIFICATIONS, OPENAI_API_KEY
from utils.logger import setup_logger

logger = setup_logger("notifier")

class LeadNotifier:
    """Handles notifications for new leads."""
    
    def __init__(self):
        """Initialize the notifier with necessary clients."""
        self.webhook_url = SLACK_WEBHOOK_URL
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Define the message generation tool
        self.message_tool = {
            "type": "function",
            "function": {
                "name": "generate_csm_message",
                "description": "Generate a friendly, informative Slack message for CSMs about a new lead",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "greeting": {
                            "type": "string",
                            "description": "Friendly greeting for CSMs"
                        },
                        "main_points": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Key points about why this lead is valuable"
                        },
                        "action_suggestions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Suggested actions CSMs can take"
                        },
                        "urgency_level": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "How urgent is this information"
                        }
                    },
                    "required": ["greeting", "main_points", "action_suggestions", "urgency_level"]
                }
            }
        }
        
        self.slack_enabled = ENABLE_SLACK_NOTIFICATIONS and SLACK_WEBHOOK_URL is not None
        if self.slack_enabled:
            logger.info(f"Slack notifications enabled with webhook URL: {SLACK_WEBHOOK_URL[:20]}...")
        else:
            logger.warning("Slack notifications disabled - Check ENABLE_SLACK_NOTIFICATIONS and SLACK_WEBHOOK_URL")

    def _generate_slack_message(self, lead: Dict[str, Any]) -> str:
        """Generate a CSM-friendly Slack message using GPT-4."""
        try:
            # Safely parse JSON strings with default empty lists
            try:
                value_types = json.loads(lead.get("value_types", "[]")) if lead.get("value_types") else []
                action_items = json.loads(lead.get("action_items", "[]")) if lead.get("action_items") else []
            except json.JSONDecodeError:
                logger.warning("Failed to parse value_types or action_items JSON, using empty lists")
                value_types = []
                action_items = []
            
            prompt = f"""
            Generate a friendly, informative Slack message for Customer Success Managers about this lead:
            
            Company: {lead.get('company', 'Unknown Company')}
            Title: {lead.get('title', 'No Title')}
            Description: {lead.get('description', 'No description available')}
            
            Value Types: {', '.join(value_types) if value_types else 'None specified'}
            Suggested Actions: {', '.join(action_items) if action_items else 'None specified'}
            
            Additional Context:
            - Relevance Score: {lead.get('relevance_score', 'N/A')}
            - Value Explanation: {lead.get('csm_value_explanation', 'N/A')}
            
            Create a message that:
            1. Has a friendly, conversational tone
            2. Highlights why this news is important for CSMs
            3. Suggests specific actions they can take
            4. Includes relevant financial or organizational insights
            5. Maintains professionalism while being engaging
            
            Generate the message structure using the generate_csm_message function.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",  # Changed to a more stable model
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates engaging, actionable Slack messages for Customer Success Managers."},
                    {"role": "user", "content": prompt}
                ],
                tools=[self.message_tool],
                tool_choice={"type": "function", "function": {"name": "generate_csm_message"}}
            )
            
            # Check if we have a valid response and tool calls
            if not response or not response.choices or not response.choices[0].message or not response.choices[0].message.tool_calls:
                logger.error("Invalid response from OpenAI API")
                return self._generate_fallback_message(lead)
            
            # Extract the function call
            function_call = response.choices[0].message.tool_calls[0].function
            if not function_call or not function_call.arguments:
                logger.error("No function call arguments in response")
                return self._generate_fallback_message(lead)
            
            try:
                message_structure = json.loads(function_call.arguments)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse function call arguments: {str(e)}")
                return self._generate_fallback_message(lead)
            
            # Validate message structure
            required_fields = ["greeting", "main_points", "action_suggestions", "urgency_level"]
            if not all(field in message_structure for field in required_fields):
                logger.error("Missing required fields in message structure")
                return self._generate_fallback_message(lead)
            
            # Format the Slack message with safe access to fields
            message_parts = []
            
            # Add greeting
            message_parts.append(message_structure.get('greeting', 'Hi CSM team!'))
            message_parts.append("")  # Empty line
            
            # Add lead header
            message_parts.append(f"🔍 *New Lead Alert for {lead.get('company', 'Unknown Company')}*")
            message_parts.append(f"<{lead.get('url', '#')}|{lead.get('title', 'No Title')}>")
            message_parts.append("")  # Empty line
            
            # Add main points
            message_parts.append("*Why this matters:*")
            for point in message_structure.get('main_points', []):
                message_parts.append(f"• {point}")
            message_parts.append("")  # Empty line
            
            # Add action suggestions
            message_parts.append("*Suggested Actions:*")
            for action in message_structure.get('action_suggestions', []):
                message_parts.append(f"📌 {action}")
            
            # Add urgency level
            urgency_emojis = {
                "high": "🚨",
                "medium": "⚡",
                "low": "ℹ️"
            }
            urgency_level = message_structure.get('urgency_level', 'low')
            message_parts.append("")  # Empty line
            message_parts.append(
                f"{urgency_emojis.get(urgency_level, 'ℹ️')} *Urgency Level:* {urgency_level.title()}"
            )
            
            # Join all parts with newlines
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Error generating Slack message: {str(e)}")
            return self._generate_fallback_message(lead)

    def _generate_fallback_message(self, lead: Dict[str, Any]) -> str:
        """Generate a simple fallback message if the AI generation fails."""
        return (
            f"🔍 *New Lead Alert for {lead['company']}*\n"
            f"<{lead['url']}|{lead['title']}>\n\n"
            f"Check the article for potential opportunities."
        )

    def notify(self, lead: Dict[str, Any]) -> bool:
        """Send notifications through all enabled channels."""
        logger.info(f"Starting notification process for lead: {lead.get('title', 'Unknown Title')}")
        success = True
        
        # Send Slack notification if enabled
        if self.slack_enabled:
            logger.info("Attempting to send Slack notification...")
            slack_success = self.send_slack_notification(lead)
            if not slack_success:
                logger.error("Failed to send Slack notification")
            success = success and slack_success
        else:
            logger.warning("Skipping Slack notification - notifications are disabled")
        
        return success

    def send_slack_notification(self, lead: Dict[str, Any]) -> bool:
        """Send a notification to Slack about a new lead."""
        if not self.slack_enabled:
            logger.warning("Slack notifications are disabled")
            return False

        try:
            logger.info(f"Preparing Slack message for lead: {lead.get('title', 'Unknown Title')}")
            message = self._generate_slack_message(lead)
            
            logger.info("Sending notification to Slack...")
            response = requests.post(
                self.webhook_url,
                json={
                    "text": message,
                    "unfurl_links": True,
                    "unfurl_media": True
                },
                timeout=5
            )
            
            if response.status_code != 200:
                logger.error(f"Slack API returned non-200 status code: {response.status_code}")
                logger.error(f"Response text: {response.text}")
                return False
                
            response.raise_for_status()
            logger.info(f"Successfully sent Slack notification for {lead['company']}: {lead['title']}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Slack notification: {str(e)}")
            logger.error(f"Request details - URL: {self.webhook_url[:20]}...")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Slack notification: {str(e)}")
            return False

if __name__ == "__main__":
    # Test the notifier
    notifier = LeadNotifier()
    
    test_lead = {
        "company": "Google",
        "title": "Google Announces New AI Initiative",
        "url": "https://example.com/test-lead",
        "description": "Google has announced a major new artificial intelligence initiative that will focus on developing more efficient and ethical AI systems.",
        "source": "BusinessWire",
        "category": "Technology",
        "timestamp": datetime.now().isoformat()
    }
    
    success = notifier.notify(test_lead)
    print(f"Notification {'sent successfully' if success else 'failed'}") 