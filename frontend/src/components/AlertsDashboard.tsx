import { useMemo, useState } from 'react';
import { mockAlerts } from '@/mocks/alerts';

export default function AlertsDashboard() {
  const [query,setQuery] = useState('');
  const [severity,setSeverity] = useState('all');
  const alerts = useMemo(() => mockAlerts.filter(alert => (severity === 'all' || alert.severity === severity) && `${alert.id} ${alert.class} ${alert.sourceIp}`.toLowerCase().includes(query.toLowerCase())), [query,severity]);
  const color: Record<string,string> = {critical:'badge-red',high:'badge-red',medium:'badge-amber',low:'badge-emerald'};
  return (
    <div className="space-y-6">
      <section><p className="eyebrow">Alert triage</p><div className="mt-2 flex flex-wrap items-end justify-between gap-4"><div><h2 className="font-display text-3xl font-semibold">Network flow alerts</h2><p className="mt-1 text-sm text-slate-400">Local fixture records are clearly separated from API-derived alerts.</p></div><span className="badge badge-amber">Demo data</span></div></section>
      <section className="glass panel flex flex-col gap-3 p-4 lg:flex-row"><input aria-label="Search alerts" value={query} onChange={e=>setQuery(e.target.value)} className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600" placeholder="Search flow ID, classification, or source IP"/><select aria-label="Filter by severity" value={severity} onChange={e=>setSeverity(e.target.value)} className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-300"><option value="all">All severities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><div className="px-2 py-2 text-sm text-slate-500">{alerts.length} of {mockAlerts.length} records</div></section>
      <section className="surface panel overflow-hidden"><div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Flow ID</th><th>Classification</th><th>Model score</th><th>Severity</th><th>Source</th><th>Timestamp</th><th>Action</th></tr></thead><tbody>{alerts.map(alert=><tr key={alert.id}><td className="mono">FLOW-{String(alert.id).padStart(4,'0')}</td><td className="font-medium text-slate-100">{alert.class}</td><td>{(alert.confidence*100).toFixed(1)}%</td><td><span className={`badge ${color[alert.severity]}`}>{alert.severity}</span></td><td className="mono text-xs">{alert.sourceIp}</td><td className="mono text-xs">{alert.timestamp}</td><td><a href="/investigation" className="text-xs font-semibold text-cyan-300 hover:text-cyan-100">Investigate →</a></td></tr>)}{alerts.length===0&&<tr><td colSpan={7} className="p-10 text-center text-slate-500">No fixture records match these filters.</td></tr>}</tbody></table></div></section>
    </div>
  );
}
