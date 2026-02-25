/**
 * Main app shell layout
 */

import { AppShell, Burger, Group, Text, ActionIcon, Tooltip, Menu, ScrollArea, Button } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconShield, IconPlus, IconChevronDown } from '@tabler/icons-react';
import { LeftPanel } from './LeftPanel';
import { RightPanel } from './RightPanel';
import { ChatView } from '../chat/ChatView';
import { useSessionsStore } from '../../store/sessionsStore';

export function AppShellLayout() {
  const [leftOpened, { toggle: toggleLeft }] = useDisclosure(true);
  const [rightOpened, { toggle: toggleRight }] = useDisclosure(true);

  const sessions = useSessionsStore((s) => s.sessions);
  const currentSessionId = useSessionsStore((s) => s.currentSessionId);
  const setCurrentSession = useSessionsStore((s) => s.setCurrentSession);
  const createSession = useSessionsStore((s) => s.createSession);

  const currentSession = sessions.find((s) => s.id === currentSessionId);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: 300,
        breakpoint: 'sm',
        collapsed: { mobile: !leftOpened, desktop: !leftOpened },
      }}
      aside={{
        width: 350,
        breakpoint: 'md',
        collapsed: { mobile: !rightOpened, desktop: !rightOpened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={leftOpened} onClick={toggleLeft} hiddenFrom="sm" size="sm" />
            <IconShield size={28} color="var(--mantine-color-blue-6)" />
            <Text size="xl" fw={700}>
              Guardrails MVP
            </Text>

            <Text c="dimmed">|</Text>

            <Menu position="bottom-start" withinPortal>
              <Menu.Target>
                <Button
                  variant="subtle"
                  size="compact-sm"
                  rightSection={<IconChevronDown size={14} />}
                  style={{ maxWidth: 200 }}
                >
                  <Text truncate size="sm">
                    {currentSession?.title ?? 'Нет чата'}
                  </Text>
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <ScrollArea mah={400}>
                  {sessions.map((session) => (
                    <Menu.Item
                      key={session.id}
                      bg={session.id === currentSessionId ? 'var(--mantine-color-blue-0)' : undefined}
                      onClick={() => setCurrentSession(session.id)}
                    >
                      <Text size="sm" fw={500} truncate>
                        {session.title}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {new Date(session.updatedAt).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })},{' '}
                        {new Date(session.updatedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                        {' · '}{session.messageCount} сообщ.
                      </Text>
                    </Menu.Item>
                  ))}
                </ScrollArea>
              </Menu.Dropdown>
            </Menu>

            <Tooltip label="Новый чат">
              <ActionIcon variant="light" onClick={() => createSession()}>
                <IconPlus size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>

          <Group gap="xs">
            <Tooltip label="Показать/скрыть инспектор">
              <Burger opened={rightOpened} onClick={toggleRight} size="sm" />
            </Tooltip>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <LeftPanel />
      </AppShell.Navbar>

      <AppShell.Main>
        <ChatView />
      </AppShell.Main>

      <AppShell.Aside p="md">
        <RightPanel />
      </AppShell.Aside>
    </AppShell>
  );
}
