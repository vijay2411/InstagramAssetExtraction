import { create } from 'zustand';
import type { Manifest, StageName } from '@/lib/api';

type Status = 'idle' | 'running' | 'done' | 'error' | 'canceled';
type StageStatus = 'pending' | 'running' | 'done' | 'error';

export interface StageState {
  status: StageStatus;
  progress: number;
  message?: string;
  errorMessage?: string;
  retriable?: boolean;
  artifacts?: Record<string, string>;
}

interface JobSliceState {
  jobId: string | null;
  jobDirName: string | null;
  status: Status;
  stages: Record<StageName, StageState>;
  manifest: Manifest | null;
  error: { stage: StageName; message: string } | null;
}

interface JobStore extends JobSliceState {
  startJob: (jobId: string, jobDirName: string) => void;
  applyEvent: (e: any) => void;
  reset: () => void;
}

const initialStages = (): Record<StageName, StageState> => ({
  download: { status: 'pending', progress: 0 },
  audio: { status: 'pending', progress: 0 },
  speech: { status: 'pending', progress: 0 },
  sfx: { status: 'pending', progress: 0 },
  music: { status: 'pending', progress: 0 },
  finalize: { status: 'pending', progress: 0 },
});

export const useJobStore = create<JobStore>((set, get) => ({
  jobId: null, jobDirName: null, status: 'idle',
  stages: initialStages(), manifest: null, error: null,

  startJob: (jobId, jobDirName) =>
    set({ jobId, jobDirName, status: 'running', stages: initialStages(), manifest: null, error: null }),

  applyEvent: (e) => {
    const s = get().stages;
    switch (e.type) {
      case 'replay':
        (e.events as any[]).forEach((sub) => get().applyEvent(sub));
        break;
      case 'stage.start':
        set({ stages: { ...s, [e.stage]: { ...s[e.stage as StageName], status: 'running' } } });
        break;
      case 'stage.progress':
        set({ stages: {
          ...s,
          [e.stage]: { ...s[e.stage as StageName], status: 'running', progress: e.progress ?? s[e.stage as StageName].progress, message: e.message },
        }});
        break;
      case 'stage.done':
        set({ stages: {
          ...s,
          [e.stage]: { ...s[e.stage as StageName], status: 'done', progress: 1, artifacts: e.artifacts },
        }});
        break;
      case 'stage.error':
        set({ stages: {
          ...s,
          [e.stage]: { ...s[e.stage as StageName], status: 'error', errorMessage: e.message, retriable: e.retriable },
        }});
        break;
      case 'job.done':
        set({ status: 'done', manifest: e.manifest });
        break;
      case 'job.error':
        set({ status: 'error', error: { stage: e.stage, message: e.message } });
        break;
      case 'job.canceled':
        set({ status: 'canceled' });
        break;
    }
  },

  reset: () => set({ jobId: null, jobDirName: null, status: 'idle', stages: initialStages(), manifest: null, error: null }),
}));
