"""
Dynamic Rails Builder.

Генератор профилей guardrails "под агента" на основе:
- Tool registry (какие инструменты доступны)
- Domain policy (что можно/нельзя)
- Output contract (формат ответа)

В MVP: статическая генерация при деплое/старте.
"""
import os
from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger()


class RailsProfileBuilder:
    """Builder для динамических rails profiles."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def build_profile(
        self,
        profile_name: str,
        tools: List[Dict[str, Any]],
        domain_policy: str,
        output_contract: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build a rails profile.

        Args:
            profile_name: Name of profile (e.g., "customer_service", "data_analyst")
            tools: List of tool definitions
            domain_policy: Policy text (what's allowed/forbidden)
            output_contract: Optional schema for output format

        Returns:
            Path to generated profile directory
        """
        logger.info("Building rails profile", profile_name=profile_name)

        profile_dir = os.path.join(self.output_dir, profile_name)
        os.makedirs(profile_dir, exist_ok=True)

        # Generate config.yml
        config = self._generate_config(tools, domain_policy, output_contract)
        with open(os.path.join(profile_dir, 'config.yml'), 'w') as f:
            f.write(config)

        # Generate rails.co (Colang flows)
        rails = self._generate_rails(tools, domain_policy, output_contract)
        with open(os.path.join(profile_dir, 'rails.co'), 'w') as f:
            f.write(rails)

        logger.info("Rails profile built", profile_name=profile_name, path=profile_dir)
        return profile_dir

    def _generate_config(
        self,
        tools: List[Dict[str, Any]],
        domain_policy: str,
        output_contract: Optional[Dict[str, Any]]
    ) -> str:
        """Generate config.yml content."""
        tool_list = "\n".join(
            f"      - {tool['name']}: {tool.get('description', '')}"
            for tool in tools
        )

        config = f"""
# Auto-generated NeMo Guardrails config
models:
  - type: main
    engine: openai
    model: gpt-4

instructions:
  - type: general
    content: |
      You are a helpful AI assistant with access to the following tools:
{tool_list}

      Domain Policy:
      {domain_policy}

      IMPORTANT: When referencing tool results, always include the TOOL_CALL_ID.
      Format: "Based on <tool_name> (TOOL_CALL_ID: <id>), ..."

rails:
  input:
    flows:
      - check input length
      - check pii input
      - check jailbreak

  output:
    flows:
      - check tool references
      - check pii output
      - check output format

  execution:
    flows:
      - enforce tool policy
"""

        if output_contract:
            config += f"\noutput_contract:\n{self._format_contract(output_contract)}"

        return config

    def _generate_rails(
        self,
        tools: List[Dict[str, Any]],
        domain_policy: str,
        output_contract: Optional[Dict[str, Any]]
    ) -> str:
        """Generate rails.co (Colang flows) content."""

        allowed_tools = "\n  ".join(f'"{tool["name"]}"' for tool in tools)

        rails = f"""
# Auto-generated Colang flows

# Input Rails
define flow check input length
  """Enforce max input length"""
  if len($user_message) > 10000
    bot refuse "Input too long"
    stop

define flow check pii input
  """Check for PII in user input"""
  # TODO: Implement PII detection (regex or ML model)
  pass

define flow check jailbreak
  """Detect prompt injection attempts"""
  $patterns = ["ignore previous", "system:", "developer mode"]
  for $pattern in $patterns
    if $pattern in $user_message.lower()
      bot refuse "Invalid request detected"
      stop

# Execution Rails
define flow enforce tool policy
  """Ensure only allowed tools are called"""
  $allowed_tools = [
  {allowed_tools}
  ]

  if $tool_name not in $allowed_tools
    bot refuse "Tool not allowed: {{$tool_name}}"
    stop

# Output Rails
define flow check tool references
  """Verify TOOL_CALL_ID references in output"""
  # If bot mentions a tool result, it MUST include TOOL_CALL_ID

  if "based on" in $bot_message.lower() and "TOOL_CALL_ID" not in $bot_message
    # Trigger regeneration
    bot regenerate with instruction "Include TOOL_CALL_ID when referencing tool results"
    stop

define flow check pii output
  """Check for PII leakage in output"""
  # TODO: Implement PII scan
  pass

define flow check output format
  """Validate output format if contract is defined"""
  # TODO: Validate against JSON schema if output_contract is set
  pass

# Main flow
define flow main
  user $user_message
  $result = execute run_agent
  bot $result.assistant_message

# Refusal flow
define bot refuse $reason
  "I cannot help with that request. Reason: {{$reason}}"
"""

        return rails

    def _format_contract(self, contract: Dict[str, Any]) -> str:
        """Format output contract as YAML."""
        # Simple YAML formatter for MVP
        lines = []
        for key, value in contract.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)


def create_default_profiles(builder: RailsProfileBuilder, tool_registry):
    """Create default rails profiles for MVP."""

    # Profile 1: General Assistant
    tools = tool_registry.to_claude_format()

    builder.build_profile(
        profile_name='default',
        tools=tools,
        domain_policy="""
        - Be helpful and honest
        - Always reference TOOL_CALL_ID when mentioning tool results
        - Do not make up information
        - If uncertain, say so
        """,
        output_contract=None
    )

    # Profile 2: Data Analyst (только read-only tools)
    analyst_tools = [
        t for t in tools
        if t['name'] in ['read_file', 'list_directory', 'calculate', 'web_search']
    ]

    builder.build_profile(
        profile_name='data_analyst',
        tools=analyst_tools,
        domain_policy="""
        - Provide data analysis and insights
        - Only use read-only database operations
        - Include TOOL_CALL_ID in all data references
        - Cite sources for all claims
        """,
        output_contract={
            'format': 'structured',
            'required_fields': ['analysis', 'sources']
        }
    )

    logger.info("Default profiles created")
