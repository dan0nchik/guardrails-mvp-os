/**
 * Type definitions for Guardrails MVP UI
 */

export type MessageRole = 'user' | 'assistant' | 'system';

export type MessageStatus = 'sending' | 'ok' | 'refused' | 'regenerated' | 'blocked' | 'error' | 'cancelled';

export interface Message {
  id: string;
  sessionId: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  traceId?: string;
  createdAt: number;
  railEvents?: RailEvent[];
  toolCalls?: ToolCall[];
  generatedRails?: GeneratedRails;
}

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

export interface GuardrailsConfig {
  enabled: boolean;
  monitorOnly: boolean;
  toggles: {
    'input.pii': boolean;
    'input.injection': boolean;
    'input.policy': boolean;
    'input.length': boolean;
    'exec.tool_allowlist': boolean;
    'exec.arg_validation': boolean;
    'exec.rate_limit': boolean;
    'exec.loop_detection': boolean;
    'output.format': boolean;
    'output.pii': boolean;
    'output.tool_truth': boolean;
    'output.safety': boolean;
    'hallucination.judge': boolean;
  };
}

export type RailStage = 'input' | 'execution' | 'output';
export type RailSeverity = 'info' | 'warn' | 'block';

export interface RailEvent {
  railName: string;
  stage: RailStage;
  severity: RailSeverity;
  reason: string;
  details?: {
    snippet?: string;
    before?: string;
    after?: string;
    [key: string]: unknown;
  };
}

export interface ToolCall {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  status: 'ok' | 'error';
  latencyMs?: number;
  result?: unknown;
  error?: string;
}

export interface DynamicRuleDetail {
  rule_id: string;
  domain: string;
  rule_type: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface GeneratedRails {
  profileId: string;
  summary: string;
  config?: string;
  rules?: DynamicRuleDetail[];
  new_rules?: DynamicRuleDetail[];
}

export interface RuntimeConfig {
  guardrails_backend: 'langchain' | 'nemo' | 'none';
  llm_provider: string;
  llm_model: string;
  available_backends: string[];
  available_providers: Array<{ id: string; models: string[] }>;
}

// API Request/Response types

export interface ChatRequest {
  session_id: string;
  user_message: string;
  agent_profile?: string;
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  guardrails?: {
    enabled: boolean;
    monitor_only: boolean;
    toggles: Record<string, boolean>;
  };
}

export interface ChatResponse {
  session_id: string;
  message_id?: string;
  assistant_message: string;
  status: 'ok' | 'refused' | 'escalated';
  trace_id: string;
  tool_calls?: ToolCall[];
  rail_events?: RailEvent[];
  generated_rails?: GeneratedRails;
}

export interface InspectorData {
  messageId: string;
  railEvents: RailEvent[];
  toolCalls: ToolCall[];
  generatedRails?: GeneratedRails;
  blockedEdits: Array<{
    type: string;
    before: string;
    after: string;
    reason: string;
  }>;
}
