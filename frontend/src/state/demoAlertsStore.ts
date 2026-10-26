import type { Alert } from '@/mocks/alerts';

/**
 * Tiny module store bridging the Simulation page to the Alerts table.
 * Frontend-only and in-memory: demo flows vanish on page reload and never
 * touch fixtures or API data.
 */
let alerts: Alert[] = [];
const listeners = new Set<() => void>();

export function setDemoAlerts(next: Alert[]): void {
  alerts = next;
  for (const l of listeners) l();
}

export function clearDemoAlerts(): void {
  setDemoAlerts([]);
}

export function getDemoAlerts(): Alert[] {
  return alerts;
}

export function subscribeDemoAlerts(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
