export interface InvestigationReport {
  flow_id: number;
  predicted_class: string;
  verdict: 'BENIGN' | 'MALICIOUS' | 'SUSPICIOUS' | 'UNCERTAIN';
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
  needs_human_review: boolean;
  evidence: Array<{
    claim: string;
    source_tool: string;
    source_value: string;
  }>;
  mitre_technique: string;
  recommended_actions: string[];
  limitations: string[];
}

export const mockInvestigationReport: InvestigationReport = {
  flow_id: 12345,
  predicted_class: 'DoS Hulk',
  verdict: 'MALICIOUS',
  severity: 'high',
  confidence: 0.92,
  needs_human_review: false,
  evidence: [
    {
      claim: "The ML model predicts flow 12345 is DoS Hulk with 92.0% confidence",
      source_tool: "predict_proba",
      source_value: "{\"flow_id\":12345,\"predicted_class\":\"DoS Hulk\",\"confidence\":0.92,\"class_probabilities\":{\"BENIGN\":0.03,\"DoS Hulk\":0.92,\"PortScan\":0.03,\"Web Attack Brute Force\":0.02}}"
    },
    {
      claim: "The most important feature is Total Fwd Packets with value 1250.00",
      source_tool: "explain_flow",
      source_value: "{\"flow_id\":12345,\"explanation\":[{\"feature\":\"Total Fwd Packets\",\"value\":1250.0,\"importance\":0.45},{\"feature\":\"Fwd Packet Length Max\",\"value\":800.0,\"importance\":0.30},{\"feature\":\"Flow Duration\",\"value\":120.5,\"importance\":0.15}]}"
    },
    {
      claim: "Found 15 related flows sharing source IP or destination port",
      source_tool: "find_related_flows",
      source_value: "{\"flow_id\":12345,\"source_ip\":\"192.168.1.100\",\"dest_port\":80,\"related_flows\":[{\"flow_id\":12346,\"source_ip\":\"192.168.1.100\",\"dest_ip\":\"10.0.0.1\",\"dest_port\":80,\"label\":\"DoS Hulk\"},{\"flow_id\":12347,\"source_ip\":\"192.168.1.100\",\"dest_ip\":\"10.0.0.2\",\"dest_port\":80,\"label\":\"DoS Hulk\"}],\"count_same_ip\":15,\"count_same_port\":15}"
    }
  ],
  mitre_technique: "T1498",
  recommended_actions: [
    "Monitor source IP 192.168.1.100 for additional suspicious activity",
    "Check destination port 80 for known vulnerabilities",
    "Block traffic from source IP if malicious intent is confirmed"
  ],
  limitations: [
    "Explanation is feature importance-based, not SHAP values",
    "Related flows analysis is simplified"
  ]
};

export const mockToolCalls = [
  { tool: "predict_proba", timestamp: "2023-11-01 10:30:01.123", status: "completed" },
  { tool: "explain_flow", timestamp: "2023-11-01 10:30:01.456", status: "completed" },
  { tool: "find_related_flows", timestamp: "2023-11-01 10:30:01.789", status: "completed" },
  { tool: "mitre_lookup", timestamp: "2023-11-01 10:30:02.012", status: "completed" }
];

export const mockShapData = [
  { feature: "Total Fwd Packets", value: 0.45 },
  { feature: "Fwd Packet Length Max", value: 0.30 },
  { feature: "Flow Duration", value: 0.15 },
  { feature: "Bwd Packet Length Min", value: -0.08 },
  { feature: "Fwd IAT Mean", value: -0.12 },
  { feature: "Packet Length Variance", value: 0.05 }
];