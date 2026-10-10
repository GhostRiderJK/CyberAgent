import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/shared/AppShell';
import Overview from './pages/Overview';
import AlertsDashboard from './components/AlertsDashboard';
import InvestigationView from './components/InvestigationView';
import ModelResultsPage from './components/ModelResultsPage';
import ReplayView from './components/ReplayView';

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/alerts" element={<AlertsDashboard />} />
          <Route path="/investigation" element={<InvestigationView />} />
          <Route path="/model-results" element={<ModelResultsPage />} />
          <Route path="/replay" element={<ReplayView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
