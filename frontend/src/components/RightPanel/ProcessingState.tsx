import { motion } from 'motion/react';
import { useJobStore } from '@/hooks/useJobStore';
import { StageCard, type StageCardStatus } from '@/components/StageCard';
import type { StageName } from '@/lib/api';

// UI shows 4 cards; map each to 1+ pipeline stages.
const MAPPING: { ui: string; sub: string; stages: StageName[]; color: string }[] = [
  { ui: 'Download',       sub: 'pulling the source reel',          stages: ['download', 'audio'], color: 'ember'  },
  { ui: 'Separate voice', sub: 'demucs — isolating the creator',   stages: ['speech'],            color: 'speech' },
  { ui: 'Mine sfx',       sub: 'finding repeated short sounds',    stages: ['sfx'],               color: 'sfx'    },
  { ui: 'Lift music',     sub: 'everything underneath the voice',  stages: ['music', 'finalize'], color: 'music'  },
];

function aggregate(
  stages: ReturnType<typeof useJobStore.getState>['stages'],
  names: StageName[]
): { status: StageCardStatus; progress: number; message?: string; errorMessage?: string } {
  const sub = names.map((n) => stages[n]);
  if (sub.some((s) => s.status === 'error')) {
    const errored = sub.find((s) => s.status === 'error');
    return { status: 'error', progress: 0, errorMessage: errored?.errorMessage };
  }
  if (sub.every((s) => s.status === 'done')) return { status: 'done', progress: 1 };
  if (sub.some((s) => s.status === 'running' || s.status === 'done')) {
    const total = sub.reduce((a, s) => a + (s.status === 'done' ? 1 : s.progress), 0) / sub.length;
    const msg = sub.find((s) => s.status === 'running')?.message;
    return { status: 'running', progress: total, message: msg };
  }
  return { status: 'pending', progress: 0 };
}

export function ProcessingState() {
  const stages = useJobStore((s) => s.stages);
  return (
    <div className="px-10 py-12 max-w-3xl">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-10"
      >
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-mute mb-3">
          Pipeline
        </div>
        <h2 className="font-display font-light text-display-sm tracking-display text-text">
          <span className="text-ember">Extracting</span>
          <span className="text-text-dim">, four passes.</span>
        </h2>
      </motion.div>

      <div className="space-y-3">
        {MAPPING.map(({ ui, sub, stages: names, color }, i) => {
          const agg = aggregate(stages, names);
          return (
            <motion.div
              key={ui}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.08 * i, ease: [0.22, 1, 0.36, 1] }}
            >
              <StageCard title={ui} subtitle={sub} {...agg} color={color} />
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
