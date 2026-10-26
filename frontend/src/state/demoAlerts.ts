import type { Alert } from '@/mocks/alerts';
import type { Host, SimResult } from '@/simulation/types';

/**
 * Optional bridge from the Simulation page to the Alerts table. Classes come
 * from the label set the ML model actually knows; source IPs are the simulated
 * attacker hosts. These records are tagged `simulated` and stay out of Model
 * Results.
 */
const CLASS_BY_ACTION: Record<string, string> = {
  exploit_vuln: 'Web Attack Brute Force',
  exploit_local_vuln: 'DoS Hulk',
  credential_dump: 'Infiltration',
  lateral_move: 'Infiltration',
  exfiltrate: 'DoS GoldenEye',
  scan: 'PortScan',
};

const SEVERITY_BY_ACTION: Record<string, Alert['severity']> = {
  exfiltrate: 'critical',
  lateral_move: 'high',
  exploit_vuln: 'high',
  exploit_local_vuln: 'high',
  credential_dump: 'medium',
  scan: 'medium',
};

export function buildDemoAlerts(result: SimResult, hosts: Host[]): Alert[] {
  const breaches = result.steps.filter(
    s => s.role === 'attacker' && s.success && s.action !== 'do_nothing' && s.targetHostId,
  );
  const byHost = new Map<string, (typeof breaches)[number]>();
  for (const b of breaches) if (!byHost.has(b.targetHostId!)) byHost.set(b.targetHostId!, b);

  const out: Alert[] = [];
  let serial = 0;
  for (const b of byHost.values()) {
    if (out.length >= 6) break;
    const host = hosts.find(h => h.id === b.targetHostId);
    if (!host) continue;
    serial++;
    out.push({
      id: 900 + result.config.seed % 90 + serial,
      class: CLASS_BY_ACTION[b.action] ?? 'PortScan',
      confidence: Math.min(0.99, 0.6 + 0.05 * b.t),
      severity: SEVERITY_BY_ACTION[b.action] ?? 'medium',
      sourceIp: host.ip,
      timestamp: `SIMULATED step ${b.t} (${b.agentId})`,
      simulated: true,
    });
  }
  return out;
}
