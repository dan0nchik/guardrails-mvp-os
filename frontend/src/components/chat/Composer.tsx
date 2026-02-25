/**
 * Message composer (input + send)
 */

import { useState } from 'react';
import { Textarea, Button, Group, ActionIcon } from '@mantine/core';
import { IconSend, IconX } from '@tabler/icons-react';

interface ComposerProps {
  onSend: (message: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  isSending?: boolean;
}

export function Composer({ onSend, onCancel, disabled, isSending }: ComposerProps) {
  const [value, setValue] = useState('');

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Group align="flex-end" gap="xs" style={{ padding: '1rem' }}>
      <Textarea
        placeholder="Введите сообщение... (Enter — отправить, Shift+Enter — новая строка)"
        value={value}
        onChange={(e) => setValue(e.currentTarget.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        minRows={1}
        maxRows={6}
        autosize
        style={{ flex: 1 }}
      />

      {isSending && onCancel ? (
        <ActionIcon
          size="lg"
          color="red"
          onClick={onCancel}
          title="Остановить генерацию"
        >
          <IconX size={20} />
        </ActionIcon>
      ) : (
        <Button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          leftSection={<IconSend size={18} />}
        >
          Отправить
        </Button>
      )}
    </Group>
  );
}
