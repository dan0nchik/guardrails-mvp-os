/**
 * Right panel - inspector
 */

import { Paper, Text } from '@mantine/core';
import { InspectorTabs } from '../inspector/InspectorTabs';

export function RightPanel() {
  return (
    <Paper h="100%" withBorder style={{ display: 'flex', flexDirection: 'column' }}>
      <Text p="md" fw={600} size="lg" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
        Инспектор
      </Text>
      <InspectorTabs />
    </Paper>
  );
}
