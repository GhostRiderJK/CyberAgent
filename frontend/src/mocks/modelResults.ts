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
    accuracy: 0.8686400959844025,
    precision: 0.9446983627010733,
    recall: 0.8686400959844025,
    f1: 0.8924253725553377,
    macroF1: 0.7452177714662462,
    trainingTime: 2.5,
    inferenceTimePer1000: 5.2
  },
  {
    model: 'Random Forest',
    accuracy: 0.9982377863597165,
    precision: 0.9982887085038108,
    recall: 0.9982377863597165,
    f1: 0.9982509950680217,
    macroF1: 0.9926809770276163,
    trainingTime: 12.3,
    inferenceTimePer1000: 8.7
  },
  {
    model: 'XGBoost',
    accuracy: 0.9988001949683176,
    precision: 0.9988117113191091,
    recall: 0.9988001949683176,
    f1: 0.9988040905468184,
    macroF1: 0.9943415198234774,
    trainingTime: 8.7,
    inferenceTimePer1000: 6.3
  },
  {
    model: 'LightGBM',
    accuracy: 0.9988939297364179,
    precision: 0.9989082289559982,
    recall: 0.9988939297364179,
    f1: 0.998898054630901,
    macroF1: 0.9952733969112718,
    trainingTime: 6.2,
    inferenceTimePer1000: 4.8
  },
  {
    model: 'MLP',
    accuracy: 0.9843462937272693,
    precision: 0.9848193265677314,
    recall: 0.9843462937272693,
    f1: 0.9844308078465956,
    macroF1: 0.9592421969086683,
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
