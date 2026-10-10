import * as React from "react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { mockModelMetrics, mockModelComparison, mockConfusionMatrix, mockPRCurveData } from '@/mocks/modelResults';

export default function ModelResultsPage() {
  // Convert PR curve data from arrays to objects for Recharts
  const benignPRData = mockPRCurveData.benign.recall.map((recall, index) => ({
    recall,
    precision: mockPRCurveData.benign.precision[index]
  }));

  const dosHulkPRData = mockPRCurveData.dosHulk.recall.map((recall, index) => ({
    recall,
    precision: mockPRCurveData.dosHulk.precision[index]
  }));

  const portScanPRData = mockPRCurveData.portScan.recall.map((recall, index) => ({
    recall,
    precision: mockPRCurveData.portScan.precision[index]
  }));

  // Combine data assuming same recall points for all classes (by index)
  const combinedData = benignPRData.map((point, index) => ({
    recall: point.recall,
    benign: point.precision,
    dosHulk: dosHulkPRData[index]?.precision ?? 0,
    portScan: portScanPRData[index]?.precision ?? 0,
  }));

  return (
    <div className="space-y-6"><section><p className="eyebrow">Reproducible evaluation</p><h2 className="font-display mt-2 text-3xl font-semibold">Model performance</h2><p className="mt-1 text-sm text-slate-400">Values below are sourced from the repository’s verified held-out evaluation artifact (53,342 samples), not operational traffic.</p></section>
      {/* Model Comparison Table */}
      <Card className="surface panel w-full overflow-hidden"><CardHeader className="p-5 pb-0">
          <CardTitle className="text-navy-200">Model Comparison</CardTitle>
          <CardDescription className="mt-1 text-sm text-slate-400">
            Held-out evaluation snapshot. LightGBM is selected by macro F1; this does not establish real-world generalization.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 p-5">
          <div className="overflow-x-auto">
            <Table className="w-full">
              <TableCaption className="text-navy-400 mb-4">
                Best model: <span className="font-semibold">{mockModelComparison.bestModel}</span>
              </TableCaption>
              <TableHead>
                <TableRow className="bg-navy-800 text-navy-50">
                  <TableCell className="px-4 py-3">Model</TableCell>
                  <TableCell className="px-4 py-3">Accuracy</TableCell>
                  <TableCell className="px-4 py-3">Precision</TableCell>
                  <TableCell className="px-4 py-3">Recall</TableCell>
                  <TableCell className="px-4 py-3">F1 Score</TableCell>
                  <TableCell className="px-4 py-3">Macro F1</TableCell>
                  <TableCell className="px-4 py-3">Training Time (s)</TableCell>
                  <TableCell className="px-4 py-3">Inference Time per 1000 (ms)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mockModelMetrics.map((metric, index) => {
                  const isBest = metric.model === mockModelComparison.bestModel;
                  return (
                    <TableRow key={index} className={isBest ? 'bg-navy-700/50' : 'border-t border-navy-700/50'}>
                      <TableCell className="px-4 py-3 font-medium {isBest ? 'text-navy-200' : 'text-navy-400'}">
                        {metric.model}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {(metric.accuracy * 100).toFixed(2)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {(metric.precision * 100).toFixed(2)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {(metric.recall * 100).toFixed(2)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {(metric.f1 * 100).toFixed(2)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {(metric.macroF1 * 100).toFixed(2)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {metric.trainingTime.toFixed(2)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-navy-400">
                        {metric.inferenceTimePer1000.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Confusion Matrix */}
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="text-navy-200">Confusion Matrix (Best Model)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="overflow-x-auto">
            <Table className="w-full">
              <TableCaption className="text-navy-400 mb-4">
                Rows: Actual class, Columns: Predicted class
              </TableCaption>
              <TableHead>
                <TableRow className="bg-navy-800 text-navy-50">
                  <TableCell className="px-4 py-3">&nbsp;</TableCell>
                  {mockConfusionMatrix.labels.map((label, index) => (
                    <TableCell key={index} className="px-4 py-3 text-navy-400">{label}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {mockConfusionMatrix.matrix.map((row, rowIdx) => (
                  <TableRow key={rowIdx} className="border-t border-navy-700/50 hover:bg-navy-800/50">
                    <TableCell className="px-4 py-3 font-medium text-navy-400">
                      {mockConfusionMatrix.labels[rowIdx]}
                    </TableCell>
                    {row.map((val, colIdx) => (
                      <TableCell key={colIdx} className="px-4 py-3 text-navy-400">
                        {val}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* PR Curves */}
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="text-navy-200">Precision-Recall Curves</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={combinedData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#6366f1" />
              <XAxis
                dataKey="recall"
                label={{ position: 'insideBottom', offset: -10 }}
                domain={[0, 1]}
              />
              <YAxis
                label={{ position: 'insideLeft', offset: -10, angle: -90 }}
                domain={[0, 1]}
              />
              <Tooltip
                labelFormatter={label => `${label}%`}
                formatter={(value) => {
                  const num = typeof value === 'number' ? value : 0;
                  return `${(num * 100).toFixed(2)}%`;
                }}
                contentStyle={{ backgroundColor: 'white', border: '1px solid #ccc', padding: '8px', borderRadius: '4px' }}
              />
              <Legend />
              {/* Benign PR Curve */}
              <Line
                type="monotone"
                dataKey="benign"
                stroke="#6366f1"
                name="Benign"
              />
              {/* DoS Hulk PR Curve */}
              <Line
                type="monotone"
                dataKey="dosHulk"
                stroke="#10b981"
                name="DoS Hulk"
              />
              {/* PortScan PR Curve */}
              <Line
                type="monotone"
                dataKey="portScan"
                stroke="#f59e0b"
                name="PortScan"
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
