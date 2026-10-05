export interface ReplaySession {
  id: string;
  startTime: string;
  endTime: string | null;
  totalFlows: number;
  maliciousFlows: number;
  benignFlows: number;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error';
}

export interface ReplayFlow {
  timestamp: string;
  flowId: number;
  prediction: string;
  confidence: number;
  investigation: {
    verdict: string;
    severity: string;
    evidenceCount: number;
  } | null;
}

export const mockReplaySession: ReplaySession = {
  id: 'replay_20231101_001',
  startTime: '2023-11-01 10:00:00',
  endTime: null,
  totalFlows: 1250,
  maliciousFlows: 87,
  benignFlows: 1163,
  status: 'running'
};

export const mockReplayFlows: ReplayFlow[] = [
  {
    timestamp: '2023-11-01 10:00:01',
    flowId: 1001,
    prediction: 'BENIGN',
    confidence: 0.98,
    investigation: null
  },
  {
    timestamp: '2023-11-01 10:00:02',
    flowId: 1002,
    prediction: 'DoS Hulk',
    confidence: 0.91,
    investigation: {
      verdict: 'MALICIOUS',
      severity: 'high',
      evidenceCount: 3
    }
  },
  {
    timestamp: '2023-11-01 10:00:03',
    flowId: 1003,
    prediction: 'PortScan',
    confidence: 0.76,
    investigation: {
      verdict: 'SUSPICIOUS',
      severity: 'medium',
      evidenceCount: 2
    }
  },
  {
    timestamp: '2023-11-01 10:00:04',
    flowId: 1004,
    prediction: 'BENIGN',
    confidence: 0.99,
    investigation: null
  },
  {
    timestamp: '2023-11-01 10:00:05',
    flowId: 1005,
    prediction: 'Web Attack Brute Force',
    confidence: 0.88,
    investigation: {
      verdict: 'MALICIOUS',
      severity: 'high',
      evidenceCount: 4
    }
  }
];

export const mockReplayStats = {
  flowsPerSecond: 12.5,
  avgConfidence: 0.87,
  threatsDetected: 87,
  falsePositives: 3,
  truePositives: 84
};