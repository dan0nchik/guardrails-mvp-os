/**
 * Main guardrails toggle (enable all/disable all)
 */

import { Switch, Stack, Text, Group, Badge } from '@mantine/core';
import { IconShield, IconShieldOff } from '@tabler/icons-react';
import { useGuardrailsStore } from '@/store/guardrailsStore';

export function GuardrailsToggleAll() {
  const { config, setEnabled, setMonitorOnly } = useGuardrailsStore();

  return (
    <Stack gap="xs" p="md" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
      <Group justify="space-between">
        <Group gap="xs">
          {config.enabled ? (
            <IconShield size={20} color="var(--mantine-color-blue-6)" />
          ) : (
            <IconShieldOff size={20} color="var(--mantine-color-gray-5)" />
          )}
          <Text fw={600}>Защитные барьеры</Text>
          {config.enabled && (
            <Badge size="xs" color={config.monitorOnly ? 'yellow' : 'blue'}>
              {config.monitorOnly ? 'Мониторинг' : 'Блокировка'}
            </Badge>
          )}
        </Group>

        <Switch
          checked={config.enabled}
          onChange={(e) => setEnabled(e.currentTarget.checked)}
          color="blue"
        />
      </Group>

      {config.enabled && (
        <Switch
          label="Режим мониторинга (логировать, но не блокировать)"
          checked={config.monitorOnly}
          onChange={(e) => setMonitorOnly(e.currentTarget.checked)}
          size="xs"
          color="yellow"
        />
      )}

      <Text size="xs" c="dimmed">
        {config.enabled
          ? config.monitorOnly
            ? 'Все барьеры активны в режиме мониторинга — нарушения логируются, но не блокируются'
            : 'Все барьеры активны и применяют политики'
          : 'Все защитные барьеры отключены'}
      </Text>
    </Stack>
  );
}
