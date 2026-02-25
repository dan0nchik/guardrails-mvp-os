/**
 * LocalStorage utilities for sessions and messages
 */

import type { Session, Message } from '@/types';

const SESSIONS_KEY = 'guardrails_sessions';
const MESSAGES_KEY_PREFIX = 'guardrails_messages_';

export const storage = {
  // Sessions
  getSessions(): Session[] {
    try {
      const data = localStorage.getItem(SESSIONS_KEY);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  },

  saveSessions(sessions: Session[]): void {
    try {
      localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    } catch (error) {
      console.error('Failed to save sessions:', error);
    }
  },

  // Messages for a session
  getMessages(sessionId: string): Message[] {
    try {
      const data = localStorage.getItem(MESSAGES_KEY_PREFIX + sessionId);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  },

  saveMessages(sessionId: string, messages: Message[]): void {
    try {
      localStorage.setItem(MESSAGES_KEY_PREFIX + sessionId, JSON.stringify(messages));
    } catch (error) {
      console.error('Failed to save messages:', error);
    }
  },

  deleteMessages(sessionId: string): void {
    try {
      localStorage.removeItem(MESSAGES_KEY_PREFIX + sessionId);
    } catch (error) {
      console.error('Failed to delete messages:', error);
    }
  },

  // Clear all
  clearAll(): void {
    try {
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith('guardrails_')) {
          localStorage.removeItem(key);
        }
      });
    } catch (error) {
      console.error('Failed to clear storage:', error);
    }
  },
};
