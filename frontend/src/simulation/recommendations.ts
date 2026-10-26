import type { Host, SimResult } from './types';

export interface WeakPoint {
  hostId: string;
  hostName: string;
  cve?: string;
  exploitedBy: number;
  detail: string;
}

export interface Recommendation {
  text: string;
  priority: 'high' | 'medium' | 'low';
}

/** Everything here is derived strictly from the run's step log - nothing hardcoded. */
export function weakestPoints(result: SimResult, hosts: Host[]): WeakPoint[] {
  const tally = new Map<string, { cve?: string; agents: Set<string> }>();
  for (const s of result.steps) {
    if (!s.success || !s.targetHostId) continue;
    if (s.action !== 'exploit_vuln' && s.action !== 'lateral_move' && s.action !== 'exploit_local_vuln') continue;
    const key = s.targetHostId;
    const cur = tally.get(key) ?? { cve: s.exploitedVuln, agents: new Set<string>() };
    cur.agents.add(s.agentId);
    if (s.exploitedVuln) cur.cve = s.exploitedVuln;
    tally.set(key, cur);
  }
  return [...tally.entries()]
    .map(([hostId, v]) => {
      const host = hosts.find(h => h.id === hostId);
      return {
        hostId,
        hostName: host?.name ?? hostId,
        cve: v.cve,
        exploitedBy: v.agents.size,
        detail: v.cve
          ? `${hostId} was breached via ${v.cve} by ${v.agents.size} distinct attacker agent(s).`
          : `${hostId} was reached by ${v.agents.size} distinct attacker agent(s) after initial foothold.`,
      };
    })
    .sort((a, b) => b.exploitedBy - a.exploitedBy);
}

export function recommendations(result: SimResult, hosts: Host[]): Recommendation[] {
  const out: Recommendation[] = [];
  const points = weakestPoints(result, hosts);

  for (const p of points) {
    if (p.cve) {
      out.push({
        text: `Patch ${p.cve} on ${p.hostName} (exploited by ${p.exploitedBy} attacker agent${p.exploitedBy > 1 ? 's' : ''}).`,
        priority: p.exploitedBy >= 3 ? 'high' : 'medium',
      });
    } else if (p.exploitedBy >= 2) {
      const host = hosts.find(h => h.id === p.hostId);
      if (host && !host.defenses.mfa) {
        out.push({
          text: `Enforce MFA on ${p.hostName} (reached ${p.exploitedBy}x via lateral movement without credential challenge).`,
          priority: 'medium',
        });
      }
    }
  }

  const exfilHosts = new Set(result.steps.filter(s => s.success && s.action === 'exfiltrate').map(s => s.targetHostId));
  for (const hostId of exfilHosts) {
    const host = hosts.find(h => h.id === hostId);
    if (host && !host.defenses.edr) {
      out.push({ text: `Deploy EDR on ${host.name} - exfiltration succeeded from an endpoint without detection coverage.`, priority: 'high' });
    }
  }

  if (result.stats.exfiltrated && !out.some(r => r.text.startsWith('Deploy EDR'))) {
    out.push({ text: 'Restrict outbound paths from the critical zone; data left the network despite endpoint coverage.', priority: 'medium' });
  }
  const isolated = Object.entries(result.hostStatus).filter(([, st]) => st === 'isolated').length;
  if (isolated > 0) {
    out.push({ text: `${isolated} host(s) required isolation; review detection-to-response latency for those segments.`, priority: 'low' });
  }
  if (out.length === 0) {
    out.push({ text: 'No attacker action achieved its effect in this run - current controls held.', priority: 'low' });
  }
  return out;
}
