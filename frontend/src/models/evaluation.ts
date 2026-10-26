/**
 * Types and selectors for the one evaluation artifact the UI is allowed to read.
 *
 * The JSON is imported as text and parsed at module load so TypeScript does not have
 * to infer a literal type over ~2,200 curve points, and so a hand-edited or stale file
 * fails here rather than silently rendering wrong numbers.
 */
import rawEvaluation from '@/data/evaluation.json?raw';

export interface PrPoint {
  recall: number;
  precision: number;
}

export interface PrCurve {
  points: PrPoint[];
  average_precision: number;
  n_thresholds: number;
}

export interface ModelMetrics {
  accuracy: number;
  precision_weighted: number;
  recall_weighted: number;
  f1_weighted: number;
  f1_macro: number;
  inference_time_ms_per_1000: number;
  /** null when the training log that measured it is not available. */
  training_time_s: number | null;
  n_classes: number;
}

export interface PerClassMetric {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface ZeroDayRow {
  model: string;
  accuracy: number;
  macro_f1: number;
  per_class_f1: Record<string, number>;
}

export interface EvaluationReady {
  available: true;
  /** Set by npm run sync:eval; the artifact itself does not carry it. */
  source_path?: string;
  schema_version: number;
  generated_at: string;
  git_commit: string | null;
  dataset: {
    source: string;
    n_samples: number;
    split: { mode: string | null; ratios: number[] | null; seed: number | null };
    note: string;
  };
  labels: string[];
  models: Record<string, ModelMetrics>;
  best_model: string;
  selection_rule: string;
  confusion_matrix: {
    model: string;
    rows: string;
    columns: string;
    matrix: number[][];
    support: number[];
    accuracy: number;
    correct: number;
    total: number;
  };
  per_class: { model: string; metrics: Record<string, PerClassMetric> };
  pr_curves: {
    model: string;
    strategy: string;
    max_points_per_class: number;
    curves: Record<string, PrCurve>;
  };
  zero_day_holdout: ZeroDayRow[];
  n_holdout_samples: number;
  zero_day_labels: string[];
  provenance: Record<string, string>;
  limitations: string[];
}

export interface EvaluationMissing {
  available: false;
  reason: string;
  command: string;
  requires: string;
}

export type EvaluationDoc = EvaluationReady | EvaluationMissing;

function isReady(doc: EvaluationDoc): doc is EvaluationReady {
  return doc.available === true;
}

export { isReady };

function parse(raw: string): EvaluationDoc {
  let doc: unknown;
  try {
    doc = JSON.parse(raw);
  } catch (e) {
    return {
      available: false,
      reason: `src/data/evaluation.json is not valid JSON (${(e as Error).message}).`,
      command: 'npm run sync:eval',
      requires: 'artifacts/eval/evaluation.json',
    };
  }
  if (!doc || typeof doc !== 'object') {
    return {
      available: false,
      reason: 'src/data/evaluation.json is empty.',
      command: 'npm run sync:eval',
      requires: 'artifacts/eval/evaluation.json',
    };
  }
  if (doc instanceof Object && 'available' in doc && doc.available === false) {
    return doc as EvaluationMissing;
  }
  const candidate = doc as EvaluationReady;
  const problems: string[] = [];
  if (!Array.isArray(candidate.labels) || candidate.labels.length === 0) problems.push('labels');
  if (!candidate.models || typeof candidate.models !== 'object') problems.push('models');
  if (!candidate.best_model) problems.push('best_model');
  if (!Array.isArray(candidate.confusion_matrix?.matrix)) problems.push('confusion_matrix');
  if (!candidate.pr_curves?.curves) problems.push('pr_curves');
  if (problems.length) {
    return {
      available: false,
      reason: `src/data/evaluation.json is missing required field(s): ${problems.join(', ')}.`,
      command: 'npm run sync:eval',
      requires: 'artifacts/eval/evaluation.json',
    };
  }
  return candidate;
}

export const evaluation: EvaluationDoc = parse(rawEvaluation);

/** Accuracy recomputed from the matrix itself: diagonal / total. */
export function matrixAccuracy(matrix: number[][]): number {
  let total = 0;
  let correct = 0;
  matrix.forEach((row, i) => {
    const rowTotal = row.reduce((a, b) => a + b, 0);
    total += rowTotal;
    correct += row[i] ?? 0;
  });
  return total === 0 ? 0 : correct / total;
}

export function matrixTotal(matrix: number[][]): number {
  return matrix.reduce((sum, row) => sum + row.reduce((a, b) => a + b, 0), 0);
}

/** Rows: true class. Divide each row by its total so every row sums to 1. */
export function rowNormalize(matrix: number[][]): number[][] {
  return matrix.map((row) => {
    const total = row.reduce((a, b) => a + b, 0);
    return total === 0 ? row.map(() => 0) : row.map((v) => v / total);
  });
}

export interface ClassRow {
  label: string;
  index: number;
  support: number;
  metric: PerClassMetric | null;
}

/** All real classes, ordered by how often they occur in the test split (desc). */
export function classesBySupport(doc: EvaluationReady): ClassRow[] {
  return doc.labels
    .map((label, index) => ({
      label,
      index,
      support: doc.per_class.metrics[label]?.support ?? doc.confusion_matrix.support[index] ?? 0,
      metric: doc.per_class.metrics[label] ?? null,
    }))
    .sort((a, b) => b.support - a.support || a.label.localeCompare(b.label));
}

export interface ModelRow {
  model: string;
  metrics: ModelMetrics;
  isBest: boolean;
}

/** Model zoo, best first under the documented selection rule. */
export function modelsRankedByMacroF1(doc: EvaluationReady): ModelRow[] {
  return Object.entries(doc.models)
    .sort((a, b) => b[1].f1_macro - a[1].f1_macro || a[0].localeCompare(b[0]))
    .map(([model, metrics]) => ({ model, metrics, isBest: model === doc.best_model }));
}

export function classesByLowestAveragePrecision(doc: EvaluationReady, count: number): string[] {
  return Object.entries(doc.pr_curves.curves)
    .sort((a, b) => a[1].average_precision - b[1].average_precision)
    .slice(0, count)
    .map(([label]) => label);
}
