import { useState, type KeyboardEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { api } from '@/lib/api';
import { useJobStore } from '@/hooks/useJobStore';

export function UrlInput() {
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const startJob = useJobStore((s) => s.startJob);
  const reset = useJobStore((s) => s.reset);
  const status = useJobStore((s) => s.status);
  const running = status === 'running';
  const hasResult = status === 'done';

  async function extract() {
    setErr(null);
    setBusy(true);
    if (hasResult) reset();
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

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && url && !running && !busy) {
      extract();
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-mute">
          Paste a reel
        </label>
        <span className="font-mono text-[9px] tracking-widest text-text-mute/50">⌘ + ↵</span>
      </div>

      <div className="relative group">
        <input
          className="w-full bg-surface/80 border border-border rounded-xl px-4 py-3 text-[13px] font-mono tracking-tight
                     placeholder:text-text-mute/70 placeholder:font-mono placeholder:text-[12px]
                     focus:border-ember focus:bg-surface focus:outline-none focus:ring-4 focus:ring-ember/10
                     transition-all duration-200 disabled:opacity-50"
          placeholder="instagram.com/reel/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={onKey}
          disabled={running}
          spellCheck={false}
        />
        {/* Focus glow */}
        <div
          className="pointer-events-none absolute inset-0 rounded-xl opacity-0 group-focus-within:opacity-100 transition-opacity"
          style={{ boxShadow: '0 0 0 1px rgba(232,177,58,0.15), 0 8px 28px rgba(232,177,58,0.1)' }}
        />
      </div>

      <motion.button
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.985 }}
        className="group relative w-full overflow-hidden rounded-xl py-3.5 font-display text-[17px] font-semibold tracking-tighter
                   bg-gradient-to-br from-ember via-ember to-ember-hot text-bg
                   shadow-[0_10px_30px_-8px_rgba(232,177,58,0.5)]
                   disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none transition"
        onClick={extract}
        disabled={!url || busy || running}
      >
        <span className="relative z-10">
          {busy ? 'starting…' : running ? 'working…' : hasResult ? 'extract another' : 'extract'}
        </span>
        {/* Shimmer sweep on hover */}
        <span
          className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent
                     group-hover:translate-x-full group-hover:duration-[900ms] duration-0 transition-transform"
        />
      </motion.button>

      <AnimatePresence>
        {err && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="text-[11px] text-coral font-mono"
          >
            {err}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
