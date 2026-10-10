import React from 'react';

interface SeverityBadgeProps {
  severity: 'low' | 'medium' | 'high' | 'critical';
  className?: string;
}

export default function SeverityBadge({ severity, className = '' }: SeverityBadgeProps) {
  // Map severity to badge variant and color
  const severityConfig: Record<string, { variant: 'default' | 'destructive' | 'outline' | 'secondary'; label: string; colorClass: string }> = {
    low: { variant: 'secondary', label: 'Low', colorClass: 'bg-green-100 text-green-800' },
    medium: { variant: 'outline', label: 'Medium', colorClass: 'bg-amber-100 text-amber-800' },
    high: { variant: 'destructive', label: 'High', colorClass: 'bg-red-100 text-red-800' },
    critical: { variant: 'destructive', label: 'Critical', colorClass: 'bg-red-100 text-red-800 font-semibold' },
  };

  const config = severityConfig[severity] || severityConfig.low;

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.colorClass} ${className}`}>
      {config.label}
    </span>
  );
}
