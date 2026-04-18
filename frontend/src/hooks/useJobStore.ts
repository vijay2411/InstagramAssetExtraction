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

export type SfxExtractStatus = 'idle' | 'running' | 'done' | 'error';
export interface SfxExtractState {
  status: SfxExtractStatus;
  stage: string | null;        // 'cache' | 'download' | 'align' | 'subtract' | 'mine' | null
  progress: number;            // 0..1 within the current stage
  message: string | null;      // latest progress message
  error: string | null;        // failure reason
  stageFailed: string | null;  // which sub-stage bailed
  sfxCount: number | null;     // populated on done
  cacheHit: boolean | null;
}

interface JobSliceState {
  jobId: string | null;
  jobDirName: string | null;
  status: Status;
  stages: Record<StageName, StageState>;
  manifest: Manifest | null;
  error: { stage: StageName; message: string } | null;
  sfxExtract: SfxExtractState;
}

interface JobStore extends JobSliceState {
  startJob: (jobId: string, jobDirName: string) => void;
  applyEvent: (e: any) => void;
  reset: () => void;
  startSfxExtract: () => void;
  setManifest: (m: Manifest) => void;
}

const initialSfxExtract = (): SfxExtractState => ({
  status: 'idle',
  stage: null,
  progress: 0,
  message: null,
  error: null,
  stageFailed: null,
  sfxCount: null,
  cacheHit: null,
});

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
  sfxExtract: initialSfxExtract(),

  startJob: (jobId, jobDirName) =>
    set({ jobId, jobDirName, status: 'running', stages: initialStages(), manifest: null, error: null, sfxExtract: initialSfxExtract() }),

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
      case 'sfx_extract.progress':
        set({ sfxExtract: {
          ...get().sfxExtract,
          status: 'running',
          stage: e.stage,
          progress: e.progress ?? 0,
          message: e.message ?? null,
        }});
        break;
      case 'sfx_extract.done':
        set({ sfxExtract: {
          ...get().sfxExtract,
          status: e.ok ? 'done' : 'error',
          progress: 1,
          error: e.error ?? null,
          stageFailed: e.stage_failed ?? null,
          sfxCount: e.sfx_count ?? 0,
          cacheHit: e.cache_hit ?? null,
        }});
        break;
    }
  },

  startSfxExtract: () => set({ sfxExtract: { ...initialSfxExtract(), status: 'running' } }),

  setManifest: (m) => set({ manifest: m }),

  reset: () => set({
    jobId: null, jobDirName: null, status: 'idle',
    stages: initialStages(), manifest: null, error: null,
    sfxExtract: initialSfxExtract(),
  }),
}));
