export interface ModelMetrics {
  model: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  macroF1: number;
  trainingTime: number; // seconds
  inferenceTimePer1000: number; // ms
}

export interface ModelComparison {
  metrics: ModelMetrics[];
  bestModel: string;
}

export const mockModelMetrics: ModelMetrics[] = [
  {
    model: 'Logistic Regression',
    accuracy: 0.82,
    precision: 0.80,
    recall: 0.78,
    f1: 0.79,
    macroF1: 0.75,
    trainingTime: 2.5,
    inferenceTimePer1000: 5.2
  },
  {
    model: 'Random Forest',
    accuracy: 0.89,
    precision: 0.88,
    recall: 0.86,
    f1: 0.87,
    macroF1: 0.85,
    trainingTime: 12.3,
    inferenceTimePer1000: 8.7
  },
  {
    model: 'XGBoost',
    accuracy: 0.91,
    precision: 0.90,
    recall: 0.89,
    f1: 0.895,
    macroF1: 0.88,
    trainingTime: 8.7,
    inferenceTimePer1000: 6.3
  },
  {
    model: 'LightGBM',
    accuracy: 0.92,
    precision: 0.91,
    recall: 0.90,
    f1: 0.905,
    macroF1: 0.89,
    trainingTime: 6.2,
    inferenceTimePer1000: 4.8
  },
  {
    model: 'MLP',
    accuracy: 0.85,
    precision: 0.84,
    recall: 0.83,
    f1: 0.835,
    macroF1: 0.81,
    trainingTime: 15.8,
    inferenceTimePer1000: 12.1
  }
];

export const mockModelComparison: ModelComparison = {
  metrics: mockModelMetrics,
  bestModel: 'LightGBM'
};

export interface ConfusionMatrixData {
  labels: string[];
  matrix: number[][];
}

export const mockConfusionMatrix: ConfusionMatrixData = {
  labels: ['BENIGN', 'DoS Hulk', 'PortScan', 'Web Attack Brute Force', 'Infiltration'],
  matrix: [
    [850, 30, 10, 5, 5],   // BENIGN
    [25, 700, 20, 10, 5],  // DoS Hulk
    [15, 10, 400, 15, 10], // PortScan
    [10, 5, 10, 300, 5],   // Web Attack Brute Force
    [5, 5, 5, 5, 200]      // Infiltration
  ]
};

export const mockPRCurveData = {
  benign: {
    recall: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    precision: [1.0, 0.95, 0.90, 0.85, 0.80, 0.75]
  },
  dosHulk: {
    recall: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    precision: [0.8, 0.82, 0.84, 0.86, 0.88, 0.90]
  },
  portScan: {
    recall: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    precision: [0.75, 0.78, 0.80, 0.82, 0.84, 0.86]
  }
};