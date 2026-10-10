import React from 'react';
import { useLocation } from 'react-router-dom';

export default function TopBar() {
  const location = useLocation();
  const [pathname] = location.pathname.split('?');

  // Get the page title based on the path
  const getPageTitle = (path: string) => {
    switch (path) {
      case '/':
        return 'Security Overview';
      case '/alerts':
        return 'Network Flow Alerts';
      case '/investigation':
        return 'Investigation';
      case '/model-results':
        return 'Model Results';
      case '/replay':
        return 'Replay';
      default:
        return 'CyberAgent';
    }
  };

  return (
    <header className="bg-navy-950/80 backdrop-blur-xl border-b border-navy-600/20 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h1 className="text-navy-100 text-2xl font-semibold">{getPageTitle(pathname)}</h1>
          <p className="text-navy-400 text-sm mt-1">
            {pathname === '/' && 'Real-time network flow monitoring and ML-assisted threat detection'}
          </p>
        </div>
        <div className="flex items-center space-x-4 text-navy-400">
          <div className="relative">
            <button className="flex items-center space-x-2 text-navy-300 hover:text-navy-100">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-6-6 6 6 0 00-6 6v3.158a2.032 2.032 0 00-.595 1.405H9"></path>
              </svg>
              <span className="hidden md:inline">Filters</span>
            </button>
            {/* Dropdown menu for filters - simplified for now */}
            <div className="absolute right-0 mt-2 w-56 bg-navy-900/80 backdrop-blur-xl border border-navy-600/20 rounded-md shadow-lg z-20 hidden">
              <div className="py-1">
                <button className="w-full text-left px-4 py-2 text-navy-300 hover:bg-navy-800/50">
                  Time Range
                </button>
                <button className="w-full text-left px-4 py-2 text-navy-300 hover:bg-navy-800/50">
                  Confidence Threshold
                </button>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <div className="h-2.5 w-2.5 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-navy-100">System Online</span>
          </div>
        </div>
      </div>
    </header>
  );
}
