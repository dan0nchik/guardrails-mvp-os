/**
 * Main chat view component
 */

import { useState, useRef } from 'react';
import { Stack, Alert } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle } from '@tabler/icons-react';
import { MessageList } from './MessageList';
import { Composer } from './Composer';
import { useSessionsStore } from '@/store/sessionsStore';
import { useGuardrailsStore } from '@/store/guardrailsStore';
import { api } from '@/api/client';
import type { Message } from '@/types';

export function ChatView() {
  const { currentSessionId, getCurrentMessages, addMessage, updateMessage } = useSessionsStore();
  const { config } = useGuardrailsStore();
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const messages = getCurrentMessages();

  const handleSend = async (content: string) => {
    if (!currentSessionId) {
      notifications.show({
        title: 'Ошибка',
        message: 'Сессия не выбрана',
        color: 'red',
      });
      return;
    }

    setError(null);
    setIsSending(true);

    // Create user message
    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      sessionId: currentSessionId,
      role: 'user',
      content,
      status: 'ok',
      createdAt: Date.now(),
    };

    addMessage(userMessage);

    // Create assistant message placeholder
    const assistantMessageId = `msg_${Date.now()}_assistant`;
    const assistantMessage: Message = {
      id: assistantMessageId,
      sessionId: currentSessionId,
      role: 'assistant',
      content: '',
      status: 'sending',
      createdAt: Date.now(),
    };

    addMessage(assistantMessage);

    // Call API
    abortControllerRef.current = new AbortController();

    try {
      // Build conversation history from previous messages (excluding the placeholder)
      const history = messages
        .filter((m) => m.status === 'ok' && (m.role === 'user' || m.role === 'assistant') && m.content)
        .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));

      const response = await api.chat(
        {
          session_id: currentSessionId,
          user_message: content,
          agent_profile: 'default',
          history,
          guardrails: config.enabled
            ? {
                enabled: true,
                monitor_only: config.monitorOnly,
                toggles: Object.fromEntries(
                  Object.entries(config.toggles).map(([k, v]) => [k, v])
                ),
              }
            : undefined,
        },
        abortControllerRef.current.signal
      );

      // Update assistant message with response
      updateMessage(currentSessionId, assistantMessageId, {
        content: response.assistant_message,
        status: response.status === 'ok' ? 'ok' : response.status === 'refused' ? 'refused' : 'ok',
        traceId: response.trace_id,
        railEvents: response.rail_events,
        toolCalls: response.tool_calls,
        generatedRails: response.generated_rails,
      });

      if (response.status === 'refused') {
        notifications.show({
          title: 'Запрос отклонён',
          message: 'Запрос был отклонён защитными барьерами',
          color: 'orange',
        });
      }
    } catch (err: any) {
      const errorMessage = err.message || 'Не удалось отправить сообщение';

      if (err.message === 'Request cancelled') {
        updateMessage(currentSessionId, assistantMessageId, {
          status: 'cancelled',
          content: 'Запрос отменён',
        });
      } else {
        updateMessage(currentSessionId, assistantMessageId, {
          status: 'error',
          content: `Ошибка: ${errorMessage}`,
        });

        setError(errorMessage);
        notifications.show({
          title: 'Ошибка',
          message: errorMessage,
          color: 'red',
        });
      }
    } finally {
      setIsSending(false);
      abortControllerRef.current = null;
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  return (
    <Stack h="100%" gap={0}>
      {error && (
        <Alert
          icon={<IconAlertCircle size={16} />}
          title="Ошибка"
          color="red"
          withCloseButton
          onClose={() => setError(null)}
          mb="md"
        >
          {error}
        </Alert>
      )}

      <MessageList messages={messages} isLoading={isSending} />

      <Composer
        onSend={handleSend}
        onCancel={handleCancel}
        disabled={!currentSessionId}
        isSending={isSending}
      />
    </Stack>
  );
}
