import { useEffect, useState } from 'react';
import { api } from '@/services/api';

export type ApiHealth = 'checking' | 'online' | 'unreachable';

/** One health probe per mount, re-checked every 30s, shared by the shell and the overview. */
export function useApiHealth(): ApiHealth {
  const [health, setHealth] = useState<ApiHealth>('checking');

  useEffect(() => {
    let active = true;
    const probe = () => api.healthCheck().then(
      () => { if (active) setHealth('online'); },
      () => { if (active) setHealth('unreachable'); },
    );
    probe();
    const timer = window.setInterval(probe, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  return health;
}
