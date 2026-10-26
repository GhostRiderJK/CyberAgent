import { describe, expect, it } from 'vitest';
import { buildShapPanel, isMissingFromRecord } from './investigation';
import type { ShapExplanation } from '@/models/apiModels';

/** The shape explain_flow actually returns: parallel arrays zipped by the agent. */
const realPayload: ShapExplanation = {
  predicted_class: 'DoS Hulk',
  value_scale: 'standardized',
  explanation_error: null,
  features: [
    { feature: 'PSHRPA', shap_value: -0.58, standardized_value: 12.4 },
    { feature: 'ToPkts', shap_value: 2.1, standardized_value: -3.2 },
    { feature: 'ActiveInfo', shap_value: 0.03, standardized_value: 0.8 },
    { feature: 'PktLenMin', shap_value: -1.4, standardized_value: 5.5 },
  ],
};

describe('buildShapPanel', () => {
  it('takes the top 10 by absolute SHAP, signed, keeping the standardized value', () => {
    const wide: ShapExplanation = {
      ...realPayload,
      features: Array.from({ length: 25 }, (_, i) => ({
        feature: `F${i}`,
        shap_value: i - 12,
        standardized_value: i / 2,
      })),
    };
    const panel = buildShapPanel(wide);
    expect(panel.kind).toBe('chart');
    if (panel.kind !== 'chart') return;
    expect(panel.bars).toHaveLength(10);
    expect(panel.valueScale).toBe('standardized');
    // Ties on |SHAP| keep the original order, so the negative side leads.
    expect(panel.bars.map((b) => b.shap)).toEqual([-12, 12, -11, 11, -10, 10, -9, 9, -8, 8]);
    for (let i = 1; i < panel.bars.length; i += 1) {
      expect(Math.abs(panel.bars[i - 1].shap)).toBeGreaterThanOrEqual(Math.abs(panel.bars[i].shap));
    }
    expect(panel.bars[0].standardized).toBeTypeOf('number');
  });

  it('keeps the sign so a feature pushing against the label is visible', () => {
    const panel = buildShapPanel(realPayload);
    if (panel.kind !== 'chart') throw new Error('expected a chart');
    expect(panel.bars.map((b) => b.feature)).toEqual(['ToPkts', 'PktLenMin', 'PSHRPA', 'ActiveInfo']);
    expect(panel.bars[2].shap).toBeLessThan(0);
  });

  it('shows the backend reason when the explanation could not be computed', () => {
    const panel = buildShapPanel({
      predicted_class: 'DoS Hulk',
      value_scale: null,
      features: [],
      explanation_error: "TreeExplainer does not support this objective: 'cross_entropy_lambda'",
    });
    expect(panel).toEqual({
      kind: 'empty',
      reason: "explain_flow could not compute an explanation: TreeExplainer does not support this objective: 'cross_entropy_lambda'",
    });
  });

  it('says which tools ran when the run carries no structured explanation at all', () => {
    const panel = buildShapPanel(undefined, ['predict_proba', 'lookup_attack_pattern']);
    expect(panel.kind).toBe('empty');
    if (panel.kind === 'empty') {
      expect(panel.reason).toContain('predict_proba, lookup_attack_pattern');
    }
  });

  it('treats a zero-feature answer with no error as an honest empty state', () => {
    const panel = buildShapPanel({ ...realPayload, features: [], explanation_error: null });
    expect(panel).toEqual({ kind: 'empty', reason: 'explain_flow returned zero features for this flow.' });
  });

  it('drops non-numeric SHAP values instead of plotting them as zero', () => {
    const panel = buildShapPanel({
      ...realPayload,
      features: [
        { feature: 'A', shap_value: Number.NaN, standardized_value: 1 },
        { feature: 'B', shap_value: 0.9, standardized_value: 2 },
      ],
    });
    expect(panel.kind === 'chart' && panel.bars.map((b) => b.feature)).toEqual(['B']);
  });
});

describe('isMissingFromRecord', () => {
  it('marks fields the dataset does not keep', () => {
    const record = {
      flow_id: 949,
      source_ip: '172.16.0.1',
      source_port: 38444,
      destination_ip: null,
      destination_port: null,
      protocol: null,
      timestamp: null,
      missing_fields: ['destination_ip', 'destination_port', 'protocol'],
      available: true,
    };
    expect(isMissingFromRecord(record, 'destination_port')).toBe(true);
    expect(isMissingFromRecord(record, 'source_ip')).toBe(false);
    expect(isMissingFromRecord(null, 'source_ip')).toBe(false);
  });
});
