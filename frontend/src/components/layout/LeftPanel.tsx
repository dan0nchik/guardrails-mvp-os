/**
 * Left panel - sessions + guardrails controls
 */

import { Stack, Divider, ScrollArea } from '@mantine/core';
import { RuntimeSettings } from '../settings/RuntimeSettings';
import { GuardrailsToggleAll } from '../guardrails/GuardrailsToggleAll';
import { GuardrailsTogglesList } from '../guardrails/GuardrailsTogglesList';

export function LeftPanel() {
  return (
    <Stack h="100%" gap={0}>
      <ScrollArea style={{ flex: 1 }}>
        <RuntimeSettings />

        <Divider my="md" />

        <GuardrailsToggleAll />
        <GuardrailsTogglesList />
      </ScrollArea>
    </Stack>
  );
}
