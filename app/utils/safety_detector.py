"""
Safety detector for harmful/dangerous content.

This is a basic implementation for demonstration purposes.
In production, use proper content moderation services like OpenAI Moderation API.
"""
import re
from typing import List, Dict, Any


class SafetyDetector:
    """Simple safety detector using keyword and pattern matching."""

    def __init__(self):
        # Dangerous content patterns
        self.harmful_keywords = {
            'violence': [
                r'\b(?:kill|murder|hurt|attack|weapon|gun|knife|bomb|explosive|poison)\b',
                r'\bhow\s+(?:to|do\s+i|can\s+i)\s+(?:kill|hurt|attack|make\s+a\s+bomb)',
            ],
            'illegal': [
                r'\b(?:hack|crack|steal|pirate|illegal|fraud|scam)\b',
                r'\bhow\s+(?:to|do\s+i|can\s+i)\s+(?:hack|steal|break\s+into)',
            ],
            'self_harm': [
                r'\b(?:suicide|self[\s-]harm|cut\s+myself|end\s+my\s+life)\b',
                r'\bhow\s+(?:to|do\s+i|can\s+i)\s+(?:kill\s+myself|commit\s+suicide)',
            ],
            'abuse': [
                r'\b(?:abuse|exploit|manipulate|groom|traffick)\b',
            ]
        }

    def detect(self, text: str, context: str = 'input') -> List[Dict[str, Any]]:
        """
        Detect harmful content in text.

        Args:
            text: Text to check
            context: Either 'input' (user message) or 'output' (assistant response)

        Returns:
            List of detected safety issues with details
        """
        detections = []
        text_lower = text.lower()

        for category, patterns in self.harmful_keywords.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    category_names = {
                        'violence': 'насильственного',
                        'illegal': 'нелегального',
                        'self_harm': 'суицидального',
                        'abuse': 'жестокого'
                    }
                    detections.append({
                        'category': category,
                        'description': f'Обнаружен потенциально опасный контент ({category_names.get(category, category)})',
                        'snippet': match.group(),
                        'pattern': pattern,
                        'context': context
                    })

        return detections

    def is_safe(self, text: str, context: str = 'input') -> bool:
        """Check if text is safe (no harmful content detected)."""
        return len(self.detect(text, context)) == 0

    def check_input(self, user_message: str) -> Dict[str, Any]:
        """
        Check user input for safety issues.

        Returns:
            {
                'safe': bool,
                'detections': List[Dict],
                'should_block': bool
            }
        """
        detections = self.detect(user_message, 'input')

        return {
            'safe': len(detections) == 0,
            'detections': detections,
            'should_block': len(detections) > 0
        }

    def check_output(self, assistant_message: str) -> Dict[str, Any]:
        """
        Check assistant output for safety issues.

        Returns:
            {
                'safe': bool,
                'detections': List[Dict],
                'should_block': bool
            }
        """
        detections = self.detect(assistant_message, 'output')

        # Also check if the assistant is providing instructions for harmful activities
        harmful_instruction_patterns = [
            r'(?:here\'s how|follow these steps|you can make|to create a)',
            r'(?:first|step 1|1\.).*(?:obtain|get|find|buy)',
        ]

        for pattern in harmful_instruction_patterns:
            if re.search(pattern, assistant_message.lower()):
                detections.append({
                    'category': 'harmful_instructions',
                    'description': 'Ассистент предоставляет потенциально опасные инструкции',
                    'snippet': 'Обнаружены инструкции',
                    'pattern': pattern,
                    'context': 'output'
                })

        return {
            'safe': len(detections) == 0,
            'detections': detections,
            'should_block': len(detections) > 0
        }
