/**
 * Dynamic Rules tab — shows LLM-generated guardrail rules
 */

import { Stack, Text, Paper, Code, Badge, Group, Collapse, Button } from '@mantine/core';
import { useState } from 'react';
import type { Message, DynamicRuleDetail } from '@/types';

interface GeneratedRailsTabProps {
  message: Message | null;
}

const SEVERITY_COLORS: Record<string, string> = {
  low: 'blue',
  medium: 'yellow',
  high: 'orange',
  critical: 'red',
};

const RULE_TYPE_LABELS: Record<string, string> = {
  block: 'Блокировка',
  warn: 'Предупреждение',
  require_disclaimer: 'Дисклеймер',
  restrict_tool: 'Ограничение инструмента',
};

function RuleCard({ rule, isNew }: { rule: DynamicRuleDetail; isNew: boolean }) {
  const severityColor = SEVERITY_COLORS[rule.severity] || 'gray';
  const typeLabel = RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type;

  return (
    <Paper
      p="sm"
      withBorder
      style={{
        borderLeft: isNew ? '3px solid var(--mantine-color-green-6)' : undefined,
        backgroundColor: isNew ? 'var(--mantine-color-green-0)' : undefined,
      }}
    >
      <Group justify="space-between" mb={4}>
        <Group gap="xs">
          <Badge size="xs" variant="light" color={severityColor}>
            {rule.severity}
          </Badge>
          <Badge size="xs" variant="outline">
            {typeLabel}
          </Badge>
          {rule.domain && (
            <Badge size="xs" variant="dot" color="violet">
              {rule.domain}
            </Badge>
          )}
          {isNew && (
            <Badge size="xs" color="green">
              НОВОЕ
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">{rule.rule_id}</Text>
      </Group>
      <Text size="sm">{rule.description}</Text>
    </Paper>
  );
}

export function GeneratedRailsTab({ message }: GeneratedRailsTabProps) {
  const [showConfig, setShowConfig] = useState(false);

  if (!message) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Выберите сообщение для инспектирования</Text>
      </Stack>
    );
  }

  const generatedRails = message.generatedRails;

  if (!generatedRails) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Нет динамических правил для этого сообщения</Text>
      </Stack>
    );
  }

  const rules = generatedRails.rules || [];
  const newRules = generatedRails.new_rules || [];
  const newRuleIds = new Set(newRules.map((r) => r.rule_id));

  return (
    <Stack gap="md">
      {/* Summary */}
      <Paper p="md" withBorder>
        <Group justify="space-between" mb="xs">
          <Text size="sm" fw={500}>Динамические правила</Text>
          <Group gap="xs">
            <Badge size="sm" variant="light">{rules.length} активных</Badge>
            {newRules.length > 0 && (
              <Badge size="sm" color="green">{newRules.length} новых</Badge>
            )}
          </Group>
        </Group>
        <Text size="sm" c="dimmed">{generatedRails.summary}</Text>
      </Paper>

      {/* New rules (highlighted) */}
      {newRules.length > 0 && (
        <div>
          <Text size="sm" fw={500} mb="xs" c="green">
            Новые правила (этот ход)
          </Text>
          <Stack gap="xs">
            {newRules.map((rule) => (
              <RuleCard key={rule.rule_id} rule={rule} isNew />
            ))}
          </Stack>
        </div>
      )}

      {/* All active rules */}
      {rules.length > 0 && (
        <div>
          <Text size="sm" fw={500} mb="xs">
            Все активные правила
          </Text>
          <Stack gap="xs">
            {rules.map((rule) => (
              <RuleCard
                key={rule.rule_id}
                rule={rule}
                isNew={newRuleIds.has(rule.rule_id)}
              />
            ))}
          </Stack>
        </div>
      )}

      {/* YAML config (collapsible) */}
      {generatedRails.config && (
        <div>
          <Button
            variant="subtle"
            size="xs"
            onClick={() => setShowConfig(!showConfig)}
          >
            {showConfig ? 'Скрыть конфигурацию' : 'Показать конфигурацию'}
          </Button>
          <Collapse in={showConfig}>
            <Code block style={{ maxHeight: 300, overflow: 'auto', marginTop: 8 }}>
              {generatedRails.config}
            </Code>
          </Collapse>
        </div>
      )}

      <Text size="xs" c="dimmed">
        Правила генерируются LLM-классификатором на основе темы разговора и накапливаются в сессии.
      </Text>
    </Stack>
  );
}
