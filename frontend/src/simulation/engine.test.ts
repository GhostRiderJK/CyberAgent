import { describe, expect, it } from 'vitest';

import { foldSteps, runSimulation } from './engine';
import { createTopology } from './topology';
import { runSwarm } from './swarm';
import { recommendations, weakestPoints } from './recommendations';

describe('engine determinism', () => {
  it('same seed gives identical result', () => {
    const a = runSimulation(createTopology(), { timesteps: 5, seed: 42 });
    const b = runSimulation(createTopology(), { timesteps: 5, seed: 42 });
    expect(a).toEqual(b);
  });

  it('different seed gives a different step log', () => {
    const a = runSimulation(createTopology(), { timesteps: 5, seed: 42 });
    const b = runSimulation(createTopology(), { timesteps: 5, seed: 7 });
    expect(a.steps).not.toEqual(b.steps);
  });
});

describe('defense semantics', () => {
  it('a patched host cannot be exploited via its vulnerability', () => {
    const hosts = createTopology();
    const web = hosts.find(h => h.id === 'web-server-01')!;
    web.defenses.patched = true;
    web.vulnerabilities = [];
    const result = runSimulation(hosts, { timesteps: 20, seed: 42 });
    const webBreaches = result.steps.filter(
      s => s.success && s.action === 'exploit_vuln' && s.targetHostId === 'web-server-01',
    );
    expect(webBreaches).toHaveLength(0);
  });

  it('MFA blocks credential-based lateral movement onto the host', () => {
    const result = runSimulation(createTopology(), { timesteps: 20, seed: 42 });
    for (const s of result.steps) {
      if (s.action === 'lateral_move' && s.targetHostId === 'prod-db-01') {
        expect(s.success).toBe(false);
      }
    }
  });
});

describe('action quality requirements', () => {
  it('do_nothing stays under 10% of all actions', () => {
    for (const seed of [1, 42, 99]) {
      const result = runSimulation(createTopology(), { timesteps: 10, seed });
      expect(result.stats.doNothingShare).toBeLessThan(0.1);
    }
  });

  it('success means effect: a successful exploit leaves the host compromised', () => {
    const result = runSimulation(createTopology(), { timesteps: 10, seed: 42 });
    const successes = result.steps.filter(s => s.role === 'attacker' && s.success
      && (s.action === 'exploit_vuln' || s.action === 'lateral_move') && s.targetHostId);
    expect(successes.length).toBeGreaterThan(0);
    for (const s of successes) {
      const fold = foldSteps(createTopology(), result.steps.filter(x => x.t <= s.t && x.agentId === s.agentId));
      expect(['compromised', 'isolated']).toContain(fold[s.targetHostId!]);
    }
  });
});

describe('statistical consistency', () => {
  it('compromise rates sit in [0,1] and match the step log', () => {
    const hosts = createTopology();
    const result = runSimulation(hosts, { timesteps: 5, seed: 42 });
    expect(result.stats.compromiseRate).toBeGreaterThanOrEqual(0);
    expect(result.stats.compromiseRate).toBeLessThanOrEqual(1);
    const refolded = foldSteps(hosts, result.steps);
    expect(refolded).toEqual(result.hostStatus);
    const compromised = Object.entries(refolded).filter(([, st]) => st === 'compromised').map(([id]) => id);
    expect(result.stats.compromisedHosts.sort()).toEqual(compromised.sort());
  });
});

describe('what-if direction', () => {
  it('patching web-server-01 lowers its compromise outcomes at the same seed', () => {
    const baseline = runSwarm({ timesteps: 5, seed: 42, followersPerArchetype: 10, batches: 2 });
    const baseWeb = baseline.perHostCompromise.find(p => p.host.id === 'web-server-01')!;

    const patchedHosts = createTopology();
    const web = patchedHosts.find(h => h.id === 'web-server-01')!;
    web.defenses.patched = true;
    web.vulnerabilities = [];
    let patchedHits = 0;
    let runs = 0;
    for (let b = 0; b < 2; b++) {
      const r = runSimulation(patchedHosts, { timesteps: 5, seed: 42 + b, followersPerArchetype: 10 });
      runs += 40;
      patchedHits += r.steps.filter(s => s.success && s.action === 'exploit_vuln' && s.targetHostId === 'web-server-01').length;
    }
    expect(patchedHits / runs).toBeLessThan(baseWeb.rate);
  });
});

describe('recommendations are derived', () => {
  it('every recommendation traces to a step that happened', () => {
    const hosts = createTopology();
    const result = runSimulation(hosts, { timesteps: 8, seed: 42 });
    for (const p of weakestPoints(result, hosts)) {
      if (p.cve) {
        expect(result.steps.some(s => s.success && s.exploitedVuln === p.cve && s.targetHostId === p.hostId)).toBe(true);
      }
    }
    const recs = recommendations(result, hosts);
    expect(recs.length).toBeGreaterThan(0);
  });
});
