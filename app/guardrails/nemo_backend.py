"""
NeMo Guardrails backend implementation.

Uses NVIDIA NeMo Guardrails for input/output checking via Colang flows.
inject_rules() compiles DynamicRules into Colang, regenerates RailsConfig
in-memory via from_content(), and reloads LLMRails.
"""
import os
import structlog
from typing import Any, Dict, List, Optional

from app.guardrails.base import GuardrailsBackend, GuardrailsResult, DynamicRule
from app.config import settings

logger = structlog.get_logger()


class NemoGuardrailsBackend(GuardrailsBackend):
    """NeMo Guardrails backend using Colang flows."""

    def __init__(self):
        self.rails = None
        self.active_rules: List[DynamicRule] = []
        self._base_colang: str = ''
        self._base_yaml: str = ''

    async def initialize(self) -> None:
        """Initialize NeMo rails from profile directory."""
        try:
            from nemoguardrails import RailsConfig, LLMRails

            config_path = os.path.join(
                os.path.dirname(__file__),
                'rails_profiles',
                settings.guardrails_profile,
            )

            if not os.path.exists(config_path):
                logger.warning("NeMo rails profile not found, creating minimal", path=config_path)
                os.makedirs(config_path, exist_ok=True)
                self._create_minimal_config(config_path)

            # Read base files for later reuse in inject_rules
            yaml_path = os.path.join(config_path, 'config.yml')
            co_path = os.path.join(config_path, 'rails.co')

            with open(yaml_path, 'r') as f:
                self._base_yaml = f.read()
            with open(co_path, 'r') as f:
                self._base_colang = f.read()

            config = RailsConfig.from_path(config_path)
            self.rails = LLMRails(config)
            logger.info("NeMo guardrails backend initialized", profile=settings.guardrails_profile)

        except Exception as e:
            logger.warning("NeMo guardrails initialization failed, running in passthrough mode", error=str(e))
            self.rails = None

    def _parse_generation_response(self, response) -> Optional[str]:
        """Extract assistant content from GenerationResponse or dict."""
        # GenerationResponse (when options= is used)
        if hasattr(response, 'response'):
            msgs = response.response
            if isinstance(msgs, list):
                for m in msgs:
                    if isinstance(m, dict) and m.get('role') == 'assistant':
                        return m.get('content', '')
            elif isinstance(msgs, str):
                return msgs
            return None
        # Plain dict (no options)
        if isinstance(response, dict):
            return response.get('content')
        return None

    async def check_input(self, user_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        """Check input through NeMo input rails."""
        if self.rails is None:
            return GuardrailsResult()

        try:
            response = await self.rails.generate_async(
                messages=[{'role': 'user', 'content': user_message}],
                options={'rails': ['input']},
            )

            content = self._parse_generation_response(response)
            if content and content != user_message:
                # Rails modified/replaced the message — check for block/warn patterns
                is_block = 'Заблокировано правилом' in content
                is_warn = 'Предупреждение' in content or 'Обратите внимание' in content
                if is_block or is_warn:
                    return GuardrailsResult(
                        blocked=is_block,
                        reason=content,
                        severity='block' if is_block else 'warn',
                    )

            return GuardrailsResult()

        except Exception as e:
            logger.error("NeMo input check failed", exc_info=e)
            return GuardrailsResult()

    async def check_output(self, assistant_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        """Check output through NeMo output rails."""
        if self.rails is None:
            return GuardrailsResult()

        try:
            response = await self.rails.generate_async(
                messages=[
                    {'role': 'user', 'content': context.get('user_message', '')},
                    {'role': 'assistant', 'content': assistant_message},
                ],
                options={'rails': ['output']},
            )

            content = self._parse_generation_response(response)
            if content and content != assistant_message:
                is_block = 'Заблокировано правилом' in content
                is_warn = 'Предупреждение' in content or 'Обратите внимание' in content
                if is_block or is_warn:
                    return GuardrailsResult(
                        blocked=is_block,
                        reason=content,
                        severity='block' if is_block else 'warn',
                    )

            return GuardrailsResult()

        except Exception as e:
            logger.error("NeMo output check failed", exc_info=e)
            return GuardrailsResult()

    async def inject_rules(self, rules: List[DynamicRule]) -> None:
        """
        Inject dynamic rules by compiling them into Colang and reloading RailsConfig.

        Generates Colang flow definitions for each rule, appends them to the base
        rails.co, and recreates LLMRails with RailsConfig.from_content().
        """
        self.active_rules = rules

        if not rules:
            return

        try:
            from nemoguardrails import RailsConfig, LLMRails

            # Compile rules to Colang
            dynamic_colang = self._rules_to_colang(rules)
            full_colang = self._base_colang + '\n\n# === Dynamic Rules (auto-generated) ===\n' + dynamic_colang

            # Inject dynamic flow names into YAML input rails
            dynamic_yaml = self._inject_dynamic_flows_yaml(rules)

            logger.info(
                "Reloading NeMo with dynamic Colang rules",
                rule_count=len(rules),
                colang_lines=dynamic_colang.count('\n'),
            )

            config = RailsConfig.from_content(
                colang_content=full_colang,
                yaml_content=dynamic_yaml,
            )
            self.rails = LLMRails(config)

            logger.info("NeMo rails reloaded with dynamic rules", count=len(rules))

        except Exception as e:
            logger.error("Failed to reload NeMo with dynamic rules", exc_info=e)

    def _rules_to_colang(self, rules: List[DynamicRule]) -> str:
        """
        Convert DynamicRule list to Colang 1.0 flow definitions.

        Generates user intent patterns and subflows for block/warn/disclaimer rules.
        Uses NeMo's canonical message/bot patterns (no $variables, no pass).
        """
        flows = []
        for rule in rules:
            safe_id = rule.rule_id.replace('-', '_').replace('.', '_')
            desc_escaped = rule.description.replace('"', '\\"')

            if rule.rule_type == 'block':
                # Define a blocked response bot message
                flows.append(
                    f'define bot refuse {safe_id}\n'
                    f'  "Заблокировано правилом [{rule.rule_id}]: {desc_escaped}"\n'
                )
                # Define the input rail subflow
                flows.append(
                    f'define subflow check dynamic {safe_id}\n'
                    f'  # Domain: {rule.domain} | Severity: {rule.severity}\n'
                    f'  if user said something violating "{desc_escaped}"\n'
                    f'    bot refuse {safe_id}\n'
                    f'    stop\n'
                )
            elif rule.rule_type == 'warn':
                flows.append(
                    f'define bot warn {safe_id}\n'
                    f'  "Предупреждение [{rule.rule_id}]: {desc_escaped}"\n'
                )
                flows.append(
                    f'define subflow check dynamic {safe_id}\n'
                    f'  # Domain: {rule.domain} | Severity: {rule.severity}\n'
                    f'  if user said something violating "{desc_escaped}"\n'
                    f'    bot warn {safe_id}\n'
                )
            elif rule.rule_type == 'require_disclaimer':
                flows.append(
                    f'define bot disclaimer {safe_id}\n'
                    f'  "Обратите внимание: {desc_escaped}"\n'
                )
                flows.append(
                    f'define subflow check dynamic {safe_id}\n'
                    f'  # Domain: {rule.domain} | Severity: {rule.severity}\n'
                    f'  bot disclaimer {safe_id}\n'
                )

        return '\n\n'.join(flows)

    def _inject_dynamic_flows_yaml(self, rules: List[DynamicRule]) -> str:
        """
        Add dynamic flow names to the YAML config's input rails section.

        Parses the base YAML and appends dynamic flow names under rails.input.flows.
        """
        dynamic_flow_names = []
        for rule in rules:
            safe_id = rule.rule_id.replace('-', '_').replace('.', '_')
            dynamic_flow_names.append(f'      - check dynamic {safe_id}')

        if not dynamic_flow_names:
            return self._base_yaml

        flows_block = '\n'.join(dynamic_flow_names)
        yaml = self._base_yaml

        if 'rails:' in yaml:
            # rails: section exists — inject into input.flows
            if 'input:' in yaml and 'flows:' in yaml:
                # Append to existing flows list
                yaml = yaml.rstrip() + '\n' + flows_block + '\n'
            elif 'output:' in yaml:
                yaml = yaml.replace(
                    '\n  output:',
                    '\n  input:\n    flows:\n' + flows_block + '\n\n  output:',
                )
            else:
                yaml = yaml.rstrip() + '\n  input:\n    flows:\n' + flows_block + '\n'
        else:
            # No rails: section — add complete section
            yaml = yaml.rstrip() + '\n\nrails:\n  input:\n    flows:\n' + flows_block + '\n'

        return yaml

    def _create_minimal_config(self, config_path: str):
        """Create minimal NeMo config."""
        model = settings.llm_model or 'gpt-4o'

        config_yml = f"""models:
  - type: main
    engine: openai
    model: {model}

instructions:
  - type: general
    content: |
      Ты — полезный ИИ-ассистент.
      Отвечай на русском языке.
"""
        rails_co = """define flow main
  user ...
  bot respond
"""
        with open(os.path.join(config_path, 'config.yml'), 'w') as f:
            f.write(config_yml)
        with open(os.path.join(config_path, 'rails.co'), 'w') as f:
            f.write(rails_co)
