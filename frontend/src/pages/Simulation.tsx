import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import WarGameReplay from '@/components/simulation/WarGameReplay';
import WhatIfPanel from '@/components/simulation/WhatIfPanel';
import { setDemoAlerts } from '@/state/demoAlertsStore';
import { buildDemoAlerts } from '@/state/demoAlerts';
import { runSimulation } from '@/simulation/engine';
import { runSwarm } from '@/simulation/swarm';
import { createTopology } from '@/simulation/topology';
import { recommendations, weakestPoints } from '@/simulation/recommendations';
import type { Host, SimResult, SwarmResult } from '@/simulation/types';

const ZONES = ['DMZ', 'INTERNAL', 'CRITICAL'] as const;
const ARCH_ORDER = ['opportunist', 'apt', 'ransomware', 'insider'] as const;
const ARCH_COLOR: Record<string, string> = { opportunist: '#f87171', apt: '#fb923c', ransomware: '#f472b6', insider: '#eab308' };

const pct = (v: number) => `${Math.round(v * 100)}%`;

function clampInt(v: string, min: number, max: number, fallback: number): number {
  const n = Math.trunc(Number(v));
  return Number.isFinite(n) ? Math.max(min, Math.min(max, n)) : fallback;
}

export default function SimulationPage() {
  const navigate = useNavigate();
  const [topology, setTopology] = useState<Host[]>(() => createTopology());
  const [baseline, setBaseline] = useState<Host[]>(topology);
  const [result, setResult] = useState<SimResult | null>(null);
  const [swarm, setSwarm] = useState<SwarmResult | null>(null);
  const [afterResult, setAfterResult] = useState<SimResult | null>(null);
  const [timestepInput, setTimestepInput] = useState('5');
  const [seedInput, setSeedInput] = useState('42');
  const [swarmOn, setSwarmOn] = useState(false);
  const [followersInput, setFollowersInput] = useState('10');
  const [batchesInput, setBatchesInput] = useState('2');
  const [demoCount, setDemoCount] = useState(0);
  const [demoHint, setDemoHint] = useState<string | null>(null);
  const [runToken, setRunToken] = useState(0);

  useEffect(() => {
    setBaseline(h => (h === topology ? h : topology));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runToken]);

  const timesteps = clampInt(timestepInput, 1, 20, 5);
  const seed = clampInt(seedInput, 0, 999999, 42);
  const followers = clampInt(followersInput, 1, 25, 10);
  const batches = clampInt(batchesInput, 1, 10, 2);

  const run = () => {
    setAfterResult(null);
    setDemoCount(0);
    setDemoHint(null);
    setRunToken(t => t + 1);
    if (swarmOn) {
      const sw = runSwarm({ timesteps, seed, followersPerArchetype: followers, batches });
      setSwarm(sw);
      setResult(sw.results[0]);
    } else {
      setSwarm(null);
      setResult(runSimulation(topology, { timesteps, seed }));
    }
  };

  const reset = () => {
    setResult(null);
    setSwarm(null);
    setAfterResult(null);
    setDemoCount(0);
    setDemoHint(null);
    setTimestepInput('5');
    setSeedInput('42');
    setSwarmOn(false);
    setFollowersInput('10');
    setBatchesInput('2');
    setTopology(createTopology());
    setRunToken(t => t + 1);
  };

  const sendToAlerts = () => {
    if (!result) return;
    const alerts = buildDemoAlerts(result, topology);
    if (alerts.length < 3) {
      setDemoHint('Not enough successful simulated breaches to build 3 demo flows.');
      return;
    }
    setDemoAlerts(alerts);
    setDemoCount(alerts.length);
    setDemoHint(null);
  };

  const recs = useMemo(() => (result ? recommendations(result, topology) : []), [result, topology]);
  const weak = useMemo(() => (result ? weakestPoints(result, topology) : []), [result, topology]);

  const statsTiles = result && [
    ['Attacker success', pct(result.stats.successRate), `${result.steps.filter(s => s.role === 'attacker' && s.success).length} of ${Object.values(result.perArchetype).reduce((a, p) => a + p.actions, 0)} attacker actions achieved their effect.`],
    ['Detection rate', pct(result.stats.detectionRate), 'Share of attacker actions flagged by defenders.'],
    ['No-op share', pct(result.stats.doNothingShare), 'Holding-position actions, kept under 10% by design.'],
    ['Hosts compromised', `${result.stats.compromisedHosts.length}/6`, result.stats.compromisedHosts.join(', ') || 'none'],
    ['Exfiltration', result.stats.exfiltrated ? 'YES' : 'no', result.stats.exfiltrated ? 'Data left the critical zone in this run.' : 'No successful exfiltration step in this run.'],
  ];

  return (
    <div className="space-y-6">
      <section>
        <p className="eyebrow">Adversary simulation</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-3xl font-semibold">Attack-swarm war game</h2>
            <p className="mt-1 text-sm text-slate-400">Deterministic rule-based agents fighting a fixed 6-host network. Everything here is simulated - no live traffic, no backend calls.</p>
          </div>
          <span className="badge badge-amber">Simulated — not live traffic</span>
        </div>
      </section>

      <section className="glass panel p-4">
        <div className="flex flex-wrap items-end gap-4">
          <button type="button" className="btn rounded-xl border-cyan-400/40 bg-cyan-400/10 font-semibold text-cyan-100" onClick={run}>▶ Run simulation</button>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            Timesteps (1–20)
            <input aria-label="Timesteps" inputMode="numeric" value={timestepInput} onChange={e => setTimestepInput(e.target.value)} onBlur={() => setTimestepInput(String(clampInt(timestepInput, 1, 20, 5)))} className="w-24 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            Seed
            <input aria-label="Random seed" inputMode="numeric" value={seedInput} onChange={e => setSeedInput(e.target.value)} onBlur={() => setSeedInput(String(clampInt(seedInput, 0, 999999, 42)))} className="w-28 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100" />
          </label>
          <label className="flex items-center gap-2 py-2 text-sm text-slate-300">
            <input type="checkbox" aria-label="Swarm mode" checked={swarmOn} onChange={e => setSwarmOn(e.target.checked)} className="h-4 w-4 accent-cyan-400" />
            Swarm mode
          </label>
          {swarmOn && (
            <>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Followers / archetype (1–25)
                <input aria-label="Followers per archetype" inputMode="numeric" value={followersInput} onChange={e => setFollowersInput(e.target.value)} onBlur={() => setFollowersInput(String(clampInt(followersInput, 1, 25, 10)))} className="w-24 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100" />
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Batches (1–10)
                <input aria-label="Batches" inputMode="numeric" value={batchesInput} onChange={e => setBatchesInput(e.target.value)} onBlur={() => setBatchesInput(String(clampInt(batchesInput, 1, 10, 2)))} className="w-24 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100" />
              </label>
            </>
          )}
          <div className="ml-auto flex gap-2">
            {demoCount > 0 && <span className="badge badge-amber self-center">{demoCount} demo flows sent to Alerts</span>}
            {result && (
              <button type="button" className="btn" onClick={sendToAlerts} title="Push 3-6 simulated breach flows into the Alerts table, tagged Simulated">Send to Alerts as demo flows</button>
            )}
            <button type="button" className="btn" onClick={reset}>Reset</button>
          </div>
        </div>
        {demoHint && <p className="mt-2 text-xs text-amber-300">{demoHint}</p>}
        <p className="mt-2 text-xs text-slate-500">Same seed + same timesteps + same network always produces the identical run.</p>
      </section>

      <section className="surface panel p-4 sm:p-6">
        <p className="eyebrow">Network topology</p>
        <div className="mt-3 space-y-3">
          {ZONES.map(zone => (
            <div key={zone} className="flex flex-col gap-2 lg:flex-row">
              <div className="mono shrink-0 self-start rounded-lg bg-white/5 px-2 py-1 text-[.65rem] font-bold uppercase tracking-[.12em] text-slate-400 lg:self-center">{zone}</div>
              <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {topology.filter(h => h.zone === zone).map(host => (
                  <div key={host.id} className="rounded-xl border border-white/10 bg-white/[.02] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-slate-100">{host.name}</span>
                      <span className="mono text-[.68rem] text-slate-500">{host.ip}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(['mfa', 'edr', 'firewall', 'patched'] as const).map(k => (
                        <span key={k} className={`rounded px-1.5 py-0.5 text-[.66rem] font-semibold ${host.defenses[k] ? 'bg-emerald-400/10 text-emerald-300' : 'bg-white/[.03] text-slate-600 line-through'}`}>{k.toUpperCase()}</span>
                      ))}
                    </div>
                    <div className="mono mt-2 text-[.68rem] text-red-300">{host.vulnerabilities.length ? host.vulnerabilities.join(', ') : 'no listed vulnerabilities'}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {!result && (
        <section className="glass panel p-10 text-center text-sm text-slate-400">
          No run yet. Click <span className="font-semibold text-cyan-200">Run simulation</span> to launch 4 attacker archetypes and 3 defender roles against this network.
        </section>
      )}

      {result && (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {statsTiles?.map(([label, value, note]) => (
              <div key={label as string} className="glass panel p-4">
                <div className="text-[.68rem] uppercase tracking-[.1em] text-slate-500">{label}</div>
                <div className="mono mt-1 text-2xl font-semibold text-slate-100">{value}</div>
                <div className="mt-1 text-[.7rem] leading-snug text-slate-500">{note}</div>
              </div>
            ))}
          </section>

          <section className="surface panel overflow-hidden">
            <div className="px-4 pt-4"><p className="eyebrow">Per-archetype results</p></div>
            <div className="mt-2 overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>Archetype</th><th>Agents</th><th>Actions</th><th>Success</th><th>Detected</th><th>Hosts breached</th><th>Exfiltrations</th></tr></thead>
                <tbody>
                  {ARCH_ORDER.map(arch => {
                    const a = result.perArchetype[arch];
                    return (
                      <tr key={arch}>
                        <td><span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: ARCH_COLOR[arch] }} /><span className="font-semibold text-slate-100">{arch}</span></td>
                        <td>{a.agents}</td>
                        <td>{a.actions}</td>
                        <td>{a.actions ? pct(a.successes / a.actions) : 'n/a'} ({a.successes})</td>
                        <td>{a.actions ? pct(a.detections / a.actions) : 'n/a'} ({a.detections})</td>
                        <td>{a.hostsCompromised}</td>
                        <td>{a.exfiltrations}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {swarm && (
            <section className="surface panel p-4 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="eyebrow">Swarm aggregate — {swarm.totalAgentRuns} agent runs across {batches} batch(es)</p>
                <span className={`badge ${swarm.converged ? 'badge-emerald' : 'badge-red'}`}>{swarm.converged ? 'stable' : 'not converged'}</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">{swarm.convergenceNote}</p>

              <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[.1em] text-slate-500">Per-host compromise rate</p>
                  <div className="mt-2 space-y-1.5">
                    {swarm.perHostCompromise.map(({ host, rate }) => (
                      <div key={host.id} className="flex items-center gap-3">
                        <span className="mono w-36 shrink-0 truncate text-xs text-slate-300">{host.name}</span>
                        <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-white/[.06]">
                          <div className={`h-full rounded-full ${rate > 0.5 ? 'bg-red-400' : rate > 0 ? 'bg-amber-400' : 'bg-emerald-400'}`} style={{ width: `${Math.max(rate * 100, rate > 0 ? 4 : 0)}%` }} />
                        </div>
                        <span className="mono w-12 text-right text-xs text-slate-300">{pct(rate)}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[.1em] text-slate-500">Top attack paths (successful action sequences)</p>
                    {swarm.topAttackPaths.length === 0 ? (
                      <p className="mt-1 text-xs text-slate-500">No attacker achieved any effect in these batches.</p>
                    ) : (
                      <ul className="mono mt-2 space-y-1 text-xs text-slate-300">
                        {swarm.topAttackPaths.map(p => <li key={p.path.join('>')}>{p.path.join(' → ')} <span className="text-slate-500">×{p.count}</span></li>)}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[.1em] text-slate-500">Defense effectiveness</p>
                    <ul className="mt-2 space-y-1 text-xs text-slate-400">
                      {swarm.defenseEffectiveness.map(d => <li key={d.defense}><span className="mono font-semibold text-slate-200">{d.defense}</span> — {d.effect}</li>)}
                    </ul>
                  </div>
                </div>
              </div>

              <div className="mt-4 overflow-x-auto">
                <p className="eyebrow">Vulnerability priority</p>
                {swarm.vulnerabilityPriority.length === 0 ? (
                  <p className="mt-1 text-xs text-slate-500">No CVE was successfully exploited in these batches - nothing to rank.</p>
                ) : (
                  <table className="data-table mt-2">
                    <thead><tr><th>CVE</th><th>Host</th><th>Successful exploits</th><th>Zone impact</th><th>Priority (rate × impact)</th></tr></thead>
                    <tbody>
                      {swarm.vulnerabilityPriority.map(v => (
                        <tr key={`${v.cve}@${v.host}`}>
                          <td className="mono">{v.cve}</td>
                          <td>{v.host}</td>
                          <td>{v.exploitCount}</td>
                          <td>{v.impact}/3</td>
                          <td className="mono font-semibold text-slate-100">{v.priority.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <p className="mt-3 text-[.7rem] text-slate-500">Batch 1 (seed {swarm.config.seed}) shown in the replay and step log below; all batches use seed + batch index.</p>
            </section>
          )}

          {(weak.length > 0 || recs.length > 0) && (
            <section className="glass panel p-4 sm:p-6">
              <p className="eyebrow">Findings &amp; recommendations</p>
              <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[.1em] text-slate-500">Weakest points</p>
                  {weak.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">No host was breached in this run.</p>
                  ) : (
                    <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
                      {weak.map(w => <li key={w.hostId}>• {w.detail}</li>)}
                    </ul>
                  )}
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[.1em] text-slate-500">Recommended controls</p>
                  <ul className="mt-2 space-y-1.5">
                    {recs.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                        <span className={`badge mt-0.5 shrink-0 ${r.priority === 'high' ? 'badge-red' : r.priority === 'medium' ? 'badge-amber' : 'badge-emerald'}`}>{r.priority}</span>
                        {r.text}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              {demoCount > 0 && (
                <button type="button" className="btn mt-3" onClick={() => navigate('/alerts')}>Open Alerts ({demoCount} demo flows) →</button>
              )}
            </section>
          )}

          <details className="surface panel p-4 sm:p-6">
            <summary className="cursor-pointer text-sm font-semibold text-slate-200">Step log — {result.steps.length} actions (seed {result.config.seed})</summary>
            <div className="mt-3 overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>t</th><th>Agent</th><th>Role</th><th>Action</th><th>Target</th><th>Outcome</th><th>Detected</th><th>MITRE</th><th>Rationale</th></tr></thead>
                <tbody>
                  {result.steps.map((s, i) => (
                    <tr key={i}>
                      <td className="mono">{s.t}</td>
                      <td className="mono text-xs" style={{ color: s.role === 'attacker' ? ARCH_COLOR[s.archetype ?? 'opportunist'] : '#22d3ee' }}>{s.agentId}</td>
                      <td className="text-xs">{s.role}</td>
                      <td className="text-xs font-semibold text-slate-100">{s.action.replace(/_/g, ' ')}</td>
                      <td className="mono text-xs">{s.targetHostId ?? '—'}</td>
                      <td><span className={`badge ${s.success ? 'badge-emerald' : 'badge-amber'}`}>{s.success ? 'success' : 'failed'}</span></td>
                      <td>{s.detected ? <span className="badge badge-cyan">yes</span> : <span className="text-xs text-slate-600">no</span>}</td>
                      <td className="mono text-[.68rem] text-slate-400">{s.mitreTechnique ?? '—'}</td>
                      <td className="max-w-72 text-xs text-slate-400">{s.rationale}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}

      <WarGameReplay key={runToken} hosts={topology} steps={result?.steps ?? []} hasResult={result !== null} />

      <WhatIfPanel
        baselineHosts={baseline}
        hosts={topology}
        latestResult={result}
        afterResult={afterResult}
        seed={seed}
        timesteps={timesteps}
        onTopologyChange={setTopology}
        onRerun={r => { setAfterResult(r); setDemoCount(0); setDemoHint(null); }}
      />
    </div>
  );
}
