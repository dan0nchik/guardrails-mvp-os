/**
 * Runtime settings — switch guardrails backend & LLM model from UI
 */

import { useEffect } from 'react';
import { Select, Stack, Text, Loader, Group, Alert } from '@mantine/core';
import { useSettingsStore } from '@/store/settingsStore';

export function RuntimeSettings() {
  const config = useSettingsStore((s) => s.config);
  const loading = useSettingsStore((s) => s.loading);
  const error = useSettingsStore((s) => s.error);
  const fetchConfig = useSettingsStore((s) => s.fetchConfig);
  const setBackend = useSettingsStore((s) => s.setBackend);
  const setLLM = useSettingsStore((s) => s.setLLM);

  useEffect(() => {
    fetchConfig();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!config) {
    return (
      <Stack gap="xs" p="md">
        <Text size="sm" fw={600}>Runtime Settings</Text>
        {loading && <Loader size="sm" />}
        {error && <Alert color="red" variant="light" p="xs">{error}</Alert>}
      </Stack>
    );
  }

  const currentProvider = config.available_providers.find(p => p.id === config.llm_provider);
  const modelOptions = currentProvider?.models.map(m => ({ value: m, label: m })) ?? [];

  return (
    <Stack gap="xs" p="md">
      <Group gap="xs">
        <Text size="sm" fw={600}>Runtime Settings</Text>
        {loading && <Loader size={14} />}
      </Group>

      <Select
        label="Guardrails Backend"
        size="xs"
        data={config.available_backends.map(b => ({ value: b, label: b }))}
        value={config.guardrails_backend}
        onChange={(val) => val && setBackend(val as typeof config.guardrails_backend)}
        disabled={loading}
        allowDeselect={false}
      />

      <Select
        label="LLM Model"
        size="xs"
        data={modelOptions}
        value={config.llm_model}
        onChange={(val) => val && setLLM(config.llm_provider, val)}
        disabled={loading}
        allowDeselect={false}
      />
    </Stack>
  );
}
