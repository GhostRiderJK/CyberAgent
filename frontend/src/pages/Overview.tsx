import React from 'react';
import MetricCard from '@/components/shared/MetricCard';
import GlassPanel from '@/components/shared/GlassPanel';
import SeverityBadge from '@/components/shared/SeverityBadge';

const Overview = () => {
  return (
    <div>
      <h1>Overview</h1>
      <MetricCard title="Test" value="123" icon={<span>Test</span>} variant="primary" accentColor="cyan" />
      <GlassPanel className="p-4">
        <h2>Glass panel</h2>
        <p>Content</p>
      </GlassPanel>
    </div>
  );
};

export default Overview;