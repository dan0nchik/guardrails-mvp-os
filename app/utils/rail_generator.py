"""
Dynamic Rail Generator — async, delegates to DynamicRuleEngine.

Maintains backward-compatible interface (profileId, summary, config)
while adding new fields (rules, new_rules) from the LLM-based engine.
"""
import hashlib
import structlog
from typing import Any, Dict, List, Optional

from app.config import settings

logger = structlog.get_logger()


class RailGenerator:
    """
    Dynamically generate guardrails based on conversation context.

    When dynamic_rails_enabled, delegates to DynamicRuleEngine for LLM-based
    classification. Falls back to regex-based detection otherwise.
    """

    def __init__(self):
        self.rule_engine = None
        self._initialized = False

    async def initialize(self):
        """Initialize the rule engine if dynamic rails are enabled."""
        if settings.dynamic_rails_enabled:
            try:
                from app.dynamic_rails.rule_engine import DynamicRuleEngine
                self.rule_engine = DynamicRuleEngine()
                await self.rule_engine.initialize()
                self._initialized = True
                logger.info("RailGenerator initialized with DynamicRuleEngine")
            except Exception as e:
                logger.warning("Failed to init DynamicRuleEngine, using fallback", error=str(e))
                self._initialized = False
        else:
            logger.info("Dynamic rails disabled, RailGenerator in passthrough mode")

    async def generate(
        self,
        user_message: str,
        session_state: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate dynamic guardrails based on conversation context.

        Args:
            user_message: The user's message
            session_state: Session state (for accumulated rules)
            history: Conversation history

        Returns:
            {
                'profileId': str,
                'summary': str,
                'config': Optional[str],
                'rules': Optional[List[Dict]],       # all active rules
                'new_rules': Optional[List[Dict]],    # added this turn
            }
            or None if no rules needed
        """
        session_state = session_state or {}
        history = history or []

        # Use LLM-based engine if available
        if self.rule_engine and self._initialized:
            return await self._generate_llm(user_message, session_state, history)

        # Fallback: no generation in passthrough mode
        return None

    async def _generate_llm(
        self,
        user_message: str,
        session_state: Dict[str, Any],
        history: List[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        """Generate rails using LLM-based DynamicRuleEngine."""
        try:
            result = await self.rule_engine.process_turn(
                user_message=user_message,
                session_state=session_state,
                history=history,
            )

            all_rules = result.get('all_active_rules', [])
            new_rules = result.get('new_rules', [])
            domains = result.get('domains', [])
            classification = result.get('classification', {})

            if not all_rules and not new_rules:
                return None

            # Generate backward-compatible fields
            domain_str = ', '.join(domains) if domains else 'general'
            profile_id = f"gen_{hashlib.md5(domain_str.encode()).hexdigest()[:12]}"

            reasoning = classification.get('reasoning', '')
            summary = reasoning or f"Динамические правила для доменов: {domain_str}"

            # Build config string for display
            config_lines = [f"# Динамические правила ({len(all_rules)} активных)"]
            config_lines.append(f"domains: [{domain_str}]")
            config_lines.append("rules:")
            for rule in all_rules:
                rid = rule.get('rule_id', '?')
                rtype = rule.get('rule_type', '?')
                desc = rule.get('description', '')
                sev = rule.get('severity', 'medium')
                config_lines.append(f"  - id: {rid}")
                config_lines.append(f"    type: {rtype}")
                config_lines.append(f"    severity: {sev}")
                config_lines.append(f"    description: {desc}")

            return {
                'profileId': profile_id,
                'summary': summary,
                'config': '\n'.join(config_lines),
                'rules': all_rules,
                'new_rules': new_rules,
            }

        except Exception as e:
            logger.error("LLM rail generation failed", exc_info=e)
            return None
