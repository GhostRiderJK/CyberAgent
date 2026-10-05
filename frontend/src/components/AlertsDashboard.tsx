import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { mockAlerts } from '@/mocks/alerts';

const severityToBadgeVariant: Record<string, 'default' | 'destructive' | 'outline' | 'secondary'> = {
  low: 'secondary',
  medium: 'outline',
  high: 'destructive',
  critical: 'destructive',
};

export default function AlertsDashboard() {
  return (
    <div className="space-y-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Network Flow Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableCaption>
                Total alerts: {mockAlerts.length}
              </TableCaption>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Class</TableCell>
                  <TableCell>Confidence</TableCell>
                  <TableCell>Severity</TableCell>
                  <TableCell>Source IP</TableCell>
                  <TableCell>Timestamp</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mockAlerts.map((alert) => (
                  <TableRow key={alert.id}>
                    <TableCell>{alert.id}</TableCell>
                    <TableCell>{alert.class}</TableCell>
                    <TableCell>
                      {(alert.confidence * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell>
                      <Badge variant={severityToBadgeVariant[alert.severity]}>
                        {alert.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>{alert.sourceIp}</TableCell>
                    <TableCell>{alert.timestamp}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}