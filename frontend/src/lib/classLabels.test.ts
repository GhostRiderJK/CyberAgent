import { describe, expect, it } from 'vitest';
import { evaluation, isReady } from '@/models/evaluation';
import {
  MODEL_CLASSES, canonicalClass, classLabelNote, displayClass, flowIdLabel, isModelClass,
} from './classLabels';

describe('classLabels', () => {
  it('agrees with the label list of the evaluation artifact', () => {
    if (!isReady(evaluation)) return; // nothing to compare against until the artifact is built
    expect(MODEL_CLASSES).toEqual([...evaluation.labels]);
  });

  it('resolves the spellings used by fixtures and MITRE text to one canonical label', () => {
    expect(canonicalClass('Web Attack Brute Force')).toBe('Web Attack');
    expect(canonicalClass('web attack')).toBe('Web Attack');
    expect(canonicalClass(' DoS Hulk ')).toBe('DoS Hulk');
    expect(canonicalClass('Infiltration')).toBe('Infiltration');
  });

  it('flags labels the trained classifier cannot output', () => {
    expect(isModelClass('Web Attack Brute Force')).toBe(true);
    expect(classLabelNote('Web Attack Brute Force')).toBeNull();
    expect(isModelClass('Infiltration')).toBe(false);
    expect(classLabelNote('Infiltration')).toBe('not in model label set');
    expect(displayClass('Infiltration')).toBe('Infiltration');
  });

  it('formats one flow id shape for every page', () => {
    expect(flowIdLabel(1)).toBe('FLOW-0001');
    expect(flowIdLabel(1001)).toBe('FLOW-1001');
    expect(flowIdLabel('949')).toBe('FLOW-0949');
  });
});
