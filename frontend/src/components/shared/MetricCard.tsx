import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  variant?: 'default' | 'primary' | 'secondary' | 'destructive' | 'outline';
  accentColor?: 'emerald' | 'cyan' | 'amber' | 'red' | 'indigo' | 'purple';
}

export default function MetricCard({
  title,
  value,
  subtitle,
  icon,
  variant = 'default',
  accentColor = 'cyan',
}: MetricCardProps) {
  // Map accent colors to Tailwind classes
  const accentColorMap: Record<string, string> = {
    emerald: 'bg-emerald-500/20 text-emerald-400',
    cyan: 'bg-cyan-500/20 text-cyan-400',
    amber: 'bg-amber-500/20 text-amber-400',
    red: 'bg-red-500/20 text-red-400',
    indigo: 'bg-indigo-500/20 text-indigo-400',
    purple: 'bg-purple-500/20 text-purple-400',
  };

  const accentClass = accentColorMap[accentColor] || accentColorMap.cyan;

  return (
    <div className="bg-navy-900/80 backdrop-blur-xl border border-navy-600/20 rounded-lg p-6">
      <div className="flex items-center space-x-3 mb-4">
        <div className={`h-8 w-8 flex items-center justify-center ${accentClass} rounded-lg`}>
          {icon}
        </div>
        <div>
          <h3 className="text-navy-300 text-sm font-medium">{title}</h3>
          {subtitle && <p className="text-navy-400 text-sm">{subtitle}</p>}
        </div>
      </div>
      <div className="text-navy-100 text-2xl font-semibold">
        {value}
      </div>
    </div>
  );
}
