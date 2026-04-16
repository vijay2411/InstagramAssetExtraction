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

  return (
    <main className="p-6 overflow-auto">
      {status === 'idle' && <IdleState />}
      {(status === 'running' || status === 'error') && (
        <div className="space-y-4">
          <ProcessingState />
          {error && (
            <div className="bg-red-500/10 border border-red-500/40 rounded-xl p-4 text-sm text-red-400">
              <div className="font-medium mb-1">{error.stage} failed</div>
              <div className="text-xs">{error.message}</div>
            </div>
          )}
        </div>
      )}
      {status === 'done' && manifest && jobDirName && (
        <ResultsState manifest={manifest} jobDirName={jobDirName} />
      )}
    </main>
  );
}
