import MetricCard from '@/components/shared/MetricCard';
import GlassPanel from '@/components/shared/GlassPanel';
import { mockAlerts } from '@/mocks/alerts';

const Icon = ({children}:{children:string}) => <span aria-hidden="true" className="text-lg">{children}</span>;

const Overview = () => {
  const suspicious = mockAlerts.filter((alert) => alert.class !== 'BENIGN').length;
  const distribution = Object.entries(mockAlerts.reduce<Record<string,number>>((total, alert) => { total[alert.class] = (total[alert.class] ?? 0) + 1; return total; }, {}));
  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="eyebrow">Detection command center</p><h2 className="font-display mt-2 text-3xl font-semibold">Network flow intelligence</h2><p className="mt-2 max-w-2xl text-sm text-slate-400">A source-aware view of the flows currently available to this frontend.</p></div><span className="badge badge-amber">Fixture-backed overview</span></section>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><MetricCard title="Available flow alerts" value={mockAlerts.length} subtitle="Current local alert fixture" accentColor="cyan" icon={<Icon>◈</Icon>}/><MetricCard title="Suspicious classifications" value={suspicious} subtitle="Non-BENIGN fixture records" accentColor="amber" icon={<Icon>!</Icon>}/><MetricCard title="Best recorded macro F1" value="99.53%" subtitle="LightGBM held-out evaluation" accentColor="emerald" icon={<Icon>✓</Icon>}/><MetricCard title="Backend health" value="Unknown" subtitle="Checked only when the API connects" accentColor="cyan" icon={<Icon>·</Icon>}/></section>
      <section className="grid gap-5 xl:grid-cols-3"><GlassPanel className="surface xl:col-span-2 p-5"><div className="flex items-center justify-between"><div><p className="eyebrow">Classification mix</p><h3 className="mt-1 text-lg font-semibold">Available alert records</h3></div><span className="text-xs text-slate-500">Fixture data · no live trend inferred</span></div><div className="mt-6 space-y-4">{distribution.map(([name,count]) => <div key={name}><div className="mb-2 flex justify-between text-sm"><span className="text-slate-300">{name}</span><span className="mono text-cyan-200">{count} flow{count===1?'':'s'}</span></div><div className="h-2 overflow-hidden rounded-full bg-white/5"><div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-indigo-400" style={{width:`${(count/mockAlerts.length)*100}%`}}/></div></div>)}</div></GlassPanel><GlassPanel className="surface p-5"><p className="eyebrow">Operational guardrails</p><h3 className="mt-1 text-lg font-semibold">Data integrity</h3><ul className="mt-5 space-y-4 text-sm text-slate-400"><li><span className="mr-2 text-emerald-300">✓</span>Classifier output remains authoritative.</li><li><span className="mr-2 text-cyan-300">✓</span>Agent narratives are separate from predictions.</li><li><span className="mr-2 text-amber-300">!</span>Live backend status is unavailable until health check succeeds.</li></ul></GlassPanel></section>
      <GlassPanel className="surface overflow-hidden"><div className="flex items-center justify-between p-5"><div><p className="eyebrow">Recent records</p><h3 className="mt-1 text-lg font-semibold">Alert intake</h3></div><span className="text-xs text-slate-500">Explicitly labeled local fixtures</span></div><div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Flow</th><th>Classification</th><th>Confidence</th><th>Observed at</th></tr></thead><tbody>{mockAlerts.slice(0,4).map(alert=><tr key={alert.id}><td className="mono">FLOW-{String(alert.id).padStart(4,'0')}</td><td>{alert.class}</td><td>{(alert.confidence*100).toFixed(1)}%</td><td className="mono text-xs">{alert.timestamp}</td></tr>)}</tbody></table></div></GlassPanel>
    </div>
  );
};

export default Overview;
