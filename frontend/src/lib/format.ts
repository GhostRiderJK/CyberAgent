/** Formatting rules shared by every page that shows a confidence or a percentage. */

/**
 * Confidence as a percentage with `decimals` places.
 *
 * A value below 1 never renders as 100%: 0.9998 must read 99.98%, and 0.99999 must
 * read 99.99% rather than implying a certainty the model did not report.
 */
export function formatConfidencePct(value: number, decimals = 2): string {
  if (!Number.isFinite(value)) return '—';
  const clamped = Math.max(0, Math.min(1, value));
  const capped = clamped < 1 ? Math.min(clamped * 100, 100 - 10 ** -decimals) : clamped * 100;
  return `${capped.toFixed(decimals)}%`;
}

/** Fixed-decimal percent for values that are already on a 0-100 scale. */
export function formatPct(value: number, decimals = 2): string {
  if (!Number.isFinite(value)) return '—';
  return `${value.toFixed(decimals)}%`;
}

/** Seconds, or an em dash when the measurement does not exist. */
export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${value.toFixed(2)} s`;
}

export function formatMilliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${value.toFixed(1)} ms`;
}

export function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return Math.trunc(value).toLocaleString('en-US');
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().replace('T', ' ').replace('Z', ' UTC');
}
