import { motion } from 'framer-motion';

export type StageCardStatus = 'pending' | 'running' | 'done' | 'error';

interface Props {
  title: string;
  status: StageCardStatus;
  progress: number;
  message?: string;
  errorMessage?: string;
  color: string; // tailwind segment: 'speech' | 'music' | 'sfx' | 'accent'
}

export function StageCard({ title, status, progress, message, errorMessage, color }: Props) {
  const borderClass =
    status === 'done' ? 'border-good/50' :
    status === 'error' ? 'border-red-500/60' :
    status === 'running' ? `border-${color}` :
    'border-border-soft';

  return (
    <motion.div
      layout
      className={`bg-surface-2 border ${borderClass} rounded-xl p-4 space-y-2`}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{title}</div>
        <StatusDot status={status} color={color} />
      </div>
      {status === 'running' && (
        <div className="h-1 bg-surface-3 rounded overflow-hidden">
          <motion.div className={`h-full bg-${color}`} animate={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      )}
      {status === 'running' && message && <div className="text-[11px] text-text-mute">{message}</div>}
      {status === 'error' && <div className="text-[11px] text-red-400">{errorMessage}</div>}
      {status === 'done' && <div className="text-[11px] text-good">Done</div>}
    </motion.div>
  );
}

function StatusDot({ status, color }: { status: StageCardStatus; color: string }) {
  if (status === 'done') return <div className="w-2 h-2 rounded-full bg-good" />;
  if (status === 'error') return <div className="w-2 h-2 rounded-full bg-red-500" />;
  if (status === 'running') return <div className={`w-2 h-2 rounded-full bg-${color} animate-pulse`} />;
  return <div className="w-2 h-2 rounded-full bg-text-mute/40" />;
}
