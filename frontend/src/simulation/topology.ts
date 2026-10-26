import type { Host, Zone } from './types';

export const ZONES: Zone[] = ['DMZ', 'INTERNAL', 'CRITICAL'];

const noDef: Host['defenses'] = { mfa: false, edr: false, firewall: false, patched: false };

/** Fresh copy of the network - always call this, never mutate a shared instance. */
export function createTopology(): Host[] {
  return [
    { id: 'web-server-01', name: 'web-server-01', ip: '10.0.0.10', zone: 'DMZ',
      defenses: { ...noDef, firewall: true }, vulnerabilities: ['CVE-2024-7347'] },
    { id: 'mail-server-01', name: 'mail-server-01', ip: '10.0.0.20', zone: 'DMZ',
      defenses: { mfa: true, edr: false, firewall: true, patched: true }, vulnerabilities: [] },
    { id: 'workstation-01', name: 'workstation-01', ip: '10.0.1.10', zone: 'INTERNAL',
      defenses: { ...noDef, firewall: true }, vulnerabilities: ['CVE-2024-38077'] },
    { id: 'file-server-01', name: 'file-server-01', ip: '10.0.1.20', zone: 'INTERNAL',
      defenses: { ...noDef, patched: true }, vulnerabilities: [] },
    { id: 'prod-db-01', name: 'prod-db-01', ip: '10.0.2.10', zone: 'CRITICAL',
      defenses: { mfa: true, edr: true, firewall: true, patched: false }, vulnerabilities: ['CVE-2024-10978'] },
    { id: 'dc-01', name: 'dc-01', ip: '10.0.2.20', zone: 'CRITICAL',
      defenses: { mfa: true, edr: true, firewall: true, patched: true }, vulnerabilities: [] },
  ];
}

/** Zone adjacency: DMZ-INTERNAL and INTERNAL-CRITICAL are one hop apart. */
export function zoneDistance(a: Zone, b: Zone): number {
  return Math.abs(ZONES.indexOf(a) - ZONES.indexOf(b));
}
