/**
 * Inspector tabs component
 */

import { Tabs } from '@mantine/core';
import { IconTool, IconShield, IconAlertTriangle, IconFileCode } from '@tabler/icons-react';
import { ActionsTab } from './ActionsTab';
import { GuardrailsTab } from './GuardrailsTab';
import { BlocksEditsTab } from './BlocksEditsTab';
import { GeneratedRailsTab } from './GeneratedRailsTab';
import { useInspectorStore } from '@/store/inspectorStore';
import { useSessionsStore } from '@/store/sessionsStore';

export function InspectorTabs() {
  const { selectedMessageId, activeTab, setActiveTab } = useInspectorStore();
  const { getCurrentMessages } = useSessionsStore();

  const messages = getCurrentMessages();
  const selectedMessage = messages.find((m) => m.id === selectedMessageId) || null;

  return (
    <Tabs value={activeTab} onChange={(v) => setActiveTab(v as any)} h="100%">
      <Tabs.List>
        <Tabs.Tab value="actions" leftSection={<IconTool size={16} />}>
          Действия
        </Tabs.Tab>
        <Tabs.Tab value="guardrails" leftSection={<IconShield size={16} />}>
          Барьеры
        </Tabs.Tab>
        <Tabs.Tab value="blocks" leftSection={<IconAlertTriangle size={16} />}>
          Блокировки
        </Tabs.Tab>
        <Tabs.Tab value="generated" leftSection={<IconFileCode size={16} />}>
          Дин. правила
        </Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="actions" p="md" style={{ overflowY: 'auto', height: 'calc(100% - 42px)' }}>
        <ActionsTab message={selectedMessage} />
      </Tabs.Panel>

      <Tabs.Panel value="guardrails" p="md" style={{ overflowY: 'auto', height: 'calc(100% - 42px)' }}>
        <GuardrailsTab message={selectedMessage} />
      </Tabs.Panel>

      <Tabs.Panel value="blocks" p="md" style={{ overflowY: 'auto', height: 'calc(100% - 42px)' }}>
        <BlocksEditsTab message={selectedMessage} />
      </Tabs.Panel>

      <Tabs.Panel value="generated" p="md" style={{ overflowY: 'auto', height: 'calc(100% - 42px)' }}>
        <GeneratedRailsTab message={selectedMessage} />
      </Tabs.Panel>
    </Tabs>
  );
}
