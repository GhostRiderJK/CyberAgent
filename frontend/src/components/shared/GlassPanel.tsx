import React from 'react';

interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
  padding?: string;
  radius?: string;
  borderOpacity?: string;
  bgOpacity?: string;
  backdropBlur?: string;
}

export default function GlassPanel({
  children,
  className = '',
  padding = 'p-6',
  radius = 'rounded-lg',
  borderOpacity = 'border-navy-600/20',
  bgOpacity = 'bg-navy-950/80',
  backdropBlur = 'backdrop-blur-xl',
}: GlassPanelProps) {
  return (
    <div className={`${bgOpacity} ${backdropBlur} ${borderOpacity} ${radius} ${padding} ${className}`}>
      {children}
    </div>
  );
}
