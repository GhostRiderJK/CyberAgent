import { useMemo, useState } from 'react';
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { classColor, displayClass } from '@/lib/classLabels';
import { formatInteger } from '@/lib/format';
import {
  classesByLowestAveragePrecision,
  classesBySupport,
  type EvaluationReady,
} from '@/models/evaluation';

const DEFAULT_CLASS_COUNT = 3;

interface Props {
  doc: EvaluationReady;
}

/**
 * Precision-recall curves straight from the stored threshold arrays.
 *
 * Each series carries its own (recall, precision) points on a shared numeric x-axis, so
 * classes keep their own threshold grids instead of being merged onto a guessed one.
 * Line type is stepAfter: the value drawn between two points is one of the two measured
 * points, never an interpolation.
 */
export default function PrecisionRecallChart({ doc }: Props) {
  const curves = doc.pr_curves.curves;
  const ordered = useMemo(() => classesBySupport(doc), [doc]);
  const [selected, setSelected] = useState<string[]>(() =>
    classesByLowestAveragePrecision(doc, DEFAULT_CLASS_COUNT));

  const toggle = (label: string) =>
    setSelected((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]);

  const shown = ordered.filter((r) => selected.includes(r.label));

  return (
    <Card className="surface panel w-full">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-navy-200">Precision-recall curves - {doc.pr_curves.model}</CardTitle>
        <CardDescription className="mt-1 text-sm text-slate-400">
          {doc.pr_curves.strategy} on the held-out split. {formatInteger(doc.labels.length)} classes,
          each curve stored as {formatInteger(doc.pr_curves.max_points_per_class)} threshold points or
          fewer; nothing is smoothed or interpolated.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 p-5 pt-2">
        <div className="flex flex-wrap gap-1.5">
          {ordered.map((r) => {
            const active = selected.includes(r.label);
            const ap = curves[r.label]?.average_precision;
            return (
              <button
                key={r.label}
                type="button"
                aria-pressed={active}
                onClick={() => toggle(r.label)}
                className={`flex items-center gap-1.5 rounded border px-2 py-1 text-xs ${
                  active ? 'border-white/30 bg-white/10 text-white' : 'border-white/10 text-slate-400 hover:border-white/25'
                }`}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: active ? classColor(r.label) : '#475569' }}
                  aria-hidden="true"
                />
                {displayClass(r.label)}
                <span className="mono text-slate-400">{ap === undefined ? '—' : ap.toFixed(3)}</span>
              </button>
            );
          })}
        </div>

        {shown.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">
            No class selected - pick at least one to plot its curve.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={360}>
            <LineChart margin={{ top: 8, right: 16, bottom: 24, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                type="number"
                dataKey="recall"
                domain={[0, 1]}
                ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                tickFormatter={(v: number) => v.toFixed(1)}
                stroke="#64748b"
                label={{ value: 'Recall', position: 'insideBottom', offset: -12, fill: '#94a3b8', fontSize: 12 }}
              />
              <YAxis
                type="number"
                domain={[0, 1]}
                ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                stroke="#64748b"
                label={{ value: 'Precision', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 12 }}
              />
              <Tooltip
                formatter={(value, name) => [
                  typeof value === 'number' ? value.toFixed(3) : String(value),
                  displayClass(String(name ?? '')),
                ]}
                labelFormatter={(label) => `Recall ${Number(label).toFixed(3)}`}
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 6, fontSize: 12 }}
              />
              <Legend formatter={(value: string) => <span className="text-xs text-slate-300">{displayClass(value)}</span>} />
              {shown.map((r) => (
                <Line
                  key={r.label}
                  type="stepAfter"
                  data={curves[r.label].points}
                  dataKey="precision"
                  name={r.label}
                  stroke={classColor(r.label)}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
        <p className="text-xs text-slate-500">
          Default selection: the {DEFAULT_CLASS_COUNT} classes with the lowest average precision,
          because that is where the model is weakest. The number beside each class is its average
          precision over the full threshold list, not over the plotted subset.
        </p>
      </CardContent>
    </Card>
  );
}
