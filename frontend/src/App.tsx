import React from 'react';
import AlertsDashboard from './components/AlertsDashboard';
import InvestigationView from './components/InvestigationView';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-2xl font-bold mb-6">CyberAgent Dashboard</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AlertsDashboard className="lg:col-span-1" />
        <InvestigationView className="lg:col-span-1" />
      </div>
    </div>
  );
}

export default App;