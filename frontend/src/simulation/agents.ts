import type { Archetype, DefenderRole } from './types';

export const ARCHETYPES: Archetype[] = ['opportunist', 'apt', 'ransomware', 'insider'];
export const DEFENDER_ROLES: DefenderRole[] = ['soc_analyst', 'incident_responder', 'threat_hunter'];

export const ATTACKER_ACTIONS = [
  'scan', 'exploit_vuln', 'exploit_local_vuln', 'credential_dump',
  'lateral_move', 'exfiltrate', 'do_nothing',
] as const;

export const DEFENDER_ACTIONS = [
  'monitor', 'block_ip', 'isolate_host', 'deploy_edr', 'patch', 'do_nothing',
] as const;

/** Single place where actions map to MITRE ATT&CK technique labels. */
export const MITRE: Record<string, string> = {
  scan: 'T1595 Active Scanning',
  exploit_vuln: 'T1190 Exploit Public-Facing Application',
  exploit_local_vuln: 'T1068 Exploitation for Privilege Escalation',
  credential_dump: 'T1003 OS Credential Dumping',
  lateral_move: 'T1021 Remote Services',
  exfiltrate: 'T1041 Exfiltration Over C2 Channel',
  block_ip: 'DETECT Block',
  isolate_host: 'RESPOND Isolate',
};

export const ARCHETYPE_BLURB: Record<Archetype, string> = {
  opportunist: 'Low-skill scavenger: scans for easy wins and gives up on hardened targets.',
  apt: 'Patient and stealthy: works toward the critical zone step by step.',
  ransomware: 'Aggressive spreader: tries to maximise lateral movement once inside.',
  insider: 'Trusted-user threat: starts with a legitimate foothold and reaches for sensitive data.',
};

export const ACTION_RATIONALE: Record<string, string> = {
  scan: 'Reconnaissance: probe the perimeter for exposed services before committing to an exploit.',
  exploit_vuln: 'Remote exploitation of a known unpatched vulnerability on the target.',
  exploit_local_vuln: 'Have foothold but no admin; attempting local privilege escalation.',
  credential_dump: 'Harvest cached credentials to enable credential-based movement.',
  lateral_move: 'Reuse access to pivot into the adjacent network zone.',
  exfiltrate: 'Stage and exfiltrate sensitive data over the command channel.',
  do_nothing: 'Hold position this round to avoid tripping sensors.',
  monitor: 'Watch telemetry; raise detection confidence for everything in flight.',
  block_ip: 'Observed malicious traffic from an active foothold - block the source.',
  isolate_host: 'Confirmed compromise; remove the host from the network.',
  deploy_edr: 'Extend visibility: deploy endpoint detection on a soft target.',
  patch: 'Emergency patch cycle against the most-exploited vulnerability.',
};
