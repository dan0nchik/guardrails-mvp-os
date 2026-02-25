/**
 * Sessions store (Zustand)
 */

import { create } from 'zustand';
import type { Session, Message } from '@/types';
import { storage } from '@/utils/storage';

interface SessionsState {
  sessions: Session[];
  currentSessionId: string | null;
  messages: Map<string, Message[]>;

  // Actions
  loadSessions: () => void;
  createSession: () => string;
  deleteSession: (sessionId: string) => void;
  renameSession: (sessionId: string, title: string) => void;
  setCurrentSession: (sessionId: string | null) => void;

  // Messages
  loadMessages: (sessionId: string) => void;
  addMessage: (message: Message) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => void;

  // Current session helpers
  getCurrentSession: () => Session | null;
  getCurrentMessages: () => Message[];
}

export const useSessionsStore = create<SessionsState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: new Map(),

  loadSessions: () => {
    const sessions = storage.getSessions();
    set({ sessions });

    // Auto-select first session if exists
    if (sessions.length > 0 && !get().currentSessionId) {
      const firstId = sessions[0].id;
      set({ currentSessionId: firstId });
      get().loadMessages(firstId);
    }
  },

  createSession: () => {
    const newSession: Session = {
      id: `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      title: 'Новый чат',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messageCount: 0,
    };

    const sessions = [newSession, ...get().sessions];
    set({ sessions, currentSessionId: newSession.id });
    storage.saveSessions(sessions);

    return newSession.id;
  },

  deleteSession: (sessionId: string) => {
    const sessions = get().sessions.filter(s => s.id !== sessionId);
    set({ sessions });
    storage.saveSessions(sessions);
    storage.deleteMessages(sessionId);

    // If deleted current session, switch to another
    if (get().currentSessionId === sessionId) {
      const nextId = sessions[0]?.id || null;
      set({ currentSessionId: nextId });
      if (nextId) {
        get().loadMessages(nextId);
      }
    }
  },

  renameSession: (sessionId: string, title: string) => {
    const sessions = get().sessions.map(s =>
      s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s
    );
    set({ sessions });
    storage.saveSessions(sessions);
  },

  setCurrentSession: (sessionId: string | null) => {
    set({ currentSessionId: sessionId });
    if (sessionId) {
      get().loadMessages(sessionId);
    }
  },

  loadMessages: (sessionId: string) => {
    const messages = storage.getMessages(sessionId);
    const messagesMap = new Map(get().messages);
    messagesMap.set(sessionId, messages);
    set({ messages: messagesMap });
  },

  addMessage: (message: Message) => {
    const { sessionId } = message;
    const messagesMap = new Map(get().messages);
    const sessionMessages = messagesMap.get(sessionId) || [];

    const updated = [...sessionMessages, message];
    messagesMap.set(sessionId, updated);
    set({ messages: messagesMap });

    // Save to storage
    storage.saveMessages(sessionId, updated);

    // Update session metadata
    const sessions = get().sessions.map(s =>
      s.id === sessionId
        ? {
            ...s,
            updatedAt: Date.now(),
            messageCount: updated.length,
            title: s.title === 'Новый чат' && message.role === 'user'
              ? message.content.slice(0, 50)
              : s.title,
          }
        : s
    );
    set({ sessions });
    storage.saveSessions(sessions);
  },

  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => {
    const messagesMap = new Map(get().messages);
    const sessionMessages = messagesMap.get(sessionId) || [];

    const updated = sessionMessages.map(m =>
      m.id === messageId ? { ...m, ...updates } : m
    );

    messagesMap.set(sessionId, updated);
    set({ messages: messagesMap });
    storage.saveMessages(sessionId, updated);
  },

  getCurrentSession: () => {
    const { currentSessionId, sessions } = get();
    return sessions.find(s => s.id === currentSessionId) || null;
  },

  getCurrentMessages: () => {
    const { currentSessionId, messages } = get();
    return currentSessionId ? messages.get(currentSessionId) || [] : [];
  },
}));
