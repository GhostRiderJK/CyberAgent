import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import ClassLabel from '@/components/shared/ClassLabel';
import { mockReplaySession, mockReplayFlows, mockReplayStats } from '@/mocks/replay';
import { flowIdLabel } from '@/lib/classLabels';
import { formatConfidencePct } from '@/lib/format';

export default function ReplayView() {
  const statusToBadgeVariant: Record<string, 'default' | 'destructive' | 'outline' | 'secondary'> = {
    idle: 'secondary',
    running: 'default',
    paused: 'outline',
    completed: 'default',
    error: 'destructive',
  };

  return (
    <div className="space-y-6"><section className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">Controlled playback</p><h2 className="font-display mt-2 text-3xl font-semibold">Flow replay</h2><p className="mt-1 text-sm text-slate-400">This interface displays five static replay fixtures, not a live network stream.</p></div><span className="badge badge-amber">Demo fixtures</span></section>
      {/* Replay Session Info */}
      <Card className="surface panel w-full">
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
      <Card className="surface panel w-full">
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
                {formatConfidencePct(mockReplayStats.avgConfidence)}
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
      <Card className="surface panel w-full">
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
                    <TableCell className="mono">{flowIdLabel(flow.flowId)}</TableCell>
                    <TableCell>
                      <ClassLabel name={flow.prediction} />
                    </TableCell>
                    <TableCell>
                      {formatConfidencePct(flow.confidence)}
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
      <Card className="surface panel w-full">
        <CardHeader>
          <CardTitle>Replay Controls</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <button className="btn" disabled title="Replay controls are not connected to a backend">{mockReplaySession.status === 'running' ? 'Pause unavailable' : 'Start unavailable'}</button>
            <span className="text-sm text-slate-500">Controls are disabled until the replay API is implemented.</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
