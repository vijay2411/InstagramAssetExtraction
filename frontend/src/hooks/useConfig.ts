import { useCallback, useEffect, useState } from 'react';
import { api, type Config } from '@/lib/api';

export function useConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.getConfig().then(setConfig).finally(() => setLoading(false)); }, []);

  const update = useCallback(async (patch: Partial<Config>) => {
    const next = await api.putConfig(patch);
    setConfig(next);
    return next;
  }, []);

  return { config, loading, update };
}
