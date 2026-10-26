import { useEffect, useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { foldSteps } from '@/simulation/engine';
import type { Host, HostStatus, Step } from '@/simulation/types';

interface Props {
  hosts: Host[];
  steps: Step[];
  hasResult: boolean;
}

const STATUS_LABEL: Record<HostStatus, string> = {
  clean: 'Clean',
  scanned: 'Scanned',
  compromised: 'Compromised',
  isolated: 'Isolated',
  shielded: 'Shielded (EDR)',
};

function statusClass(st: HostStatus): string {
  switch (st) {
    case 'clean': return 'border-blue-400/60 text-blue-200';
    case 'scanned': return 'border-amber-400/70 text-amber-200';
    case 'compromised': return 'border-red-500 text-red-200 shadow-[0_0_18px_rgba(248,113,113,0.5)]';
    case 'isolated': return 'border-dashed border-slate-400 text-slate-300';
    case 'shielded': return 'border-emerald-400 text-emerald-200';
  }
}

function statusText(st: HostStatus): string {
  switch (st) {
    case 'clean': return 'text-blue-300';
    case 'scanned': return 'text-amber-300';
    case 'compromised': return 'text-red-300';
    case 'isolated': return 'text-slate-300';
    case 'shielded': return 'text-emerald-300';
  }
}

const SPEEDS = [0.5, 1, 2, 4];

export default function WarGameReplay({ hosts, steps, hasResult }: Props) {
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setIdx(cur => {
        if (cur >= steps.length) {
          setPlaying(false);
          return cur;
        }
        return cur + 1;
      });
    }, 1000 / speed);
    return () => window.clearInterval(id);
  }, [playing, speed, steps.length]);

  const statuses = useMemo(
    () => foldSteps(hosts, steps.slice(0, idx)),
    [hosts, steps, idx],
  );

  const agentColors = useMemo(() => {
    const map = new Map<string, string>();
    let a = 0;
    for (const s of steps) {
      if (map.has(s.agentId)) continue;
      map.set(s.agentId, s.role === 'attacker' ? ['#f87171', '#fb923c', '#f472b6', '#eab308'][a++ % 4] : '#22d3ee');
    }
    return map;
  }, [steps]);

  const currentStep = idx > 0 ? steps[idx - 1] : undefined;
  const activeHost = currentStep && currentStep.success ? currentStep.targetHostId : undefined;
  const zonedHosts = (['DMZ', 'INTERNAL', 'CRITICAL'] as const).map(zone => ({
    zone,
    list: hosts.filter(h => h.zone === zone),
  }));
  const atEnd = idx >= steps.length;

  const togglePlay = () => {
    if (!hasResult || steps.length === 0) return;
    if (!playing && idx >= steps.length) setIdx(0);
    setPlaying(p => !p);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === ' ') { e.preventDefault(); togglePlay(); return; }
    if (e.key === 'ArrowRight') { e.preventDefault(); setPlaying(false); setIdx(i => Math.min(steps.length, i + 1)); return; }
    if (e.key === 'ArrowLeft') { e.preventDefault(); setPlaying(false); setIdx(i => Math.max(0, i - 1)); return; }
    if (e.key === 'Home') { e.preventDefault(); setIdx(0); return; }
    if (e.key === 'End') { e.preventDefault(); setIdx(steps.length); }
  };

  if (!hasResult) {
    return (
      <section className="surface panel p-6">
        <p className="eyebrow">War-game replay</p>
        <div className="mt-4 flex min-h-24 items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-slate-500">
          Run a simulation to enable replay.
        </div>
      </section>
    );
  }

  return (
    <section className="surface panel p-4 sm:p-6" tabIndex={0} onKeyDown={onKeyDown} aria-label="War-game replay, use space and arrow keys to control playback">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow">War-game replay</p>
        <span className="badge badge-amber">Simulated — not live traffic</span>
      </div>

      <div className="mt-4 space-y-3">
        {zonedHosts.map(({ zone, list }) => (
          <div key={zone} className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
            <div className="mono shrink-0 self-start rounded-lg bg-white/5 px-2 py-1 text-[.65rem] font-bold uppercase tracking-[.12em] text-slate-400 sm:self-center">{zone}</div>
            <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {list.map(host => {
                const st = statuses[host.id];
                const isActive = host.id === activeHost;
                return (
                  <div
                    key={host.id}
                    className={`rounded-xl border-2 px-3 py-2 transition-colors ${statusClass(st)} ${isActive ? 'ring-2 ring-cyan-300' : ''}`}
                    aria-label={`${host.name}: ${STATUS_LABEL[st]}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold">{host.name}</span>
                      <span className={`whitespace-nowrap text-[.68rem] font-bold uppercase tracking-wide ${statusText(st)}`}>{STATUS_LABEL[st]}</span>
                    </div>
                    <div className="mono text-[.68rem] text-slate-500">{host.ip}</div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" className="btn" onClick={() => { setPlaying(false); setIdx(i => Math.max(0, i - 1)); }} disabled={idx === 0} aria-label="Step back">⏮ Step back</button>
        <button type="button" className="btn" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>{playing ? '⏸ Pause' : '▶ Play'}</button>
        <button type="button" className="btn" onClick={() => { setPlaying(false); setIdx(i => Math.min(steps.length, i + 1)); }} disabled={atEnd} aria-label="Step forward">Step forward ⏭</button>
        <label className="ml-1 flex items-center gap-2 text-xs text-slate-400">
          Speed
          <select aria-label="Playback speed" className="rounded-lg border border-white/10 bg-slate-950/60 px-2 py-1 text-sm text-slate-200" value={speed} onChange={e => setSpeed(Number(e.target.value))}>
            {SPEEDS.map(s => <option key={s} value={s}>{s}x</option>)}
          </select>
        </label>
        <span className="mono ml-auto text-sm text-slate-300">{idx}/{steps.length}</span>
      </div>

      <input
        type="range"
        aria-label="Timeline scrubber"
        min={0}
        max={steps.length}
        step={1}
        value={idx}
        onChange={e => { setPlaying(false); setIdx(Number(e.target.value)); }}
        className="mt-3 w-full accent-cyan-400"
      />

      {reducedMotion && <p className="mt-2 text-xs text-slate-500">Reduced-motion is on: auto-play is disabled, use Step back / Step forward.</p>}

      <div className="mt-4">
        {currentStep ? (
          <div className="rounded-xl border border-white/10 bg-white/[.03] p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mono rounded px-1.5 py-0.5 text-xs font-bold" style={{ background: `${agentColors.get(currentStep.agentId)}22`, color: agentColors.get(currentStep.agentId) }}>{currentStep.agentId}</span>
              <span className="font-semibold text-slate-100">{currentStep.action.replace(/_/g, ' ')}</span>
              {currentStep.targetHostId && <span className="text-slate-400">→ {currentStep.targetHostId}</span>}
              <span className={currentStep.success ? 'badge badge-emerald' : 'badge badge-amber'}>{currentStep.success ? 'effect achieved' : 'no effect'}</span>
              {currentStep.detected && <span className="badge badge-cyan">detected</span>}
              {currentStep.mitreTechnique && <span className="mono ml-auto text-xs text-slate-500">{currentStep.mitreTechnique}</span>}
            </div>
            <p className="mt-2 text-xs italic text-slate-400">{currentStep.rationale}</p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Idle — before the first action. Initial state shows the insider foothold on workstation-01.</p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-white/10 pt-3 text-[.7rem] text-slate-400">
        {(Object.keys(STATUS_LABEL) as HostStatus[]).map(st => (
          <span key={st} className="flex items-center gap-1.5">
            <span className={`inline-block h-3.5 w-3.5 rounded border-2 ${statusClass(st)}`} />
            {STATUS_LABEL[st]}
          </span>
        ))}
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: '#f87171' }} /> Attacker agent</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: '#22d3ee' }} /> Defender agent</span>
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded ring-2 ring-cyan-300" /> Active in this step</span>
      </div>
    </section>
  );
}
