export interface Alert {
  id: number;
  class: string;
  confidence: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  sourceIp: string;
  timestamp: string;
}

export const mockAlerts: Alert[] = [
  {
    id: 1,
    class: 'DoS Hulk',
    confidence: 0.95,
    severity: 'high',
    sourceIp: '192.168.1.100',
    timestamp: '2023-11-01 10:30:00',
  },
  {
    id: 2,
    class: 'PortScan',
    confidence: 0.87,
    severity: 'medium',
    sourceIp: '10.0.0.50',
    timestamp: '2023-11-01 10:32:00',
  },
  {
    id: 3,
    class: 'Web Attack Brute Force',
    confidence: 0.92,
    severity: 'high',
    sourceIp: '172.16.0.25',
    timestamp: '2023-11-01 10:35:00',
  },
  {
    id: 4,
    class: 'Infiltration',
    confidence: 0.78,
    severity: 'medium',
    sourceIp: '192.168.10.5',
    timestamp: '2023-11-01 10:40:00',
  },
  {
    id: 5,
    class: 'BENIGN',
    confidence: 0.99,
    severity: 'low',
    sourceIp: '192.168.1.101',
    timestamp: '2023-11-01 10:45:00',
  },
  {
    id: 6,
    class: 'DoS GoldenEye',
    confidence: 0.81,
    severity: 'medium',
    sourceIp: '10.0.0.51',
    timestamp: '2023-11-01 10:50:00',
  },
];