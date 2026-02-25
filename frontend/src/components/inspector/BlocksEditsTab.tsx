/**
 * Blocks/Edits tab - shows what was blocked or modified
 */

import { Stack, Text, Paper, Badge, Group, Alert, Code } from '@mantine/core';
import {
  IconAlertTriangle,
  IconInfoCircle,
  IconExclamationCircle,
} from '@tabler/icons-react';
import type { Message, RailEvent } from '@/types';

interface BlocksEditsTabProps {
  message: Message | null;
}

export function BlocksEditsTab({ message }: BlocksEditsTabProps) {
  if (!message) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Выберите сообщение для инспектирования</Text>
      </Stack>
    );
  }

  const railEvents = message.railEvents || [];

  if (railEvents.length === 0) {
    return (
      <Stack align="center" justify="center" h={200}>
        <Text c="dimmed">Нет событий барьеров для этого сообщения</Text>
      </Stack>
    );
  }

  const getSeverityIcon = (severity: RailEvent['severity']) => {
    switch (severity) {
      case 'block':
        return <IconExclamationCircle size={16} />;
      case 'warn':
        return <IconAlertTriangle size={16} />;
      case 'info':
        return <IconInfoCircle size={16} />;
    }
  };

  const getSeverityColor = (severity: RailEvent['severity']) => {
    switch (severity) {
      case 'block':
        return 'red';
      case 'warn':
        return 'orange';
      case 'info':
        return 'blue';
    }
  };

  return (
    <Stack gap="md">
      <Text size="sm" fw={500}>
        События барьеров ({railEvents.length})
      </Text>

      {railEvents.map((event, idx) => (
        <Paper key={idx} p="md" withBorder>
          <Group mb="xs">
            <Badge
              color={getSeverityColor(event.severity)}
              leftSection={getSeverityIcon(event.severity)}
            >
              {event.severity}
            </Badge>
            <Badge variant="light">{event.stage}</Badge>
          </Group>

          <Text size="sm" fw={500} mb="xs">
            {event.railName}
          </Text>

          <Text size="sm" c="dimmed" mb="xs">
            {event.reason}
          </Text>

          {event.details?.snippet && (
            <Alert color={getSeverityColor(event.severity)} variant="light" mb="xs">
              <Text size="xs" fw={500} mb={4}>
                Затронутый контент:
              </Text>
              <Code block>{event.details.snippet}</Code>
            </Alert>
          )}

          {event.details?.before && event.details?.after && (
            <Stack gap="xs">
              <div>
                <Text size="xs" fw={500} c="dimmed" mb={4}>
                  До:
                </Text>
                <Code block>{event.details.before}</Code>
              </div>
              <div>
                <Text size="xs" fw={500} c="dimmed" mb={4}>
                  После:
                </Text>
                <Code block>{event.details.after}</Code>
              </div>
            </Stack>
          )}
        </Paper>
      ))}
    </Stack>
  );
}
