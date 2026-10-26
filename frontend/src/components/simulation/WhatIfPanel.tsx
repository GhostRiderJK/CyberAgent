import { useMemo, useState } from 'react';
import { runSimulation } from '@/simulation/engine';
import type { Host, SimResult } from '@/simulation/types';

interface Props {
  /** The pristine baseline network (createTopology) - toggles start from this. */
  baselineHosts: Host[];
  /** The currently active topology, shown in the cards. */
  hosts: Host[];
  latestResult: SimResult | null;
  afterResult: SimResult | null;
  seed: number;
  timesteps: number;
  onTopologyChange: (hosts: Host[]) => void;
  onRerun: (result: SimResult, topology: Host[]) => void;
}

type DefenseKey = 'mfa' | 'edr' | 'firewall' | 'patched';
const DEFENSES: DefenseKey[] = ['mfa', 'edr', 'firewall', 'patched'];

interface HostEdit {
  defenses: Record<DefenseKey, boolean>;
  vulns: Record<string, boolean>;
}

function initialState(hosts: Host[]): Record<string, HostEdit> {
  const map: Record<string, HostEdit> = {};
  for (const h of hosts) {
    map[h.id] = {
      defenses: { mfa: h.defenses.mfa, edr: h.defenses.edr, firewall: h.defenses.firewall, patched: h.defenses.patched },
      vulns: Object.fromEntries(h.vulnerabilities.map(v => [v, true])),
    };
  }
  return map;
}

const METRICS = [
  ['compromiseRate', 'Hosts compromised'],
  ['successRate', 'Attacker success'],
  ['detectionRate', 'Detection'],
] as const;

