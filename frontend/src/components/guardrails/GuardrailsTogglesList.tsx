/**
 * Individual guardrails toggles list
 */

import { Stack, Switch, Text, Tooltip, ActionIcon, Group, Button } from '@mantine/core';
import { IconInfoCircle, IconRefresh } from '@tabler/icons-react';
import { useGuardrailsStore } from '@/store/guardrailsStore';
import type { GuardrailsConfig } from '@/types';

const RAIL_DESCRIPTIONS: Record<keyof GuardrailsConfig['toggles'], { label: string; description: string; category: string }> = {
  'input.pii': {
    label: 'Обнаружение ПДн',
    description: 'Обнаружение и маскирование персональных данных во вводе пользователя',
    category: 'Входные барьеры',
  },
  'input.injection': {
    label: 'Защита от инъекций',
    description: 'Обнаружение попыток инъекций в промпт и взлома (jailbreak)',
    category: 'Входные барьеры',
  },
  'input.policy': {
    label: 'Проверка политик',
    description: 'Валидация ввода по доменным политикам',
    category: 'Входные барьеры',
  },
  'input.length': {
    label: 'Валидация длины',
    description: 'Ограничение максимальной длины ввода',
    category: 'Входные барьеры',
  },
  'exec.tool_allowlist': {
    label: 'Белый список инструментов',
    description: 'Ограничение доступных для вызова инструментов',
    category: 'Барьеры выполнения',
  },
  'exec.arg_validation': {
    label: 'Валидация аргументов',
    description: 'Проверка аргументов вызовов инструментов по схемам',
    category: 'Барьеры выполнения',
  },
  'exec.rate_limit': {
    label: 'Ограничение частоты',
    description: 'Ограничение количества вызовов инструментов на запрос/сессию',
    category: 'Барьеры выполнения',
  },
  'exec.loop_detection': {
    label: 'Обнаружение циклов',
    description: 'Обнаружение и прерывание бесконечных циклов вызовов инструментов',
    category: 'Барьеры выполнения',
  },
  'output.format': {
    label: 'Валидация формата',
    description: 'Проверка формата и структуры выходных данных',
    category: 'Выходные барьеры',
  },
  'output.pii': {
    label: 'Утечка ПДн',
    description: 'Предотвращение утечки персональных данных в ответах ассистента',
    category: 'Выходные барьеры',
  },
  'output.tool_truth': {
    label: 'Достоверность инструментов',
    description: 'Проверка наличия TOOL_CALL_ID в ссылках на вызовы инструментов',
    category: 'Выходные барьеры',
  },
  'output.safety': {
    label: 'Проверка безопасности',
    description: 'Общая проверка безопасности и соответствия политикам',
    category: 'Выходные барьеры',
  },
  'hallucination.judge': {
    label: 'Детектор галлюцинаций',
    description: 'Обнаружение фактических галлюцинаций в ответах',
    category: 'Продвинутые',
  },
};

const CATEGORIES = ['Входные барьеры', 'Барьеры выполнения', 'Выходные барьеры', 'Продвинутые'];

export function GuardrailsTogglesList() {
  const { config, toggleRail, resetToDefault } = useGuardrailsStore();

  const railsByCategory = CATEGORIES.map((category) => ({
    category,
    rails: Object.entries(RAIL_DESCRIPTIONS).filter(
      ([_, info]) => info.category === category
    ),
  }));

  return (
    <Stack gap="lg" p="md">
      <Group justify="space-between">
        <Text size="sm" fw={500}>
          Индивидуальные настройки
        </Text>
        <Button
          size="xs"
          variant="subtle"
          leftSection={<IconRefresh size={14} />}
          onClick={resetToDefault}
        >
          Сбросить
        </Button>
      </Group>

      {railsByCategory.map(({ category, rails }) => (
        <Stack key={category} gap="xs">
          <Text size="xs" fw={600} c="dimmed" tt="uppercase">
            {category}
          </Text>

          {rails.map(([key, info]) => (
            <Group key={key} justify="space-between" wrap="nowrap">
              <Group gap="xs" style={{ flex: 1, minWidth: 0 }}>
                <Switch
                  checked={config.toggles[key as keyof GuardrailsConfig['toggles']]}
                  onChange={() => toggleRail(key as keyof GuardrailsConfig['toggles'])}
                  disabled={!config.enabled}
                  size="xs"
                />
                <Text
                  size="sm"
                  style={{
                    opacity: !config.enabled ? 0.5 : 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {info.label}
                </Text>
              </Group>

              <Tooltip label={info.description} position="left" withArrow>
                <ActionIcon variant="subtle" size="xs">
                  <IconInfoCircle size={14} />
                </ActionIcon>
              </Tooltip>
            </Group>
          ))}
        </Stack>
      ))}
    </Stack>
  );
}
