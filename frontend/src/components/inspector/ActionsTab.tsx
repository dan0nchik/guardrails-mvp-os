/**
 * Actions tab - shows tool calls and agent steps
 */

import { Stack, Text, Badge, Group, Code, Accordion } from '@mantine/core';
import { IconTool, IconCheck, IconX, IconClock } from '@tabler/icons-react';
import type { Message } from '@/types';

interface ActionsTabProps {
  message: Message | null;
}

export function ActionsTab({ message }: ActionsTabProps) {
  if (!message) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Выберите сообщение для инспектирования</Text>
      </Stack>
    );
  }

  const toolCalls = message.toolCalls || [];

  if (toolCalls.length === 0) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Нет вызовов инструментов в этом сообщении</Text>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Text size="sm" fw={500}>
        Вызовы инструментов ({toolCalls.length})
      </Text>

      <Accordion variant="separated">
        {toolCalls.map((call, idx) => {
          // Ensure unique value for Accordion.Item - use index as fallback
          const itemValue = call.id || `tool-call-${idx}`;
          const displayId = call.id || 'N/A';

          return (
            <Accordion.Item key={itemValue} value={itemValue}>
              <Accordion.Control>
                <Group gap="xs">
                  <IconTool size={16} />
                  <Text size="sm" fw={500}>
                    {call.tool || 'Неизвестный инструмент'}
                  </Text>
                  <Badge
                    size="sm"
                    color={call.status === 'ok' ? 'green' : 'red'}
                    leftSection={call.status === 'ok' ? <IconCheck size={12} /> : <IconX size={12} />}
                  >
                    {call.status || 'unknown'}
                  </Badge>
                  {call.latencyMs && (
                    <Badge size="sm" variant="light" leftSection={<IconClock size={12} />}>
                      {call.latencyMs}ms
                    </Badge>
                  )}
                </Group>
              </Accordion.Control>

              <Accordion.Panel>
                <Stack gap="xs">
                  <div>
                    <Text size="xs" fw={500} c="dimmed" mb={4}>
                      TOOL_CALL_ID
                    </Text>
                    <Code block>{displayId}</Code>
                  </div>

                  <div>
                    <Text size="xs" fw={500} c="dimmed" mb={4}>
                      Аргументы
                    </Text>
                    <Code block>{JSON.stringify(call.args || {}, null, 2)}</Code>
                  </div>

                  {call.result != null && (
                    <div>
                      <Text size="xs" fw={500} c="dimmed" mb={4}>
                        Результат (превью)
                      </Text>
                      <Code block>
                        {typeof call.result === 'string'
                          ? (call.result as string).slice(0, 200)
                          : JSON.stringify(call.result, null, 2).slice(0, 200)}
                        {JSON.stringify(call.result).length > 200 ? '\n...' : ''}
                      </Code>
                    </div>
                  )}

                  {call.error && (
                    <div>
                      <Text size="xs" fw={500} c="red" mb={4}>
                        Ошибка
                      </Text>
                      <Code block color="red">
                        {call.error}
                      </Code>
                    </div>
                  )}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          );
        })}
      </Accordion>
    </Stack>
  );
}
