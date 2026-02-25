/**
 * Guardrails configuration store
 */

import { create } from 'zustand';
import type { GuardrailsConfig } from '@/types';

const STORAGE_KEY = 'guardrails_config';

const DEFAULT_CONFIG: GuardrailsConfig = {
  enabled: true,
  monitorOnly: false,
  toggles: {
    'input.pii': true,
    'input.injection': true,
    'input.policy': true,
    'input.length': true,
    'exec.tool_allowlist': true,
    'exec.arg_validation': true,
    'exec.rate_limit': true,
    'exec.loop_detection': true,
    'output.format': true,
    'output.pii': true,
    'output.tool_truth': true,
    'output.safety': true,
    'hallucination.judge': false,
  },
};

interface GuardrailsState {
  config: GuardrailsConfig;

  // Actions
  loadConfig: () => void;
  setEnabled: (enabled: boolean) => void;
  setMonitorOnly: (monitorOnly: boolean) => void;
  toggleRail: (key: keyof GuardrailsConfig['toggles']) => void;
  setRail: (key: keyof GuardrailsConfig['toggles'], value: boolean) => void;
  resetToDefault: () => void;
}

export const useGuardrailsStore = create<GuardrailsState>((set, get) => ({
  config: DEFAULT_CONFIG,

  loadConfig: () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const config = JSON.parse(stored);
        set({ config: { ...DEFAULT_CONFIG, ...config } });
      }
    } catch (error) {
      console.error('Failed to load guardrails config:', error);
    }
  },

  setEnabled: (enabled: boolean) => {
    const config = { ...get().config, enabled };
    set({ config });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  },

  setMonitorOnly: (monitorOnly: boolean) => {
    const config = { ...get().config, monitorOnly };
    set({ config });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  },

  toggleRail: (key: keyof GuardrailsConfig['toggles']) => {
    const current = get().config.toggles[key];
    get().setRail(key, !current);
  },

  setRail: (key: keyof GuardrailsConfig['toggles'], value: boolean) => {
    const config = {
      ...get().config,
      toggles: {
        ...get().config.toggles,
        [key]: value,
      },
    };
    set({ config });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  },

  resetToDefault: () => {
    set({ config: DEFAULT_CONFIG });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_CONFIG));
  },
}));
