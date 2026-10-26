import { Rng } from './rng';
import { createTopology, zoneDistance } from './topology';
import { ARCHETYPES, ACTION_RATIONALE, MITRE } from './agents';
import type {
  Archetype, AttackerAction, DefenderAction, DefenderRole, Host, HostStatus,
  SimConfig, SimResult, Step,
} from './types';

interface AttackerState {
  id: string;
  archetype: Archetype;
  hostId: string | null;
  admin: boolean;
  hasCreds: boolean;
  exfiltrated: boolean;
  compromisedSet: Set<string>;
  actions: number;
  successes: number;
  detections: number;
}

interface DefenderState {
  id: string;
  role: DefenderRole;
}

interface Decision {
  action: AttackerAction | DefenderAction;
  target?: Host;
  rationale?: string;
  exploitedVuln?: string;
}

const DETECT_BASE: Record<string, number> = {
  scan: 0.08, exploit_vuln: 0.15, exploit_local_vuln: 0.15,
  credential_dump: 0.2, lateral_move: 0.18, exfiltrate: 0.25,
};

export function initialHostStatus(hosts: Host[]): Record<string, HostStatus> {
  const status: Record<string, HostStatus> = {};
  for (const h of hosts) status[h.id] = 'clean';
  // The insider agent begins with a legitimate foothold on the workstation.
  status['workstation-01'] = 'compromised';
  return status;
}

/**
 * Apply one step's effects to a status map. Used by the engine while running
 * AND by the replay/consistency tests, so both views can never disagree.
 */
export function applyStep(statuses: Record<string, HostStatus>, step: Step): void {
  if (!step.success || !step.targetHostId) return;
  const cur = statuses[step.targetHostId];
  switch (step.action) {
    case 'scan':
      if (cur === 'clean') statuses[step.targetHostId] = 'scanned';
      break;
    case 'exploit_vuln':
    case 'lateral_move':
      statuses[step.targetHostId] = 'compromised';
      break;
    case 'deploy_edr':
      if (cur === 'clean' || cur === 'scanned' || cur === 'shielded') statuses[step.targetHostId] = 'shielded';
      break;
    case 'isolate_host':
    case 'block_ip':
      if (cur === 'compromised' || cur === 'scanned' || cur === 'clean' || cur === 'shielded') {
        statuses[step.targetHostId] = 'isolated';
      }
      break;
    default:
      break;
  }
}

export function foldSteps(hosts: Host[], steps: Step[]): Record<string, HostStatus> {
  const statuses = initialHostStatus(hosts);
  for (const s of steps) applyStep(statuses, s);
  return statuses;
}

function cloneHosts(hosts: Host[]): Host[] {
  return hosts.map(h => ({ ...h, defenses: { ...h.defenses }, vulnerabilities: [...h.vulnerabilities] }));
}

