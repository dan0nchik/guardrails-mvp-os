"""
Dynamic Rule Engine.

Orchestrates LLM classification, rule generation, and rule lifecycle.
Rules accumulate across the session (medical rules persist even if next message is about weather).
"""
import structlog
from typing import Any, Dict, List, Optional

from app.config import settings
from app.dynamic_rails.llm_classifier import LLMTopicClassifier
from app.dynamic_rails.rule_registry import RuleRegistry

logger = structlog.get_logger()


class DynamicRuleEngine:
    """
    Engine for dynamic guardrail rule management.

    process_turn() is the main entry point, called once per user message:
    1. Load existing rules from session_state
    2. Classify the message with LLM
    3. Generate new rules (with deduplication)
    4. Return all active rules + new rules + classification
    """

    def __init__(self):
        self.classifier = LLMTopicClassifier()
        self.rule_registry = RuleRegistry()

    async def initialize(self):
        """Initialize the classifier."""
        await self.classifier.initialize()
        logger.info("Dynamic rule engine initialized")

    async def process_turn(
        self,
        user_message: str,
        session_state: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Process a single conversation turn.

        Args:
            user_message: Current user message
            session_state: Session state dict (contains 'dynamic_rules' list)
            history: Conversation history

        Returns:
            {
                'new_rules': List[Dict],        # Rules added this turn
                'all_active_rules': List[Dict],  # All accumulated rules
                'classification': Dict,           # LLM classification result
                'domains': List[str],             # Detected domains
            }
        """
        # Step 1: Load existing rules
        existing_rules = session_state.get('dynamic_rules', [])

        # Step 2: Classify with LLM
        classification = await self.classifier.classify(
            user_message=user_message,
            history=history,
            existing_rules=existing_rules,
        )

        # Step 3: Generate new rules
        new_rules = []
        suggested = classification.get('suggested_rules', [])
        domains = classification.get('domains', [])

        # Add template rules for detected domains (if not already present)
        existing_ids = {r.get('rule_id', r.get('id', '')) for r in existing_rules}
        for domain in domains:
            templates = self.rule_registry.get_templates_for_domain(domain)
            for tmpl in templates:
                if tmpl['rule_id'] not in existing_ids:
                    new_rules.append(tmpl)
                    existing_ids.add(tmpl['rule_id'])

        # Add LLM-suggested custom rules (deduplicate)
        for rule in suggested:
            rule_id = rule.get('rule_id', '')
            if rule_id and rule_id not in existing_ids:
                new_rules.append(rule)
                existing_ids.add(rule_id)

        # Step 4: Combine all rules (with limit)
        max_rules = settings.dynamic_rails_max_rules_per_session
        all_active_rules = existing_rules + new_rules
        if len(all_active_rules) > max_rules:
            all_active_rules = all_active_rules[-max_rules:]
            logger.warning("Rule limit reached, trimming oldest rules", max=max_rules)

        logger.info(
            "Dynamic rules processed",
            new_count=len(new_rules),
            total_count=len(all_active_rules),
            domains=domains,
        )

        return {
            'new_rules': new_rules,
            'all_active_rules': all_active_rules,
            'classification': classification,
            'domains': domains,
        }
