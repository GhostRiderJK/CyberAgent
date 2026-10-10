import React from 'react';
import { NavLink } from 'react-router-dom';

export default function Sidebar() {
  return (
    <aside className="w-64 bg-navy-950/80 backdrop-blur-xl border-r border-navy-600/20 flex flex-col h-full">
      <div className="flex-shrink-0 p-6">
        <div className="flex items-center space-x-3">
          <svg className="h-8 w-8 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
          </svg>
          <div className="space-y-1">
            <p className="text-navy-100 font-semibold text-lg">CyberAgent</p>
            <p className="text-navy-400 text-sm">AI Security Operations</p>
          </div>
        </div>
      </div>
      <nav className="mt-6 space-y-2 flex-1">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `
            flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors
            ${isActive ? 'bg-navy-900 text-navy-100' : 'text-navy-300 hover:bg-navy-900/20 hover:text-navy-100'}
          `}
        >
          <svg className="h-5 w-5 text-navy-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7l9 11m0-9L12 4m6 3l-9 11m0 9V4h6a2 2 0 012 2v12a2 2 0 01-2 2H9"></path>
          </svg>
          Overview
        </NavLink>
        <NavLink
          to="/alerts"
          end
          className={({ isActive }) => `
            flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors
            ${isActive ? 'bg-navy-900 text-navy-100' : 'text-navy-300 hover:bg-navy-900/20 hover:text-navy-100'}
          `}
        >
          <svg className="h-5 w-5 text-navy-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7 20h10a2 2 0 002-2V6a2 2 0 00-2-2H7a2 2 0 00-2 2v12z"></path>
          </svg>
          Alerts
        </NavLink>
        <NavLink
          to="/investigation"
          end
          className={({ isActive }) => `
            flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors
            ${isActive ? 'bg-navy-900 text-navy-100' : 'text-navy-300 hover:bg-navy-900/20 hover:text-navy-100'}
          `}
        >
          <svg className="h-5 w-5 text-navy-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h5m6-4V9a2 2 0 00-2-2H5a2 2 0 00-2 2v11a2 2 0 002 2h5m6-4h12a2 2 0 012 2v12a2 2 0 01-2 2h-6m-5-6V9a2 2 0 002-2h2a2 2 0 002 2v2m-2-4H9a2 2 0 00-2 2v2h2a2 2 0 002 2zm0 8h.01"></path>
          </svg>
          Investigations
        </NavLink>
        <NavLink
          to="/model-results"
          end
          className={({ isActive }) => `
            flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors
            ${isActive ? 'bg-navy-900 text-navy-100' : 'text-navy-300 hover:bg-navy-900/20 hover:text-navy-100'}
          `}
        >
          <svg className="h-5 w-5 text-navy-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m2 0H9m0 0l-3-3m3 3l3-3m-3 3l3 3"></path>
          </svg>
          Model Results
        </NavLink>
        <NavLink
          to="/replay"
          end
          className={({ isActive }) => `
            flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors
            ${isActive ? 'bg-navy-900 text-navy-100' : 'text-navy-300 hover:bg-navy-900/20 hover:text-navy-100'}
          `}
        >
          <svg className="h-5 w-5 text-navy-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2 2 2 2 2h10c2 0 2-2 2-2V9"></path>
          </svg>
          Replay
        </NavLink>
      </nav>
      <div className="flex-shrink-0 p-4 border-t border-navy-700/20">
        <div className="flex items-center space-x-3 text-navy-400 text-xs">
          <div className="h-2.5 w-2.5 bg-emerald-400 rounded-full" />
          <span>System Online</span>
        </div>
        <div className="flex items-center space-x-3 text-navy-400 text-xs mt-1">
          <div className="h-2.5 w-2.5 bg-cyan-400 rounded-full" />
          <span>Model Ready</span>
        </div>
      </div>
    </aside>
  );
}
