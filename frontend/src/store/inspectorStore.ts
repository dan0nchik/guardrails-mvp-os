/**
 * Inspector state store
 */

import { create } from 'zustand';

interface InspectorState {
  selectedMessageId: string | null;
  activeTab: 'actions' | 'guardrails' | 'blocks' | 'generated';

  setSelectedMessage: (messageId: string | null) => void;
  setActiveTab: (tab: InspectorState['activeTab']) => void;
}

export const useInspectorStore = create<InspectorState>((set) => ({
  selectedMessageId: null,
  activeTab: 'actions',

  setSelectedMessage: (messageId: string | null) => {
    set({ selectedMessageId: messageId });
  },

  setActiveTab: (tab) => {
    set({ activeTab: tab });
  },
}));
