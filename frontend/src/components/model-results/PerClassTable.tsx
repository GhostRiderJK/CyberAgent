import { useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { classColor, displayClass } from '@/lib/classLabels';
import { formatConfidencePct, formatInteger } from '@/lib/format';
import { classesBySupport, type EvaluationReady } from '@/models/evaluation';

interface Props {
  doc: EvaluationReady;
}

/** Per-class numbers for the selected model - the metrics that survive class imbalance. */
export default function PerClassTable({ doc }: Props) {
  const rows = useMemo(() => classesBySupport(doc), [doc]);
  const totalSupport = rows.reduce((sum, r) => sum + r.support, 0);

  return (
    <Card className="surface panel w-full overflow-hidden">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-navy-200">Per-class performance - {doc.per_class.model}</CardTitle>
        <CardDescription className="mt-1 text-sm text-slate-400">
          {formatInteger(totalSupport)} test flows across {formatInteger(rows.length)} classes. A class
          with a handful of samples can move its F1 a long way with a handful of mistakes, so support
          is printed next to every score.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-5 pt-2">
        <div className="overflow-x-auto">
          <table className="data-table w-full text-sm">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left">Class</th>
                <th className="px-4 py-3 text-right">Support</th>
                <th className="px-4 py-3 text-right">Share of split</th>
                <th className="px-4 py-3 text-right">Precision</th>
                <th className="px-4 py-3 text-right">Recall</th>
                <th className="px-4 py-3 text-right">F1</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const m = r.metric;
                return (
                  <tr key={r.label}>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: classColor(r.label) }} aria-hidden="true" />
                      <span style={{ color: classColor(r.label) }}>{displayClass(r.label)}</span>
                    </td>
                    <td className="px-4 py-3 text-right mono">{formatInteger(r.support)}</td>
                    <td className="px-4 py-3 text-right mono text-slate-400">
                      {totalSupport ? `${((r.support / totalSupport) * 100).toFixed(2)}%` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right mono">{m ? formatConfidencePct(m.precision) : '—'}</td>
                    <td className="px-4 py-3 text-right mono">{m ? formatConfidencePct(m.recall) : '—'}</td>
                    <td className="px-4 py-3 text-right mono">{m ? formatConfidencePct(m.f1) : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
