import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { api } from '@/services/api';
import type { InvestigationResult } from '@/models/apiModels';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';

interface ToolCallEvent {
  tool: string;
  kwargs: Record<string, string>;
  status: string;
  timestamp: number;
}

const DEFAULT_FLOW_ID = 0;

export default function InvestigationView() {
  const [flowId, setFlowId] = useState<number>(DEFAULT_FLOW_ID);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [toolCalls, setToolCalls] = useState<ToolCallEvent[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const runIdRef = useRef(0);

  const severityToBadgeVariant: Record<string, 'default' | 'destructive' | 'outline' | 'secondary'> = {
    low: 'secondary',
    medium: 'outline',
    high: 'destructive',
    critical: 'destructive',
  };
  const badgeFor = (value: string) => severityToBadgeVariant[value.toLowerCase()] ?? 'outline';

  const runInvestigation = async (id: number) => {
    const runId = ++runIdRef.current;
    setResult(null);
    setToolCalls([]);
    setError(null);
    setStatus('running');
    try {
      const stream = await api.investigateFlow({ flow_id: id });
      for await (const event of stream) {
        if (runId !== runIdRef.current) return; // stale run
        setResult(event);
        setToolCalls(event.tool_call_events ?? []);
        setStatus('idle');
      }
    } catch (e) {
      if (runId !== runIdRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
      setStatus('error');
    }
  };

  useEffect(() => {
    runInvestigation(flowId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shapData = React.useMemo(() => {
    const ev = result?.evidence.find((e) => e.source_tool === 'explain_flow');
    if (!ev) return [];
    try {
      const parsed = JSON.parse(ev.source_value);
      const names: string[] = parsed.feature_names ?? [];
      const values: number[] = parsed.shap_values ?? [];
      return names.map((feature, i) => ({ feature, value: values[i] ?? 0 }));
    } catch {
      return [];
    }
  }, [result]);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Evidence workspace</p>
          <h2 className="font-display mt-2 text-3xl font-semibold">Investigation report</h2>
          <p className="mt-1 text-sm text-slate-400">
            Live agent run over POST /investigate. The ML label is authoritative; the LLM report is
            grounded-checked against tool evidence.
          </p>
        </div>
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            runInvestigation(flowId);
          }}
        >
          <label className="text-sm text-slate-400" htmlFor="flow-id">Flow ID</label>
          <input
            id="flow-id"
            type="number"
            min={0}
            value={flowId}
            onChange={(e) => setFlowId(Number(e.target.value))}
            className="w-32 rounded border border-slate-600 bg-transparent px-2 py-1 text-sm"
          />
          <button
            type="submit"
            disabled={status === 'running'}
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white disabled:opacity-50"
          >
            {status === 'running' ? 'Investigating…' : 'Investigate'}
          </button>
        </form>
      </section>

      {status === 'error' && (
        <Card className="surface panel w-full border-red-500/40">
          <CardContent className="p-4 text-sm text-red-400">
            Investigation failed: {error}. Is the API server running (make api) and reachable at the
            configured VITE_API_BASE_URL?
          </CardContent>
        </Card>
      )}

      {status === 'running' && !result && (
        <Card className="surface panel w-full">
          <CardContent className="p-4 text-sm text-slate-400">
            Agent is gathering evidence… ({toolCalls.length} tool calls so far)
          </CardContent>
        </Card>
      )}

      {/* Report Summary */}
      <Card className="surface panel w-full">
        <CardHeader className="p-1">
          <CardTitle>Investigation Report{result ? ` — flow ${flowId}` : ''}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          {!result && status !== 'error' ? (
            <p className="text-sm text-muted-foreground">No report yet.</p>
          ) : result ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Predicted Class</p>
                  <p className="text-xl font-semibold">{result.predicted_class}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Severity</p>
                  <Badge variant={badgeFor(result.severity)}>{result.severity}</Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Confidence</p>
                  <p className="text-xl font-semibold">
                    {(result.confidence * 100).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Needs Human Review</p>
                  <span className={`px-2 py-1 rounded ${
                    result.needs_human_review
                      ? 'bg-red-100 text-red-800'
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {result.needs_human_review ? 'Yes' : 'No'}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">MITRE Technique</p>
                  <p className="text-lg font-semibold">{result.mitre_technique}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Grounding Verifier</p>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    result.grounding_check?.passed
                      ? 'bg-green-100 text-green-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {result.grounding_check?.passed ? 'All claims grounded' : 'Ungrounded claims — review'}
                  </span>
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Verdict</p>
                <p className="text-sm text-foreground">{result.verdict}</p>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      {/* SHAP Explanation Chart */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Feature Explanation (SHAP Values)</CardTitle>
          <CardDescription>
            Top features contributing to the prediction
          </CardDescription>
        </CardHeader>
        <CardContent>
          {shapData.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={shapData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="feature" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="value" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground">
              No explanation data for this run.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Tool Calls Timeline */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Tool Calls Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {toolCalls.length === 0 && (
              <p className="text-sm text-muted-foreground">No tool calls recorded yet.</p>
            )}
            {toolCalls.map((call, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="flex-shrink-0 h-2.5 w-2.5 rounded-full bg-blue-500" />
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium text-foreground">
                    {call.tool}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {JSON.stringify(call.kwargs)}
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date((call.timestamp ?? 0) * 1000).toLocaleTimeString()}
                  </p>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    call.status === 'completed'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {call.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Evidence Table */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableCaption>
                Evidence supporting the investigation verdict
              </TableCaption>
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Evidence</TableCell>
                  <TableCell>Source Tool</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(result?.evidence ?? []).map((evidence, index) => (
                  <TableRow key={index}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell className="max-w-[300px] break-words">{evidence.source_value}</TableCell>
                    <TableCell>{evidence.source_tool}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Recommended Actions */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Recommended Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {(result?.recommended_actions ?? []).map((action, index) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="flex-shrink-0">
                  <span className="inline-flex h-2.5 w-2.5 items-center justify-center rounded-sm bg-blue-500 text-white text-xs">
                    {index + 1}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-foreground">{action}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Limitations */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Limitations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {(result?.limitations ?? []).map((limitation, index) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="flex-shrink-0">
                  <span className="inline-flex h-2.5 w-2.5 items-center justify-center rounded-sm bg-yellow-500 text-white text-xs">
                    {index + 1}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-foreground">{limitation}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
