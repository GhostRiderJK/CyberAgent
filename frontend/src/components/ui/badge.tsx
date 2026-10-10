import * as React from "react";

interface BadgeProps {
  children?: React.ReactNode;
  variant?: string;
  className?: string;
}

export const Badge = ({ children, variant, className }: BadgeProps) => {
  let variantClass = '';
  if (variant === 'low') variantClass = 'bg-navy-200 text-navy-800';
  else if (variant === 'medium') variantClass = 'bg-navy-300 text-navy-900';
  else if (variant === 'high' || variant === 'critical') variantClass = 'bg-red-100 text-red-800';
  else variantClass = 'bg-navy-100 text-navy-900';

  const classes = [`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variantClass}`, className].filter(Boolean).join(' ');
  return <span className={classes}>{children}</span>;
};
