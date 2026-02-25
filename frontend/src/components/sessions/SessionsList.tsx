/**
 * Sessions list component
 */

import { ActionIcon, Button, Group, Menu, Stack, Text, TextInput } from '@mantine/core';
import { IconPlus, IconTrash, IconEdit, IconDots } from '@tabler/icons-react';
import { useState } from 'react';
import { useSessionsStore } from '@/store/sessionsStore';
import { format } from 'date-fns';

export function SessionsList() {
  const {
    sessions,
    currentSessionId,
    createSession,
    deleteSession,
    renameSession,
    setCurrentSession,
  } = useSessionsStore();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleRename = (sessionId: string, currentTitle: string) => {
    setEditingId(sessionId);
    setEditValue(currentTitle);
  };

  const handleSaveRename = (sessionId: string) => {
    if (editValue.trim()) {
      renameSession(sessionId, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <Stack gap="xs">
      <Button
        leftSection={<IconPlus size={18} />}
        onClick={createSession}
        fullWidth
        variant="light"
      >
        Новый чат
      </Button>

      <Stack gap="xs" mt="md">
        {sessions.map((session) => (
          <Group
            key={session.id}
            gap="xs"
            p="xs"
            style={{
              backgroundColor:
                currentSessionId === session.id
                  ? 'var(--mantine-color-blue-0)'
                  : undefined,
              borderRadius: 'var(--mantine-radius-sm)',
              cursor: 'pointer',
            }}
            onClick={() => setCurrentSession(session.id)}
          >
            <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
              {editingId === session.id ? (
                <TextInput
                  value={editValue}
                  onChange={(e) => setEditValue(e.currentTarget.value)}
                  onBlur={() => handleSaveRename(session.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveRename(session.id);
                    if (e.key === 'Escape') setEditingId(null);
                  }}
                  size="xs"
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <Text size="sm" fw={500} lineClamp={1}>
                  {session.title}
                </Text>
              )}

              <Text size="xs" c="dimmed">
                {format(session.updatedAt, 'dd.MM, HH:mm')} • {session.messageCount} сообщ.
              </Text>
            </Stack>

            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={(e) => e.stopPropagation()}
                >
                  <IconDots size={16} />
                </ActionIcon>
              </Menu.Target>

              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconEdit size={14} />}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRename(session.id, session.title);
                  }}
                >
                  Переименовать
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconTrash size={14} />}
                  color="red"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Удалить этот чат?')) {
                      deleteSession(session.id);
                    }
                  }}
                >
                  Удалить
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        ))}
      </Stack>
    </Stack>
  );
}
