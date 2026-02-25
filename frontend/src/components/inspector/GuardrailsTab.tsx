/**
 * Guardrails tab - shows which rails were active/inactive
 */

import { Stack, Text, Paper, Badge, Group } from '@mantine/core';
import { IconShield, IconShieldOff } from '@tabler/icons-react';
import type { Message } from '@/types';
import { useGuardrailsStore } from '@/store/guardrailsStore';

interface GuardrailsTabProps {
  message: Message | null;
}

export function GuardrailsTab({ message }: GuardrailsTabProps) {
  const { config } = useGuardrailsStore();

  if (!message) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Выберите сообщение для инспектирования</Text>
      </Stack>
    );
  }

  const activeRails = Object.entries(config.toggles).filter(([_, enabled]) => enabled);
  const inactiveRails = Object.entries(config.toggles).filter(([_, enabled]) => !enabled);

  return (
    <Stack gap="md">
      <div>
        <Group mb="xs">
          <IconShield size={16} color="var(--mantine-color-blue-6)" />
          <Text size="sm" fw={500}>
            Активные барьеры ({activeRails.length})
          </Text>
        </Group>

        <Stack gap="xs">
          {activeRails.map(([key]) => (
            <Paper key={key} p="xs" withBorder>
              <Group justify="space-between">
                <Text size="sm">{key}</Text>
                <Badge size="sm" color="green">
                  Активен
                </Badge>
              </Group>
            </Paper>
          ))}
        </Stack>
      </div>

      {inactiveRails.length > 0 && (
        <div>
          <Group mb="xs">
            <IconShieldOff size={16} color="var(--mantine-color-gray-5)" />
            <Text size="sm" fw={500} c="dimmed">
              Неактивные барьеры ({inactiveRails.length})
            </Text>
          </Group>

          <Stack gap="xs">
            {inactiveRails.map(([key]) => (
              <Paper key={key} p="xs" withBorder style={{ opacity: 0.5 }}>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">
                    {key}
                  </Text>
                  <Badge size="sm" color="gray">
                    Неактивен
                  </Badge>
                </Group>
              </Paper>
            ))}
          </Stack>
        </div>
      )}

      <Paper p="md" withBorder>
        <Text size="xs" c="dimmed">
          Режим: {config.enabled ? (config.monitorOnly ? 'Только мониторинг' : 'Блокировка') : 'Отключено'}
        </Text>
        {message.traceId && (
          <Text size="xs" c="dimmed" mt="xs">
            ID трассировки: {message.traceId}
          </Text>
        )}
      </Paper>
    </Stack>
  );
}