export default function WhatIfPanel({ baselineHosts, hosts, latestResult, afterResult, seed, timesteps, onTopologyChange, onRerun }: Props) {
  const initial = useMemo(() => initialState(baselineHosts), [baselineHosts]);
  const [edits, setEdits] = useState<Record<string, HostEdit>>({});
  const state = { ...initial, ...edits };

  const toggleDefense = (hostId: string, key: DefenseKey) => {
    const cur = state[hostId];
    setEdits(e => ({ ...e, [hostId]: { ...cur, defenses: { ...cur.defenses, [key]: !cur.defenses[key] } } }));
  };

  const toggleVuln = (hostId: string, cve: string) => {
    const cur = state[hostId];
    setEdits(e => ({ ...e, [hostId]: { ...cur, vulns: { ...cur.vulns, [cve]: !cur.vulns[cve] } } }));
  };

  const reset = () => {
    setEdits({});
    onTopologyChange(baselineHosts.map(h => ({ ...h, defenses: { ...h.defenses }, vulnerabilities: [...h.vulnerabilities] })));
  };

  const applyAndRerun = () => {
    const topology: Host[] = hosts.map(h => {
      const e = state[h.id] ?? initial[h.id];
      const currentVulns = new Set(h.vulnerabilities);
      const vulns = Object.keys(e.vulns).filter(v => currentVulns.has(v) && e.vulns[v]);
      return { ...h, defenses: { ...e.defenses }, vulnerabilities: vulns };
    });
    onTopologyChange(topology.map(h => ({ ...h, defenses: { ...h.defenses }, vulnerabilities: [...h.vulnerabilities] })));
    onRerun(runSimulation(topology, { timesteps, seed, followersPerArchetype: 1 }), topology);
  };

  const runningComparison = latestResult && afterResult === null;

  return (
    <section className="glass panel p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">What-if analysis</p>
          <h3 className="mt-1 font-display text-xl font-semibold">Tune the network, re-run the same seed</h3>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn" onClick={reset}>Reset</button>
          <button type="button" className="btn" onClick={applyAndRerun} disabled={!latestResult}>Apply changes &amp; re-run</button>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {latestResult
          ? `Replays seed ${seed} at ${timesteps} timestep${timesteps > 1 ? 's' : ''} against your edited topology, so every delta is caused by the defense change only.`
          : 'Run a simulation first - the what-if re-run compares against your last result with the same seed.'}
      </p>

      <div className="mt-4 space-y-3">
        {hosts.map(host => {
          const st = state[host.id];
          const changed = JSON.stringify(st) !== JSON.stringify(initial[host.id]);
          return (
            <div key={host.id} className={`rounded-xl border p-3 ${changed ? 'border-cyan-400/40 bg-cyan-400/[.04]' : 'border-white/10 bg-white/[.02]'}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-slate-100">{host.name}</span>
                <span className="mono text-xs text-slate-500">{host.ip}</span>
                <span className="badge badge-cyan">{host.zone}</span>
                {changed && <span className="ml-auto text-[.68rem] font-bold uppercase tracking-wide text-cyan-300">edited</span>}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {DEFENSES.map(key => {
                  const on = st.defenses[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      role="switch"
                      aria-checked={on}
                      aria-label={`${host.name} ${key.toUpperCase()} defense`}
                      onClick={() => toggleDefense(host.id, key)}
                      className={`rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors ${on ? 'border-emerald-400/50 bg-emerald-400/10 text-emerald-300' : 'border-white/10 bg-white/[.03] text-slate-500'}`}
                    >
                      {key.toUpperCase()} {on ? 'on' : 'off'}
                    </button>
                  );
                })}
                {host.vulnerabilities.map(cve => {
                  const present = st.vulns[cve];
                  return (
                    <button
                      key={cve}
                      type="button"
                      role="switch"
                      aria-checked={present}
                      aria-label={`${host.name} ${cve}`}
                      onClick={() => toggleVuln(host.id, cve)}
                      className={`rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors ${present ? 'border-red-400/50 bg-red-400/10 text-red-300' : 'border-white/10 bg-white/[.03] text-slate-500'}`}
                    >
                      {cve} {present ? 'present' : 'removed'}
                    </button>
                  );
                })}
                {host.vulnerabilities.length === 0 && <span className="px-1 py-1 text-xs text-slate-600">no listed vulnerabilities</span>}
              </div>
            </div>
          );
        })}
      </div>

      {runningComparison && (
        <p className="mt-4 text-xs text-amber-300">Baseline for this comparison: your previous run. Click "Apply changes &amp; re-run" to compute deltas.</p>
      )}

      {latestResult && afterResult && (
        <div className="mt-4 rounded-xl border border-white/10 bg-white/[.03] p-3">
          <p className="text-xs font-bold uppercase tracking-[.1em] text-slate-400">Before vs after (same seed {afterResult.config.seed}, timesteps {afterResult.config.timesteps})</p>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
            {METRICS.map(([key, label]) => {
              const before = latestResult.stats[key];
              const after = afterResult.stats[key];
              const d = after - before;
              const good = key === 'detectionRate' ? d > 0 : d < 0;
              const cls = Math.abs(d) < 0.005 ? 'text-slate-400' : good ? 'text-emerald-300' : 'text-red-300';
              return (
                <div key={key} className="rounded-lg bg-slate-950/50 px-3 py-2">
                  <div className="text-[.68rem] uppercase tracking-wide text-slate-500">{label}</div>
                  <div className="mono mt-1 text-sm text-slate-200">{Math.round(before * 100)}% → {Math.round(after * 100)}%</div>
                  <div className={`mono text-xs font-bold ${cls}`}>{d >= 0 ? '+' : '−'}{Math.abs(Math.round(d * 100))} pp {Math.abs(d) < 0.005 ? 'no change' : good ? 'improved' : 'worsened'}</div>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-[.7rem] text-slate-500">
            Compromised hosts: {latestResult.stats.compromisedHosts.join(', ') || 'none'} → {afterResult.stats.compromisedHosts.join(', ') || 'none'}
          </p>
        </div>
      )}
    </section>
  );
}
