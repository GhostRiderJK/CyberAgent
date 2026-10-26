import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { formatConfidencePct, formatMilliseconds, formatSeconds } from '@/lib/format';
import { modelsRankedByMacroF1, type EvaluationReady } from '@/models/evaluation';

interface Props {
  doc: EvaluationReady;
}

export default function ModelComparisonTable({ doc }: Props) {
  const rows = modelsRankedByMacroF1(doc);
  const anyTrainingTime = rows.some((r) => r.metrics.training_time_s !== null);

  return (
    <Card className="surface panel w-full overflow-hidden">
      <CardHeader className="p-5 pb-2">
        <CardTitle className="text-navy-200">Model comparison</CardTitle>
        <CardDescription className="mt-1 text-sm text-slate-400">
          Selected model: <span className="font-semibold text-navy-200">{doc.best_model}</span> -{' '}
          {doc.selection_rule}. Precision, recall and F1 are support-weighted averages over the{' '}
          {doc.labels.length} classes; macro F1 weights every class equally.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-5 pt-2">
        <div className="overflow-x-auto">
          <table className="data-table w-full text-sm">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left">Model</th>
                <th className="px-4 py-3 text-right">Accuracy</th>
                <th className="px-4 py-3 text-right">Weighted precision</th>
                <th className="px-4 py-3 text-right">Weighted recall</th>
                <th className="px-4 py-3 text-right">Weighted F1</th>
                <th className="px-4 py-3 text-right">Macro F1</th>
                <th className="px-4 py-3 text-right">Training time</th>
                <th className="px-4 py-3 text-right">Inference / 1000 flows</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ model, metrics, isBest }) => (
                <tr key={model} className={isBest ? 'bg-cyan-400/5' : undefined}>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className={isBest ? 'font-semibold text-cyan-200' : 'text-slate-300'}>{model}</span>
                    {isBest && (
                      <span className="ml-2 rounded bg-cyan-400/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-cyan-200">
                        selected
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right mono">{formatConfidencePct(metrics.accuracy)}</td>
                  <td className="px-4 py-3 text-right mono">{formatConfidencePct(metrics.precision_weighted)}</td>
                  <td className="px-4 py-3 text-right mono">{formatConfidencePct(metrics.recall_weighted)}</td>
                  <td className="px-4 py-3 text-right mono">{formatConfidencePct(metrics.f1_weighted)}</td>
                  <td className="px-4 py-3 text-right mono">{formatConfidencePct(metrics.f1_macro)}</td>
                  <td className="px-4 py-3 text-right mono">
                    {anyTrainingTime ? formatSeconds(metrics.training_time_s) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right mono">{formatMilliseconds(metrics.inference_time_ms_per_1000)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!anyTrainingTime && (
          <p className="mt-3 text-xs text-slate-500">
            Training time shows “—” because no training log was available when the artifact was
            built. It is left blank rather than estimated.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
