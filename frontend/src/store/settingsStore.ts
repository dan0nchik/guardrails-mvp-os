/**
 * Runtime settings store — manages guardrails backend & LLM config
 */

import { create } from 'zustand';
import type { RuntimeConfig } from '@/types';
import { api } from '@/api/client';

interface SettingsState {
  config: RuntimeConfig | null;
  loading: boolean;
  error: string | null;

  fetchConfig: () => Promise<void>;
  setBackend: (backend: RuntimeConfig['guardrails_backend']) => Promise<void>;
  setLLM: (provider: string, model: string) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  config: null,
  loading: false,
  error: null,

  fetchConfig: async () => {
    set({ loading: true, error: null });
    try {
      const config = await api.getConfig();
      set({ config, loading: false });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
    }
  },

  setBackend: async (backend) => {
    set({ loading: true, error: null });
    try {
      const config = await api.setConfig({ guardrails_backend: backend });
      set({ config, loading: false });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
    }
  },

  setLLM: async (provider, model) => {
    set({ loading: true, error: null });
    try {
      const config = await api.setConfig({ llm_provider: provider, llm_model: model });
      set({ config, loading: false });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
    }
  },
}));
