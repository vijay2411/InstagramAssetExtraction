import { useEffect } from 'react';
import { openJobSocket } from '@/lib/ws';
import { useJobStore } from './useJobStore';

export function useJobSocket() {
  const jobId = useJobStore((s) => s.jobId);
  const applyEvent = useJobStore((s) => s.applyEvent);

  useEffect(() => {
    if (!jobId) return;
    const ws = openJobSocket(jobId, applyEvent);
    return () => ws.close();
  }, [jobId, applyEvent]);
}
