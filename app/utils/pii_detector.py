"""
Simple PII detection utility for MVP.

This is a basic implementation for demonstration purposes.
In production, use proper PII detection services.
"""
import re
from typing import List, Dict, Any


class PIIDetector:
    """Simple PII detector using regex patterns."""

    def __init__(self):
        self.patterns = {
            'credit_card': {
                'pattern': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
                'description': 'Обнаружен номер банковской карты'
            },
            'ssn': {
                'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
                'description': 'Обнаружен номер социального страхования'
            },
            'email': {
                'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'description': 'Обнаружен адрес электронной почты'
            },
            'phone': {
                'pattern': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
                'description': 'Обнаружен номер телефона'
            },
            'ip_address': {
                'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                'description': 'Обнаружен IP-адрес'
            }
        }

    def detect(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PII in text.

        Returns:
            List of detected PII items with details
        """
        detections = []

        for pii_type, config in self.patterns.items():
            matches = re.finditer(config['pattern'], text)
            for match in matches:
                detections.append({
                    'type': pii_type,
                    'description': config['description'],
                    'snippet': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })

        return detections

    def has_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        return len(self.detect(text)) > 0
