import { useState } from 'react';
import { api } from '@/lib/api';
import { useJobStore } from '@/hooks/useJobStore';

export function UrlInput() {
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const startJob = useJobStore((s) => s.startJob);
  const status = useJobStore((s) => s.status);
  const running = status === 'running';

  async function extract() {
    setErr(null);
    setBusy(true);
    try {
      const { job_id, job_dir } = await api.createJob(url);
      const jobDirName = job_dir.split('/').pop() ?? job_id;
      startJob(job_id, jobDirName);
    } catch (e: any) {
      setErr(e.message || 'failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <label className="block text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold">URL</label>
      <input
        className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm placeholder:text-text-mute focus:border-accent outline-none transition-colors"
        placeholder="https://instagram.com/reel/..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={running}
      />
      <button
        className="w-full bg-accent text-white rounded-lg py-2 text-sm font-medium hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition"
        onClick={extract}
        disabled={!url || busy || running}
      >
        {busy ? 'Starting…' : running ? 'Running…' : 'Extract'}
      </button>
      {err && <div className="text-xs text-red-400 mt-1">{err}</div>}
    </div>
  );
}
