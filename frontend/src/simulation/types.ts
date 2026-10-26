export type Zone = 'DMZ' | 'INTERNAL' | 'CRITICAL';

export interface HostDefenses {
  mfa: boolean;
  edr: boolean;
  firewall: boolean;
  patched: boolean;
}

export interface Host {
  id: string;
  name: string;
  ip: string;
  zone: Zone;
  defenses: HostDefenses;
  vulnerabilities: string[];
}

export type HostStatus = 'clean' | 'scanned' | 'compromised' | 'isolated' | 'shielded';

export type Archetype = 'opportunist' | 'apt' | 'ransomware' | 'insider';
export type DefenderRole = 'soc_analyst' | 'incident_responder' | 'threat_hunter';

export type AttackerAction =
  | 'scan'
  | 'exploit_vuln'
  | 'exploit_local_vuln'
  | 'credential_dump'
  | 'lateral_move'
  | 'exfiltrate'
  | 'do_nothing';

export type DefenderAction =
  | 'monitor'
  | 'block_ip'
  | 'isolate_host'
  | 'deploy_edr'
  | 'patch'
  | 'do_nothing';

export interface Step {
  t: number;
  agentId: string;
  role: 'attacker' | 'defender';
  archetype?: Archetype;
  defenderRole?: DefenderRole;
  action: AttackerAction | DefenderAction;
  targetHostId?: string;
  exploitedVuln?: string;
  success: boolean;
  detected: boolean;
  mitreTechnique?: string;
  rationale: string;
}

export interface SimConfig {
  timesteps: number;
  seed: number;
  /** Attackers spawned per archetype (1 for a single run, 10 for swarm). */
  followersPerArchetype?: number;
}

export interface ArchetypeStats {
  agents: number;
  actions: number;
  successes: number;
  detections: number;
  hostsCompromised: number;
  exfiltrations: number;
}

export interface SimStats {
  totalActions: number;
  successRate: number;
  detectionRate: number;
  doNothingShare: number;
  compromiseRate: number;
  exfiltrated: boolean;
  compromisedHosts: string[];
}

export interface SimResult {
  config: Required<SimConfig>;
  steps: Step[];
  hostStatus: Record<string, HostStatus>;
  stats: SimStats;
  perArchetype: Record<Archetype, ArchetypeStats>;
}

export interface SwarmBatchSummary {
  batch: number;
  seed: number;
  compromiseRate: number;
  detectionRate: number;
  successRate: number;
}

export interface SwarmResult {
  config: Required<SimConfig>;
  totalAgentRuns: number;
  batches: SwarmBatchSummary[];
  converged: boolean;
  convergenceNote: string;
  perHostCompromise: Array<{ host: Host; rate: number }>;
  perArchetype: Array<ArchetypeStats & { archetype: Archetype; successRate: number; detectionRate: number; exfiltrationRate: number }>;
  topAttackPaths: Array<{ path: string[]; count: number }>;
  defenseEffectiveness: Array<{ defense: string; effect: string }>;
  vulnerabilityPriority: Array<{ cve: string; host: string; exploitCount: number; impact: number; priority: number }>;
  results: SimResult[];
}