export function runSimulation(topology: Host[], config: SimConfig): SimResult {
  const timesteps = Math.max(1, Math.min(20, Math.trunc(config.timesteps)));
  const followers = Math.max(1, Math.min(25, Math.trunc(config.followersPerArchetype ?? 1)));
  const hosts = cloneHosts(topology.length ? topology : createTopology());
  const rng = new Rng(config.seed);
  const statuses = initialHostStatus(hosts);
  const steps: Step[] = [];

  const attackers: AttackerState[] = [];
  let idx = 0;
  for (const arch of ARCHETYPES) {
    for (let f = 0; f < followers; f++) {
      const insiderFoothold = arch === 'insider' && f === 0;
      attackers.push({
        id: `${arch}-${idx++}`,
        archetype: arch,
        hostId: insiderFoothold ? 'workstation-01' : null,
        admin: false,
        hasCreds: false,
        exfiltrated: false,
        compromisedSet: new Set(insiderFoothold ? ['workstation-01'] : []),
        actions: 0, successes: 0, detections: 0,
      });
    }
  }
  const defenders: DefenderState[] = [
    { id: 'soc_analyst-0', role: 'soc_analyst' },
    { id: 'incident_responder-1', role: 'incident_responder' },
    { id: 'threat_hunter-2', role: 'threat_hunter' },
  ];

  let monitorStreak = 0;
  let openDetections: Array<{ attackerId: string; hostId: string }> = [];

  const byId = new Map(hosts.map(h => [h.id, h]));
  const live = (h: Host) => statuses[h.id] !== 'isolated' && statuses[h.id] !== 'compromised';
  const vulnerableHosts = () => hosts.filter(h => h.vulnerabilities.length > 0 && !h.defenses.patched && statuses[h.id] !== 'isolated');

  function record(a: AttackerState | DefenderState, action: string, target: Host | undefined,
                  success: boolean, detected: boolean, t: number, extraRationale?: string,
                  exploitedVuln?: string): void {
    const step: Step = {
      t,
      agentId: a.id,
      role: 'archetype' in a ? 'attacker' : 'defender',
      ...(('archetype' in a) ? { archetype: a.archetype } : { defenderRole: a.role }),
      action: action as AttackerAction,
      targetHostId: target?.id,
      exploitedVuln,
      success,
      detected,
      mitreTechnique: MITRE[action],
      rationale: extraRationale ?? ACTION_RATIONALE[action] ?? action,
    };
    steps.push(step);
    applyStep(statuses, step);
  }

  // ---- attacker policy ------------------------------------------------
  function decideAttacker(a: AttackerState): Decision {
    if (rng.chance(0.03)) return { action: 'do_nothing' };
    const foothold = a.hostId ? byId.get(a.hostId) : undefined;

    if (!foothold) {
      const vulns = vulnerableHosts();
      if (a.archetype === 'apt') {
        const crit = vulns.filter(h => h.zone === 'CRITICAL');
        if (crit.length && rng.chance(0.5)) return { action: 'exploit_vuln', target: crit[0] };
      }
      if (a.archetype === 'opportunist') {
        const easy = vulns.filter(h => h.zone !== 'CRITICAL');
        if (easy.length && rng.chance(0.6)) return { action: 'exploit_vuln', target: rng.pick(easy) };
        return { action: 'scan', target: rng.pick(hosts.filter(live)) };
      }
      if (vulns.length && rng.chance(a.archetype === 'ransomware' ? 0.75 : 0.55)) {
        return { action: 'exploit_vuln', target: rng.pick(vulns) };
      }
      return { action: 'scan', target: rng.pick(hosts.filter(live)) };
    }

    // Has foothold
    if (a.archetype === 'ransomware') {
      const next = hosts.filter(h => zoneDistance(foothold.zone, h.zone) <= 1
        && (statuses[h.id] === 'clean' || statuses[h.id] === 'scanned' || statuses[h.id] === 'shielded'));
      if (!a.admin) return { action: 'exploit_local_vuln', target: foothold };
      if (next.length) return { action: 'lateral_move', target: rng.pick(next) };
      return { action: 'credential_dump', target: foothold };
    }
    if (a.archetype === 'insider') {
      if (!a.admin) return { action: 'exploit_local_vuln', target: foothold };
      if (!a.hasCreds) return { action: 'credential_dump', target: foothold };
      if (foothold.zone === 'CRITICAL') return { action: 'exfiltrate', target: foothold };
      const crit = hosts.filter(h => h.zone === 'CRITICAL' && (statuses[h.id] === 'clean' || statuses[h.id] === 'shielded'));
      const adj = crit.length ? rng.pick(crit)
        : rng.pick(hosts.filter(h => zoneDistance(foothold.zone, h.zone) <= 1 && statuses[h.id] !== 'compromised' && statuses[h.id] !== 'isolated'));
      if (adj) return { action: 'lateral_move', target: adj };
      return { action: 'scan', target: rng.pick(hosts.filter(live)) };
    }
    if (a.archetype === 'apt') {
      if (foothold.zone === 'CRITICAL' && a.hasCreds) return { action: 'exfiltrate', target: foothold };
      if (!a.hasCreds) return { action: 'credential_dump', target: foothold };
      const crit = hosts.filter(h => zoneDistance(h.zone, 'CRITICAL') === 0 && statuses[h.id] !== 'compromised' && statuses[h.id] !== 'isolated');
      const toward = crit.length ? rng.pick(crit)
        : rng.pick(hosts.filter(h => zoneDistance(foothold.zone, h.zone) === 1 && statuses[h.id] !== 'compromised' && statuses[h.id] !== 'isolated'));
      if (toward) return { action: 'lateral_move', target: toward };
      return { action: 'scan', target: foothold, rationale: 'Re-scan current position for missed paths.' };
    }
    // opportunist with foothold
    if (!a.hasCreds && rng.chance(0.6)) return { action: 'credential_dump', target: foothold };
    const soft = hosts.filter(h => zoneDistance(foothold.zone, h.zone) <= 1
      && (statuses[h.id] === 'clean' || statuses[h.id] === 'scanned') && !h.defenses.edr);
    if (soft.length && rng.chance(0.55)) return { action: 'lateral_move', target: rng.pick(soft) };
    if (vulnerableHosts().length && rng.chance(0.4)) return { action: 'exploit_vuln', target: rng.pick(vulnerableHosts()) };
    return { action: 'scan', target: rng.pick(hosts.filter(live)) };
  }

  function execAttacker(a: AttackerState, d: Decision, t: number): void {
    const action = d.action as AttackerAction;
    a.actions++;
    if (action === 'do_nothing') {
      record(a, action, undefined, false, false, t);
      return;
    }
    const target = d.target ?? rng.pick(hosts.filter(live));
    if (!target) {
      record(a, action, undefined, false, false, t, 'No viable target remains; action aborted.');
      return;
    }
    let success = false;
    let detectP = DETECT_BASE[action] ?? 0.1;
    let rationale = d.rationale;

    switch (action) {
      case 'scan':
        success = true;
        break;
      case 'exploit_vuln': {
        const vuln = target.vulnerabilities[0];
        if (target.defenses.patched || !vuln) {
          success = false;
          rationale = `No exploitable path on ${target.name}: vulnerability surface is patched or absent.`;
          detectP += 0.05;
        } else {
          let p = 0.6;
          if (target.defenses.firewall && !a.hostId) p -= 0.18;
          if (target.defenses.edr) { p -= 0.12; detectP += 0.2; }
          success = rng.chance(p);
          if (success) {
            a.hostId = target.id;
            a.admin = false;
            a.hasCreds = false;
            a.compromisedSet.add(target.id);
          }
          d = { ...d, exploitedVuln: vuln };
        }
        break;
      }
      case 'exploit_local_vuln':
        if (target.defenses.patched) {
          success = false;
          rationale = `Local escalation on ${target.name} failed: fully patched endpoints close the privilege-escalation path.`;
        } else {
          success = rng.chance(0.55);
          if (success) a.admin = true;
        }
        detectP += target.defenses.edr ? 0.2 : 0;
        break;
      case 'credential_dump':
        success = rng.chance(target.defenses.edr ? 0.35 : 0.55);
        if (success) a.hasCreds = true;
        detectP += target.defenses.edr ? 0.25 : 0;
        break;
      case 'lateral_move': {
        if (!a.hasCreds && !a.admin) {
          success = false;
          rationale = `Lateral pivot to ${target.name} failed: no stolen credentials or admin rights to reuse.`;
        } else if (target.defenses.mfa) {
          success = false;
          rationale = `MFA on ${target.name} blocked credential-based lateral movement.`;
          detectP += 0.05;
        } else {
          let p = 0.5;
          if (target.defenses.edr) { p -= 0.2; detectP += 0.2; }
          if (target.defenses.firewall && zoneDistance(target.zone, 'DMZ') === 0) p -= 0.1;
          success = rng.chance(p);
          if (success) {
            a.hostId = target.id;
            a.compromisedSet.add(target.id);
          }
        }
        break;
      }
      case 'exfiltrate': {
        if (target.zone !== 'CRITICAL') {
          success = false;
          rationale = `No sensitive data staging found on ${target.name}; exfiltration aborted.`;
        } else {
          let p = 0.65;
          if (target.defenses.edr) { p -= 0.2; detectP += 0.2; }
          success = rng.chance(p);
          if (success) a.exfiltrated = true;
        }
        break;
      }
    }

    const boost = monitorStreak > 0 ? 0.07 : 0;
    const detected = rng.chance(Math.min(0.9, detectP + boost));
    if (success) a.successes++;
    if (detected) {
      a.detections++;
      if (target) openDetections.push({ attackerId: a.id, hostId: target.id });
    }
    record(a, action, target, success, detected, t, rationale, d.exploitedVuln);
  }

  // ---- defender policy --------------------------------------------------
  function decideDefender(df: DefenderState): Decision {
    const recent = openDetections.filter(o => o.hostId && statuses[o.hostId] === 'compromised');
    const anyOpen = openDetections.length > 0;
    if (df.role === 'soc_analyst') {
      const badIp = anyOpen && rng.chance(0.4) ? openDetections[openDetections.length - 1] : null;
      if (badIp) return { action: 'block_ip', target: byId.get(badIp.hostId) };
      if (rng.chance(0.7)) return { action: 'monitor' };
      return { action: 'deploy_edr', target: rng.pick(hosts.filter(h => statuses[h.id] === 'clean' && !h.defenses.edr)) };
    }
    if (df.role === 'incident_responder') {
      const compromised = hosts.filter(h => statuses[h.id] === 'compromised'
        && recent.some(r => r.hostId === h.id));
      if (compromised.length) return { action: 'isolate_host', target: rng.pick(compromised) };
      if (recent.length) {
        const byHost = recent[recent.length - 1];
        if (statuses[byHost.hostId] !== 'isolated') return { action: 'isolate_host', target: byId.get(byHost.hostId) };
      }
      const soft = hosts.filter(h => statuses[h.id] === 'clean' && !h.defenses.edr);
      if (soft.length && rng.chance(0.6)) return { action: 'deploy_edr', target: rng.pick(soft) };
      return { action: 'monitor', target: undefined, rationale: 'No confirmed compromise yet; keep watching telemetry.' };
    }
    // threat_hunter
    const exploited = hosts.filter(h => h.vulnerabilities.length > 0 && !h.defenses.patched
      && steps.some(s => s.success && s.action === 'exploit_vuln' && s.targetHostId === h.id));
    if (exploited.length && rng.chance(0.5)) return { action: 'patch', target: rng.pick(exploited) };
    const shieldTargets = hosts.filter(h => (statuses[h.id] === 'clean' || statuses[h.id] === 'scanned') && !h.defenses.edr);
    if (shieldTargets.length && rng.chance(0.5)) return { action: 'deploy_edr', target: rng.pick(shieldTargets) };
    return { action: 'monitor' };
  }

  function execDefender(df: DefenderState, d: Decision, t: number): void {
    const action = d.action as DefenderAction;
    if (action === 'do_nothing') {
      record(df, action, undefined, false, false, t);
      return;
    }
    let success = true;
    let rationale = d.rationale;
    const target = d.target;

    if (action === 'block_ip' || action === 'isolate_host') {
      if (!target || (statuses[target.id] !== 'compromised' && statuses[target.id] !== 'scanned'
          && statuses[target.id] !== 'clean' && statuses[target.id] !== 'shielded')) {
        success = false;
        rationale = 'No confirmed malicious activity to respond to this round.';
      } else {
        const stuck = attackers.find(a => a.hostId === target.id);
        if (stuck) { stuck.hostId = null; stuck.admin = false; stuck.hasCreds = false; }
      }
    }
    if (action === 'deploy_edr') {
      if (!target) {
        success = false;
        rationale = 'Every host already has endpoint coverage.';
      } else {
        target.defenses.edr = true;
      }
    }
    if (action === 'patch') {
      if (!target) {
        success = false;
        rationale = 'Nothing newly patchable was found.';
      } else {
        target.defenses.patched = true;
        target.vulnerabilities = [];
      }
    }
    if (action === 'monitor') monitorStreak++;
    if (success && (action === 'block_ip' || action === 'isolate_host')) {
      openDetections = openDetections.filter(o => o.hostId !== target?.id && o.attackerId !== undefined);
    }
    const detected = false;
    record(df, action, target, success, detected, t, rationale);
  }

  // ---- main loop --------------------------------------------------------
  for (let t = 1; t <= timesteps; t++) {
    monitorStreak = Math.max(0, monitorStreak - 1);
    for (const a of attackers) execAttacker(a, decideAttacker(a), t);
    for (const df of defenders) execDefender(df, decideDefender(df), t);
  }

  const totalActions = steps.length;
  const successes = steps.filter(s => s.success).length;
  const detections = steps.filter(s => s.detected).length;
  const doNothings = steps.filter(s => s.action === 'do_nothing').length;
  const compromisedHosts = hosts.filter(h => statuses[h.id] === 'compromised').map(h => h.id);

  const perArchetype = {} as SimResult['perArchetype'];
  for (const arch of ARCHETYPES) {
    const group = attackers.filter(a => a.archetype === arch);
    perArchetype[arch] = {
      agents: group.length,
      actions: group.reduce((s, a) => s + a.actions, 0),
      successes: group.reduce((s, a) => s + a.successes, 0),
      detections: group.reduce((s, a) => s + a.detections, 0),
      hostsCompromised: new Set(group.flatMap(a => [...a.compromisedSet])).size,
      exfiltrations: group.filter(a => a.exfiltrated).length,
    };
  }

  return {
    config: { timesteps, seed: config.seed, followersPerArchetype: followers },
    steps,
    hostStatus: { ...statuses },
    stats: {
      totalActions,
      successRate: totalActions ? successes / totalActions : 0,
      detectionRate: totalActions ? detections / totalActions : 0,
      doNothingShare: totalActions ? doNothings / totalActions : 0,
      compromiseRate: compromisedHosts.length / hosts.length,
      exfiltrated: compromisedHosts.length > 0 && steps.some(s => s.action === 'exfiltrate' && s.success),
      compromisedHosts,
    },
    perArchetype,
  };
}
