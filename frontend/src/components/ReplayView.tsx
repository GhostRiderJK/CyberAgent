import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { mockReplaySession, mockReplayFlows, mockReplayStats } from '@/mocks/replay';

export default function ReplayView() {
  const statusToBadgeVariant: Record<string, 'default' | 'destructive' | 'outline' | 'secondary'> = {
    idle: 'secondary',
    running: 'default',
    paused: 'outline',
    completed: 'default',
    error: 'destructive',
  };

  return (
    <div className="space-y-6">
      {/* Replay Session Info */}
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Replay Session</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Session ID</p>
              <p className="text-xl font-semibold">{mockReplaySession.id}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Status</p>
              <Badge variant={statusToBadgeVariant[mockReplaySession.status]}>
                {mockReplaySession.status}
              </Badge>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Duration</p>
              <p className="text-xl font-semibold">
                {mockReplaySession.endTime ? (
                  ` ${mockReplaySession.startTime} → ${mockReplaySession.endTime}`
                ) : (
                  `Started: ${mockReplaySession.startTime}`
                )}
              </p>
            </div>
          </div>

          <div className="space-x-4 text-sm text-muted-foreground">
            <span>Total Flows: {mockReplaySession.totalFlows}</span>
            <span>Malicious Flows: {mockReplaySession.maliciousFlows}</span>
            <span>Benign Flows: {mockReplaySession.benignFlows}</span>
          </div>
        </CardContent>
      </Card>

      {/* Replay Statistics */}
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Replay Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Flows/Second</p>
              <p className="text-xl font-semibold">{mockReplayStats.flowsPerSecond}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Avg Confidence</p>
              <p className="text-xl font-semibold">
                {(mockReplayStats.avgConfidence * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Threats Detected</p>
              <p className="text-xl font-semibold">{mockReplayStats.threatsDetected}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">False Positives</p>
              <p className="text-xl font-semibold">{mockReplayStats.falsePositives}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Flows Table */}
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Recent Flows</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableCaption>
                Showing last {mockReplayFlows.length} flows
              </TableCaption>
              <TableHead>
                <TableRow>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>Flow ID</TableCell>
                  <TableCell>Prediction</TableCell>
                  <TableCell>Confidence</TableCell>
                  <TableCell>Investigation Verdict</TableCell>
                  <TableCell>Severity</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mockReplayFlows.map((flow, index) => (
                  <TableRow key={index}>
                    <TableCell>{flow.timestamp}</TableCell>
                    <TableCell>{flow.flowId}</TableCell>
                    <TableCell>
                      {flow.prediction}
                    </TableCell>
                    <TableCell>
                      {(flow.confidence * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell>
                      {flow.investigation ? flow.investigation.verdict : 'N/A'}
                    </TableCell>
                    <TableCell>
                      {flow.investigation ? flow.investigation.severity : 'N/A'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Replay Controls */}
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Replay Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <button
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-md transition-colors disabled:opacity-50"
              onClick={() => {
                // TODO: Implement replay start/pause/resume/stop
                alert('Replay control not implemented in prototype');
              }}
            >
              {mockReplaySession.status === 'running' ? 'Pause' : 'Start'}
            </button>
            <button
              className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium rounded-md transition-colors disabled:opacity-50"
              onClick={() => {
                // TODO: Implement replay stop
                alert('Replay stop not implemented in prototype');
              }}
            >
              Stop
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}