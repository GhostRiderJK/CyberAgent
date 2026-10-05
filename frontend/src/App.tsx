import React from 'react';
import AlertsDashboard from './components/AlertsDashboard';
import InvestigationView from './components/InvestigationView';
import ModelResultsPage from './components/ModelResultsPage';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-2xl font-bold mb-6">CyberAgent Dashboard</h1>
      <div className="space-x-6">
        <div className="w-1/3 space-y-4">
          <AlertsDashboard />
          <InvestigationView />
        </div>
        <div className="w-2/3 space-y-4">
          <ModelResultsPage />
        </div>
      </div>
    </div>
  );
}

export default App;