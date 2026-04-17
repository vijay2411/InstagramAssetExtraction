import { AnimatePresence, motion } from 'motion/react';
import { useJobStore } from '@/hooks/useJobStore';
import { useJobSocket } from '@/hooks/useJobSocket';
import { IdleState } from './IdleState';
import { ProcessingState } from './ProcessingState';
import { ResultsState } from './ResultsState';

export function RightPanel() {
  useJobSocket();
  const status = useJobStore((s) => s.status);
  const manifest = useJobStore((s) => s.manifest);
  const jobDirName = useJobStore((s) => s.jobDirName);
  const error = useJobStore((s) => s.error);

  const key = status === 'done' && manifest ? 'results' :
              status === 'running' || status === 'error' ? 'processing' :
              'idle';

  return (
    <main className="relative overflow-auto">
      <AnimatePresence mode="wait">
        <motion.div
          key={key}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          {key === 'idle' && <IdleState />}
          {key === 'processing' && (
            <div>
              <ProcessingState />
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mx-10 mb-10 -mt-2 rounded-xl border border-coral/40 bg-coral/5 p-5"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-coral" />
                    <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-coral">
                      {error.stage} · error
                    </div>
                  </div>
                  <div className="font-mono text-[11px] text-coral/90 whitespace-pre-wrap break-words leading-relaxed">
                    {error.message}
                  </div>
                </motion.div>
              )}
            </div>
          )}
          {key === 'results' && manifest && jobDirName && (
            <ResultsState manifest={manifest} jobDirName={jobDirName} />
          )}
        </motion.div>
      </AnimatePresence>
    </main>
  );
}
