import { useJobStore } from '@/hooks/useJobStore';
import { StageCard, type StageCardStatus } from '@/components/StageCard';
import type { StageName } from '@/lib/api';

// UI shows 4 cards; map each to 1+ pipeline stages.
const MAPPING: { ui: string; stages: StageName[]; color: string }[] = [
  { ui: 'Download',        stages: ['download', 'audio'],      color: 'accent' },
  { ui: 'Separate speech', stages: ['speech'],                 color: 'speech' },
  { ui: 'Mine SFX',        stages: ['sfx'],                    color: 'sfx' },
  { ui: 'Identify music',  stages: ['music', 'finalize'],      color: 'music' },
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
    <div className="space-y-3">
      {MAPPING.map(({ ui, stages: names, color }) => {
        const agg = aggregate(stages, names);
        return <StageCard key={ui} title={ui} {...agg} color={color} />;
      })}
    </div>
  );
}
