import Sidebar from './Sidebar';
import TopBar from './TopBar';
import type { ReactNode } from 'react';

export default function AppShell({ children }: { children: ReactNode }) {
  return <div className="app-canvas"><div className="flex min-h-screen"><Sidebar /><div className="min-w-0 flex-1"><TopBar /><main className="mx-auto w-full max-w-[1680px] p-4 sm:p-6 lg:p-8">{children}</main></div></div></div>;
}
