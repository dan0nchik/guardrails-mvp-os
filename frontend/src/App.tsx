/**
 * Main App component
 */

import { useEffect } from 'react';
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { AppShellLayout } from './components/layout/AppShellLayout';
import { useSessionsStore } from './store/sessionsStore';
import { useGuardrailsStore } from './store/guardrailsStore';

import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';

export default function App() {
  const loadSessions = useSessionsStore((state) => state.loadSessions);
  const createSession = useSessionsStore((state) => state.createSession);
  const sessions = useSessionsStore((state) => state.sessions);
  const loadGuardrailsConfig = useGuardrailsStore((state) => state.loadConfig);

  useEffect(() => {
    // Load saved state on mount
    loadSessions();
    loadGuardrailsConfig();

    // Create default session if none exists
    if (sessions.length === 0) {
      createSession();
    }
  }, []);

  return (
    <MantineProvider defaultColorScheme="light">
      <Notifications position="top-right" />
      <AppShellLayout />
    </MantineProvider>
  );
}
