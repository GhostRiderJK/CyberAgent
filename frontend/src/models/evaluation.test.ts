import { describe, expect, it } from 'vitest';
import {
  classesByLowestAveragePrecision, classesBySupport, isReady, matrixAccuracy, matrixTotal,
  modelsRankedByMacroF1, rowNormalize, evaluation,
} from './evaluation';

const doc = isReady(evaluation) ? evaluation : null;
const guard = doc ? describe : describe.skip;

guard('evaluation artifact selectors', () => {
  it('computes the same accuracy from the matrix that the comparison table reports', () => {
    // This is the check the old page failed: a ~92% matrix sitting under a 99.89% headline.
    const computed = matrixAccuracy(doc!.confusion_matrix.matrix);
    const reported = doc!.models[doc!.best_model].accuracy;
    expect(Math.abs(computed - reported)).toBeLessThan(1e-6);
    expect(doc!.confusion_matrix.accuracy).toBeCloseTo(computed, 6);
  });

  it('counts exactly the number of test samples in the matrix', () => {
    expect(matrixTotal(doc!.confusion_matrix.matrix)).toBe(doc!.dataset.n_samples);
    expect(doc!.confusion_matrix.support).toEqual(
      doc!.labels.map((l) => doc!.per_class.metrics[l].support),
    );
  });

  it('keeps the matrix square over the label list', () => {
    expect(doc!.confusion_matrix.matrix).toHaveLength(doc!.labels.length);
    for (const row of doc!.confusion_matrix.matrix) expect(row).toHaveLength(doc!.labels.length);
  });

  it('row-normalises without losing the diagonal', () => {
    const norm = rowNormalize(doc!.confusion_matrix.matrix);
    norm.forEach((row, i) => {
      expect(row.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 8);
      expect(row[i]).toBeCloseTo(
        doc!.confusion_matrix.matrix[i][i] / doc!.confusion_matrix.support[i], 8);
    });
    expect(rowNormalize([[0, 0], [1, 1]])[0]).toEqual([0, 0]); // empty row must not be NaN
  });

  it('orders classes by support and models by macro F1', () => {
    const supports = classesBySupport(doc!).map((r) => r.support);
    expect([...supports].sort((a, b) => b - a)).toEqual(supports);
    const ranked = modelsRankedByMacroF1(doc!);
    expect(ranked[0].isBest).toBe(true);
    expect(ranked.map((r) => r.metrics.f1_macro)).toEqual(
      [...ranked.map((r) => r.metrics.f1_macro)].sort((a, b) => b - a),
    );
  });

  it('defaults the PR chart to the weakest classes and keeps curves inside [0,1]', () => {
    const selected = classesByLowestAveragePrecision(doc!, 3);
    expect(selected).toHaveLength(3);
    const aps = selected.map((c) => doc!.pr_curves.curves[c].average_precision);
    const all = Object.values(doc!.pr_curves.curves).map((c) => c.average_precision);
    const sorted = [...all].sort((a, b) => a - b);
    expect([...aps].sort((a, b) => a - b)).toEqual(sorted.slice(0, 3));
    for (const curve of Object.values(doc!.pr_curves.curves)) {
      expect(curve.points.length).toBeLessThanOrEqual(doc!.pr_curves.max_points_per_class);
      expect(curve.points[0].recall).toBe(0);
      expect(curve.points.at(-1)!.recall).toBe(1);
      for (const p of curve.points) {
        expect(p.precision).toBeGreaterThanOrEqual(0);
        expect(p.precision).toBeLessThanOrEqual(1);
      }
    }
  });
});
