/**
 * API client for backend communication
 */

import type { ChatRequest, ChatResponse, RuntimeConfig } from '@/types';

const API_BASE = '/api';

export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export const api = {
  /**
   * Send chat message
   */
  async chat(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new APIError(
          error.detail || 'Request failed',
          response.status,
          error
        );
      }

      return await response.json();
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      if ((error as Error).name === 'AbortError') {
        throw new APIError('Request cancelled');
      }

      throw new APIError(
        error instanceof Error ? error.message : 'Network error'
      );
    }
  },

  /**
   * Get runtime config
   */
  async getConfig(): Promise<RuntimeConfig> {
    const response = await fetch(`${API_BASE}/config`);
    if (!response.ok) {
      throw new APIError('Failed to fetch config', response.status);
    }
    return response.json();
  },

  /**
   * Update runtime config (partial)
   */
  async setConfig(update: Partial<Pick<RuntimeConfig, 'guardrails_backend' | 'llm_provider' | 'llm_model'>>): Promise<RuntimeConfig> {
    const response = await fetch(`${API_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new APIError(error.detail || 'Failed to update config', response.status, error);
    }
    return response.json();
  },

  /**
   * Health check
   */
  async health(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
  },

  /**
   * Get metrics (optional)
   */
  async metrics(): Promise<string> {
    const response = await fetch(`${API_BASE}/metrics`);
    return response.text();
  },
};
