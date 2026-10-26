import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import ConfusionMatrixTable from '@/components/model-results/ConfusionMatrixTable';
import ModelComparisonTable from '@/components/model-results/ModelComparisonTable';
import PerClassTable from '@/components/model-results/PerClassTable';
import PrecisionRecallChart from '@/components/model-results/PrecisionRecallChart';
import { formatConfidencePct, formatDateTime, formatInteger } from '@/lib/format';
import { evaluation, isReady } from '@/models/evaluation';

export default function ModelResultsPage() {
  if (!isReady(evaluation)) {
    return (
      <div className="space-y-6">
        <section>
          <p className="eyebrow">Reproducible evaluation</p>
          <h2 className="font-display mt-2 text-3xl font-semibold">Model performance</h2>
        </section>
        <Card className="surface panel w-full">
          <CardHeader>
            <CardTitle>No evaluation artifact available</CardTitle>
            <CardDescription className="mt-1 text-sm text-slate-400">{evaluation.reason}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-300">
            <p>This page renders only from measured numbers, so it stays empty rather than showing sample data.</p>
            <p className="text-slate-400">Requires: {evaluation.requires}</p>
            <ol className="list-decimal space-y-1 pl-5 text-slate-300">
              <li>
                Build the artifact:<pre className="mono mt-1 inline-block rounded bg-black/30 px-2 py-1 text-xs">{evaluation.command}</pre>
              </li>
              <li>
                Copy it into the frontend:<pre className="mono mt-1 inline-block rounded bg-black/30 px-2 py-1 text-xs">npm run sync:eval</pre>
              </li>
            </ol>
          </CardContent>
        </Card>
      </div>
    );
  }

  const doc = evaluation;
  const holdoutFailed =
    doc.zero_day_holdout.length > 0 &&
    doc.zero_day_holdout.every((r) => r.accuracy === 0 && r.macro_f1 === 0);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Reproducible evaluation</p>
          <h2 className="font-display mt-2 text-3xl font-semibold">Model performance</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">{doc.dataset.note}</p>
        </div>
        <span className="badge badge-amber">Held-out evaluation, not operational traffic</span>
      </section>

      <Card className="surface panel w-full">
        <CardContent className="flex flex-wrap gap-x-6 gap-y-1 p-4 text-xs text-slate-400">
          <span>Source: <span className="mono text-slate-300">{doc.source_path ?? 'artifacts/eval/evaluation.json'}</span></span>
          <span>Generated: <span className="mono text-slate-300">{formatDateTime(doc.generated_at)}</span></span>
          <span>Git commit: <span className="mono text-slate-300">{doc.git_commit ?? 'unknown'}</span></span>
          <span>Test samples: <span className="mono text-slate-300">{formatInteger(doc.dataset.n_samples)}</span></span>
          <span>
            Split: <span className="mono text-slate-300">
              {doc.dataset.split.mode} {(doc.dataset.split.ratios ?? []).map((r) => Math.round(r * 100)).join('/')}% seed {doc.dataset.split.seed ?? '—'}
            </span>
          </span>
          <span>Dataset: <span className="mono text-slate-300">{doc.dataset.source}</span></span>
        </CardContent>
      </Card>

      <ModelComparisonTable doc={doc} />
      <ConfusionMatrixTable doc={doc} />
      <PerClassTable doc={doc} />
      <PrecisionRecallChart doc={doc} />

      {doc.n_holdout_samples > 0 && (
        <Card className="surface panel w-full overflow-hidden">
          <CardHeader className="p-5 pb-2">
            <CardTitle className="text-navy-200">Unseen-attack holdout</CardTitle>
            <CardDescription className="mt-1 text-sm text-slate-400">
              {formatInteger(doc.n_holdout_samples)} flows from {doc.zero_day_labels.join(', ')} - attack
              families deliberately kept out of training. This is the only number on the page measured
              on genuinely unseen attack traffic.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 p-5 pt-2">
            <div className="overflow-x-auto">
              <table className="data-table w-full text-sm">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left">Model</th>
                    <th className="px-4 py-3 text-right">Accuracy</th>
                    <th className="px-4 py-3 text-right">Macro F1</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.zero_day_holdout.map((row) => (
                    <tr key={row.model}>
                      <td className="px-4 py-3 text-slate-300">{row.model}</td>
                      <td className="px-4 py-3 text-right mono">{formatConfidencePct(row.accuracy)}</td>
                      <td className="px-4 py-3 text-right mono">{formatConfidencePct(row.macro_f1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {holdoutFailed && (
              <p className="rounded border border-amber-400/40 bg-amber-400/10 p-3 text-sm text-amber-200">
                Every model scored 0 on this holdout: none classified an unseen attack family
                correctly. The 99%+ numbers above describe a stratified split of the same capture
                days, not novel attacks.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="surface panel w-full">
        <CardHeader className="p-5 pb-2">
          <CardTitle className="text-navy-200">What these numbers do not show</CardTitle>
        </CardHeader>
        <CardContent className="p-5 pt-2">
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-400">
            {doc.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
