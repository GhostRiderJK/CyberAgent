import { describe, expect, it } from 'vitest';
import { formatConfidencePct, formatSeconds } from './format';

describe('formatConfidencePct', () => {
  it('shows two decimals so a near-certain score is not read as certainty', () => {
    expect(formatConfidencePct(0.9998)).toBe('99.98%');
    expect(formatConfidencePct(0.8686400959844025)).toBe('86.86%');
  });

  it('never rounds a value below 1 up to 100%', () => {
    for (const v of [0.9999, 0.99994, 0.99999, 0.999999, 1 - Number.EPSILON / 2]) {
      expect(formatConfidencePct(v)).not.toBe('100.00%');
    }
    expect(formatConfidencePct(0.99999)).toBe('99.99%');
  });

  it('does show 100.00% when the model actually reported exactly 1.0', () => {
    expect(formatConfidencePct(1)).toBe('100.00%');
  });

  it('clamps out-of-range and non-finite values instead of printing nonsense', () => {
    expect(formatConfidencePct(1.4)).toBe('100.00%');
    expect(formatConfidencePct(-0.2)).toBe('0.00%');
    expect(formatConfidencePct(Number.NaN)).toBe('—');
  });
});

describe('formatSeconds', () => {
  it('renders a missing measurement as an em dash, never as zero', () => {
    expect(formatSeconds(null)).toBe('—');
    expect(formatSeconds(undefined)).toBe('—');
    expect(formatSeconds(11.28)).toBe('11.28 s');
  });
});
