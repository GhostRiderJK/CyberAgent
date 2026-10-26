import type { HealthResponse, ModelStatusResponse, PredictRequest, PredictResponse, FlowMetadataResponse, InvestigationResult } from '../models/apiModels';

// Base URL for the API - empty for same-origin (proxied/rewritten),
// or set VITE_API_BASE_URL=http://localhost:8000 for direct dev against the API server
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export const api = {
  healthCheck: async (): Promise<HealthResponse> => {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    return response.json();
  },

  getModelStatus: async (): Promise<ModelStatusResponse> => {
    const response = await fetch(`${API_BASE_URL}/model/status`);
    if (!response.ok) {
      throw new Error(`Failed to get model status: ${response.status}`);
    }
    return response.json();
  },

  predictFlow: async (request: PredictRequest): Promise<PredictResponse> => {
    const response = await fetch(`${API_BASE_URL}/predict`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error(`Prediction failed: ${response.status}`);
    }
    return response.json();
  },

  getFlowMetadata: async (flowId: number): Promise<FlowMetadataResponse> => {
    const response = await fetch(`${API_BASE_URL}/flow/${flowId}`);
    if (!response.ok) {
      throw new Error(`Failed to get flow metadata: ${response.status}`);
    }
    return response.json();
  },

  // For SSE, we return an AsyncGenerator that yields InvestigationResult objects
  investigateFlow: async (request: PredictRequest): Promise<AsyncGenerator<InvestigationResult, void, unknown>> => {
    const response = await fetch(`${API_BASE_URL}/investigate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Investigation failed: ${response.status}`);
    }

    if (!response.body) {
      throw new Error('No response body');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    const generator = async function* () {
      try {
        let currentEvent = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          let lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6);
              let parsed: unknown;
              try {
                parsed = JSON.parse(data);
              } catch (e) {
                console.error('Failed to parse SSE data:', data, e);
                currentEvent = '';
                continue;
              }
              if (currentEvent === 'error') {
                throw new Error(String((parsed as { error?: string }).error ?? 'Investigation failed'));
              }
              if (currentEvent === 'end') {
                yield parsed as InvestigationResult;
                return;
              }
              // start / progress events carry no result payload
              currentEvent = '';
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    };

    return generator();
  },
};
