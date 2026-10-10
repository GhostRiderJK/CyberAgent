import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { mockInvestigationReport, mockToolCalls, mockShapData } from '@/mocks/investigation';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';

export default function InvestigationView() {
  const severityToBadgeVariant: Record<string, 'default' | 'destructive' | 'outline' | 'secondary'> = {
    low: 'secondary',
    medium: 'outline',
    high: 'destructive',
    critical: 'destructive',
  };

  return (
    <div className="space-y-6"><section className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">Evidence workspace</p><h2 className="font-display mt-2 text-3xl font-semibold">Investigation report</h2><p className="mt-1 text-sm text-slate-400">The current report is a labeled fixture. Streaming results remain available through the existing POST /investigate client.</p></div><span className="badge badge-amber">Fixture report</span></section>
      {/* Report Summary */}
      <Card className="surface panel w-full"><CardHeader className="p-1">
          <CardTitle>Investigation Report</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Predicted Class</p>
              <p className="text-xl font-semibold">{mockInvestigationReport.predicted_class}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Verdict</p>
              <Badge variant={severityToBadgeVariant[mockInvestigationReport.verdict]}>
                {mockInvestigationReport.verdict}
              </Badge>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Severity</p>
              <Badge variant={severityToBadgeVariant[mockInvestigationReport.severity]}>
                {mockInvestigationReport.severity}
              </Badge>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Confidence</p>
              <p className="text-xl font-semibold">
                {(mockInvestigationReport.confidence * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Needs Human Review</p>
              <span className={`px-2 py-1 rounded ${
                mockInvestigationReport.needs_human_review
                  ? 'bg-red-100 text-red-800'
                  : 'bg-green-100 text-green-800'
              }`}>
                {mockInvestigationReport.needs_human_review ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* SHAP Explanation Chart */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Feature Explanation (SHAP Values)</CardTitle>
          <CardDescription>
            Top features contributing to the prediction
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={mockShapData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="feature" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="value" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Tool Calls Timeline */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Tool Calls Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {mockToolCalls.map((call, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="flex-shrink-0 h-2.5 w-2.5 rounded-full bg-blue-500" />
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium text-foreground">
                    {call.tool}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {call.timestamp}
                  </p>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    {call.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Evidence Table */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableCaption>
                Evidence supporting the investigation verdict
              </TableCaption>
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Claim</TableCell>
                  <TableCell>Source Tool</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mockInvestigationReport.evidence.map((evidence, index) => (
                  <TableRow key={index}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell className="max-w-[300px] break-words">{evidence.claim}</TableCell>
                    <TableCell>{evidence.source_tool}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Recommended Actions */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Recommended Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {mockInvestigationReport.recommended_actions.map((action, index) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="flex-shrink-0">
                  <span className="inline-flex h-2.5 w-2.5 items-center justify-center rounded-sm bg-blue-500 text-white text-xs">
                    {index + 1}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-foreground">{action}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Limitations */}
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Limitations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {mockInvestigationReport.limitations.map((limitation, index) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="flex-shrink-0">
                  <span className="inline-flex h-2.5 w-2.5 items-center justify-center rounded-sm bg-yellow-500 text-white text-xs">
                    {index + 1}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-foreground">{limitation}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
