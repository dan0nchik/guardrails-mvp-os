/**
 * Message bubble component
 */

import { Paper, Text, Badge, Group } from '@mantine/core';
import { IconShield, IconShieldOff, IconAlertTriangle, IconRefresh } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '@/types';
import { useInspectorStore } from '@/store/inspectorStore';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const { selectedMessageId, setSelectedMessage } = useInspectorStore();
  const isSelected = selectedMessageId === message.id;
  const isUser = message.role === 'user';

  const getStatusBadge = () => {
    switch (message.status) {
      case 'refused':
        return <Badge color="red" leftSection={<IconShieldOff size={12} />}>Отклонено</Badge>;
      case 'blocked':
        return <Badge color="orange" leftSection={<IconShield size={12} />}>Заблокировано</Badge>;
      case 'regenerated':
        return <Badge color="yellow" leftSection={<IconRefresh size={12} />}>Перегенерировано</Badge>;
      case 'error':
        return <Badge color="red" leftSection={<IconAlertTriangle size={12} />}>Ошибка</Badge>;
      case 'sending':
        return <Badge color="gray">Отправка...</Badge>;
      default:
        return null;
    }
  };

  const hasRailEvents = message.railEvents && message.railEvents.length > 0;

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '1rem',
      }}
    >
      <Paper
        p="md"
        shadow={isSelected ? 'md' : 'xs'}
        withBorder
        onClick={() => setSelectedMessage(message.id)}
        style={{
          maxWidth: '70%',
          cursor: 'pointer',
          backgroundColor: isUser
            ? 'var(--mantine-color-blue-0)'
            : isSelected
            ? 'var(--mantine-color-gray-0)'
            : undefined,
          borderColor: isSelected ? 'var(--mantine-color-blue-5)' : undefined,
          borderWidth: isSelected ? 2 : 1,
        }}
      >
        <Group mb="xs" gap="xs">
          <Text size="sm" fw={500} c="dimmed">
            {isUser ? 'Вы' : 'Ассистент'}
          </Text>
          {getStatusBadge()}
          {hasRailEvents && (
            <Badge color="blue" variant="light" size="xs">
              {message.railEvents!.length} событ.барьеров
            </Badge>
          )}
        </Group>

        {isUser ? (
          <Text>{message.content}</Text>
        ) : (
          <div>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {message.traceId && (
          <Text size="xs" c="dimmed" mt="xs">
            Трассировка: {message.traceId}
          </Text>
        )}
      </Paper>
    </div>
  );
}
