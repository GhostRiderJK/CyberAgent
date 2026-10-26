import { useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { classColor, displayClass } from '@/lib/classLabels';
import { formatConfidencePct, formatInteger } from '@/lib/format';
import {
  classesBySupport,
  matrixAccuracy,
  matrixTotal,
  rowNormalize,
  type EvaluationReady,
} from '@/models/evaluation';

type View = 'counts' | 'percent';

interface Props {
  doc: EvaluationReady;
}

/**
 * The best model's real confusion matrix. Nothing here is rounded into plausibility:
 * cells are the exact counts from the artifact and the header recomputes accuracy from
 * those same counts, so a matrix that disagreed with the headline metrics would show it.
 */
export default function ConfusionMatrixTable({ doc }: Props) {
  const [view, setView] = useState<View>('counts');
  const rows = useMemo(() => classesBySupport(doc), [doc]);
  const percent = useMemo(() => rowNormalize(doc.confusion_matrix.matrix), [doc]);
  const computedAccuracy = useMemo(() => matrixAccuracy(doc.confusion_matrix.matrix), [doc]);
  const total = useMemo(() => matrixTotal(doc.confusion_matrix.matrix), [doc]);
  const headline = doc.models[doc.best_model].accuracy;
  const consistent = Math.abs(computedAccuracy - headline) < 1e-6;

  const cell = (count: number, pct: number) =>
    view === 'counts' ? (count === 0 ? <span className="text-slate-600">0</span> : formatInteger(count))
      : pct === 0 ? <span className="text-slate-600">0.0%</span> : `${(pct * 100).toFixed(1)}%`;

  return (
    <Card className="surface panel w-full">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-navy-200">Confusion matrix - {doc.confusion_matrix.model}</CardTitle>
        <CardDescription className="mt-1 text-sm text-slate-400">
          Rows are the true class, columns the predicted one, over all {formatInteger(doc.labels.length)} labels
          the model can output. {formatInteger(doc.confusion_matrix.correct)} of{' '}
          {formatInteger(total)} flows classified correctly = {formatConfidencePct(computedAccuracy)} accuracy.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 p-5 pt-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Cell values</span>
            {(['counts', 'percent'] as View[]).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={view === mode}
                onClick={() => setView(mode)}
                className={`rounded border px-2 py-1 ${
                  view === mode
                    ? 'border-cyan-400/60 bg-cyan-400/10 text-cyan-200'
                    : 'border-white/10 text-slate-400 hover:border-white/25'
                }`}
              >
                {mode === 'counts' ? 'Counts' : 'Row %'}
              </button>
            ))}
          </div>
          <span
            className={`rounded px-2 py-1 text-xs font-medium ${
              consistent ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
            }`}
          >
            {consistent
              ? `Matches the reported accuracy (${formatConfidencePct(headline)})`
              : `Matrix says ${formatConfidencePct(computedAccuracy)} but the table reports ${formatConfidencePct(headline)}`}
          </span>
        </div>

        <div className="max-h-[560px] overflow-auto rounded border border-white/10">
          <table className="mono border-collapse text-xs">
            <thead className="sticky top-0 z-10 bg-navy-800">
              <tr>
                <th className="sticky left-0 z-20 bg-navy-800 px-2 py-2 text-left font-medium text-slate-300">
                  True \ Pred
                </th>
                {rows.map((r) => (
                  <th key={r.label} className="whitespace-nowrap px-2 py-2 font-medium" style={{ color: classColor(r.label) }}>
                    {displayClass(r.label)}
                  </th>
                ))}
                <th className="px-2 py-2 font-medium text-slate-400">Support</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-t border-white/5">
                  <th
                    scope="row"
                    className="sticky left-0 z-[5] whitespace-nowrap bg-navy-800 px-2 py-1 text-left font-medium"
                    style={{ color: classColor(row.label) }}
                  >
                    {displayClass(row.label)}
                  </th>
                  {rows.map((col) => {
                    const count = doc.confusion_matrix.matrix[row.index][col.index];
                    const pct = percent[row.index][col.index];
                    const isDiagonal = row.index === col.index;
                    return (
                      <td
                        key={col.label}
                        title={`${displayClass(row.label)} predicted as ${displayClass(col.label)}: ${count} (${(pct * 100).toFixed(2)}% of row)`}
                        className={`px-2 py-1 text-right ${isDiagonal ? 'bg-emerald-400/10 text-emerald-100' : 'text-slate-300'}`}
                      >
                        {cell(count, pct)}
                      </td>
                    );
                  })}
                  <td className="px-2 py-1 text-right text-slate-400">{formatInteger(row.support)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500">
          Sorted by support, largest class first. BENIGN dominates this split, which is why
          accuracy alone is not a useful summary of attack detection.
        </p>
      </CardContent>
    </Card>
  );
}
