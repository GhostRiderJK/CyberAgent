import { runSimulation } from './engine';
import { createTopology } from './topology';
import { ARCHETYPES } from './agents';
import type { SimResult, SwarmResult, SwarmBatchSummary } from './types';

export interface SwarmConfig {
  timesteps: number;
  seed: number;
  followersPerArchetype: number;
  batches: number;
}

const IMPACT_BY_ZONE: Record<string, number> = { DMZ: 1, INTERNAL: 2, CRITICAL: 3 };

export function runSwarm(cfg: SwarmConfig): SwarmResult {
  const results: SimResult[] = [];
  for (let b = 0; b < cfg.batches; b++) {
    results.push(runSimulation(createTopology(), {
      timesteps: cfg.timesteps,
      seed: cfg.seed + b,
      followersPerArchetype: cfg.followersPerArchetype,
    }));
  }

  const hosts = createTopology();
  const totalAgentRuns = cfg.followersPerArchetype * ARCHETYPES.length * cfg.batches;

  const perHostCompromise = hosts.map(host => {
    let n = 0;
    for (const r of results) for (const s of r.steps) {
      if (s.success && (s.action === 'exploit_vuln' || s.action === 'lateral_move') && s.targetHostId === host.id) n++;
    }
    return { host, rate: totalAgentRuns ? Math.min(1, n / totalAgentRuns) : 0 };
  });

  const perArchetype = ARCHETYPES.map(arch => {
    const agg = { agents: 0, actions: 0, successes: 0, detections: 0, hostsCompromised: 0, exfiltrations: 0 };
    for (const r of results) {
      const a = r.perArchetype[arch];
      agg.agents += a.agents; agg.actions += a.actions; agg.successes += a.successes;
      agg.detections += a.detections; agg.hostsCompromised += a.hostsCompromised;
      agg.exfiltrations += a.exfiltrations;
    }
    return {
      archetype: arch, ...agg,
      successRate: agg.actions ? agg.successes / agg.actions : 0,
      detectionRate: agg.actions ? agg.detections / agg.actions : 0,
      exfiltrationRate: agg.agents ? agg.exfiltrations / agg.agents : 0,
    };
  });

  const livePaths = new Map<string, string[]>();
  for (const r of results) for (const s of r.steps) {
    if (s.role === 'attacker' && s.success && s.action !== 'do_nothing') {
      const key = `${s.archetype}:${s.agentId}`;
      const arr = livePaths.get(key);
      if (arr) arr.push(s.action); else livePaths.set(key, [s.action]);
    }
  }
  const topPaths: Array<{ path: string[]; count: number }> = [];
  for (const [, actions] of livePaths) {
    const seq: string[] = [];
    for (const a of actions) if (a !== seq[seq.length - 1]) seq.push(a);
    topPaths.push({ path: seq, count: 1 });
  }
  const merged = new Map<string, { path: string[]; count: number }>();
  for (const p of topPaths) {
    const k = p.path.join('>');
    merged.set(k, { path: p.path, count: (merged.get(k)?.count ?? 0) + 1 });
  }
  const topAttackPaths = [...merged.values()].sort((a, b) => b.count - a.count).slice(0, 5);

  // Defense effectiveness: compare per-host compromise when that defense exists.
  const defenseEffectiveness = (['edr', 'firewall', 'mfa', 'patched'] as const).map(defense => {
    let withDef = 0, withDefHits = 0, without = 0, withoutHits = 0;
    for (const { host, rate } of perHostCompromise) {
      if (host.defenses[defense]) { withDef++; withDefHits += rate; }
      else { without++; withoutHits += rate; }
    }
    const a = withDef ? withDefHits / withDef : 0;
    const b = without ? withoutHits / without : 0;
    const delta = b - a;
    return {
      defense,
      effect: withDef === 0 || without === 0
        ? `insufficient spread of this control to measure (${Math.round(a * 100)}% vs n/a)`
        : `hosts with it averaged ${Math.round(a * 100)}% compromise vs ${Math.round(b * 100)}% without (~${delta >= 0 ? '-' : '+'}${Math.abs(Math.round(delta * 100))}pp)`,
    };
  });

  const vulnTally = new Map<string, { host: string; exploitCount: number; zone: string }>();
  for (const r of results) for (const s of r.steps) {
    if (s.action === 'exploit_vuln' && s.success && s.exploitedVuln) {
      const key = `${s.exploitedVuln}@${s.targetHostId}`;
      const cur = vulnTally.get(key) ?? { host: s.targetHostId!, exploitCount: 0, zone: hosts.find(h => h.id === s.targetHostId)?.zone ?? 'DMZ' };
      cur.exploitCount++;
      vulnTally.set(key, cur);
    }
  }
  const vulnerabilityPriority = [...vulnTally.entries()].map(([key, v]) => {
    const cve = key.split('@')[0];
    const exploitRate = totalAgentRuns ? v.exploitCount / totalAgentRuns : 0;
    const impact = IMPACT_BY_ZONE[v.zone] ?? 1;
    return { cve, host: v.host, exploitCount: v.exploitCount, impact, priority: Math.round(exploitRate * impact * 100) / 100 };
  }).sort((a, b) => b.priority - a.priority);

  const batches: SwarmBatchSummary[] = results.map((r, i) => ({
    batch: i, seed: cfg.seed + i,
    compromiseRate: r.stats.compromiseRate,
    detectionRate: r.stats.detectionRate,
    successRate: r.stats.successRate,
  }));

  let converged = true;
  if (cfg.batches >= 2) {
    const first = batches[0], last = batches[batches.length - 1];
    const drift = Math.max(
      Math.abs(first.compromiseRate - last.compromiseRate),
      Math.abs(first.detectionRate - last.detectionRate),
      Math.abs(first.successRate - last.successRate),
    );
    converged = drift < 0.05;
  }
  const convergenceNote = cfg.batches < 2
    ? 'Only one batch run - convergence cannot be assessed.'
    : converged
      ? 'Early and late batches differ by less than 5 percentage points - results are stable.'
      : 'Early and late batches differ by 5+ percentage points - the aggregate has NOT converged; increase batches.';

  return {
    config: { timesteps: cfg.timesteps, seed: cfg.seed, followersPerArchetype: cfg.followersPerArchetype },
    totalAgentRuns, batches, converged, convergenceNote,
    perHostCompromise, perArchetype, topAttackPaths, defenseEffectiveness,
    vulnerabilityPriority, results,
  };
}
