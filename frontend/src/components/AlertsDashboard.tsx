import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableRow, TableCaption } from '@/components/ui/table';
import SeverityBadge from '@/components/shared/SeverityBadge';
import { mockAlerts } from '@/mocks/alerts';

export default function AlertsDashboard() {
  return (
    <div className="space-y-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="text-navy-200">Network Flow Alerts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="overflow-x-auto">
            <Table className="w-full">
              <TableCaption className="text-navy-400">
                Total alerts: {mockAlerts.length}
              </TableCaption>
              <TableHead>
                <TableRow className="bg-navy-800 text-navy-50">
                  <TableCell className="px-4 py-2">ID</TableCell>
                  <TableCell className="px-4 py-2">Classification</TableCell>
                  <TableCell className="px-4 py-2">Confidence</TableCell>
                  <TableCell className="px-4 py-2">Severity</TableCell>
                  <TableCell className="px-4 py-2">Source IP</TableCell>
                  <TableCell className="px-4 py-2">Timestamp</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mockAlerts.map((alert) => (
                  <TableRow key={alert.id} className="border-t border-navy-700/50 hover:bg-navy-800/50">
                    <TableCell className="px-4 py-2">{alert.id}</TableCell>
                    <TableCell className="px-4 py-2">{alert.class}</TableCell>
                    <TableCell className="px-4 py-2">
                      {(alert.confidence * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="px-4 py-2">
                      <SeverityBadge severity={alert.severity} className="ml-2" />
                    </TableCell>
                    <TableCell className="px-4 py-2">{alert.sourceIp}</TableCell>
                    <TableCell className="px-4 py-2">{alert.timestamp}</TableCell>
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