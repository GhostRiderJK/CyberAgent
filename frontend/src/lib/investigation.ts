/** Turns the agent's structured explanation payload into chart data. */
import type { FlowRecord, ShapExplanation, ShapFeature } from '@/models/apiModels';

export type { FlowRecord, ShapFeature };

export interface ShapBar {
  feature: string;
  shap: number;
  standardized: number;
}

export type ShapPanel =
  | { kind: 'chart'; bars: ShapBar[]; valueScale: string }
  | { kind: 'empty'; reason: string };

const TOP_K = 10;

function describeTools(tools: string[] | undefined): string {
  return tools && tools.length ? tools.join(', ') : 'none';
}

/**
 * Reads `shap_explanation`, the arrays the explain_flow tool actually returned.
 *
 * The evidence table holds prose ("Top feature: X (SHAP: 0.12)"), and parsing that as
 * JSON is what made this panel claim there was no data while the verdict quoted SHAP
 * values. An empty chart is only shown when the backend truly produced nothing, and
 * then the backend's own reason is shown instead of a generic message.
 */
export function buildShapPanel(
  payload: ShapExplanation | null | undefined,
  toolsCalled?: string[],
): ShapPanel {
  if (!payload) {
    return {
      kind: 'empty',
      reason: `explain_flow returned no structured explanation in this run (tools called: ${describeTools(toolsCalled)}).`,
    };
  }
  const features = (payload.features ?? []).filter(
    (f) => typeof f.shap_value === 'number' && Number.isFinite(f.shap_value),
  );
  if (features.length === 0) {
    return {
      kind: 'empty',
      reason: payload.explanation_error
        ? `explain_flow could not compute an explanation: ${payload.explanation_error}`
        : 'explain_flow returned zero features for this flow.',
    };
  }
  const bars = [...features]
    .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
    .slice(0, TOP_K)
    .map((f) => ({
      feature: f.feature,
      shap: f.shap_value,
      standardized: typeof f.standardized_value === 'number' ? f.standardized_value : Number.NaN,
    }));
  return { kind: 'chart', bars, valueScale: payload.value_scale ?? 'standardized' };
}

/** True when the flow record genuinely does not carry this field. */
export function isMissingFromRecord(record: FlowRecord | null | undefined, field: string): boolean {
  return (record?.missing_fields ?? []).includes(field);
}
