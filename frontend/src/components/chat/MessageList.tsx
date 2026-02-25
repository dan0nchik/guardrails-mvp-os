/**
 * Message list component with auto-scroll
 */

import { useEffect, useRef } from 'react';
import { Stack, Center, Text, Loader } from '@mantine/core';
import type { Message } from '@/types';
import { MessageBubble } from './MessageBubble';

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  if (messages.length === 0 && !isLoading) {
    return (
      <Center h="100%" style={{ flexDirection: 'column' }}>
        <Text size="lg" c="dimmed" mb="xs">
          Сообщений пока нет
        </Text>
        <Text size="sm" c="dimmed">
          Начните разговор с ИИ-ассистентом
        </Text>
      </Center>
    );
  }

  return (
    <Stack gap="md" style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {isLoading && (
        <Center>
          <Loader size="sm" />
        </Center>
      )}

      <div ref={bottomRef} />
    </Stack>
  );
}
