export type StageName = 'download' | 'audio' | 'speech' | 'sfx' | 'music' | 'finalize';

export interface Config {
  output_base_dir: string;
  demucs_model: string;
  demucs_device: 'mps' | 'cpu';
  sfx_min_cluster_size: number;
  sfx_clip_min_ms: number;
  sfx_clip_max_ms: number;
  audd_api_key: string;
}

export interface Song {
  title: string;
  artist?: string;
  album?: string | null;
  source?: string;              // "yt_dlp_meta" (case 2) or undefined (case 1 from AudD)
  spotify_url?: string | null;
  apple_music_url?: string | null;
  youtube_url?: string | null;
  song_link?: string | null;    // AudD "shortcut"
  release_date?: string | null;
  label?: string | null;
}

export interface Manifest {
  job_id: string;
  source_url: string;
  created_at: string;
  duration_seconds: number;
  assets: {
    video: { path: string; duration: number };
    speech: { path: string; duration: number };
    music: { path: string; duration: number; song?: Song };
    sfx: Array<{ path: string; duration: number; repeats: number; onset_times: number[] }>;
  };
}

export interface IdentifyMusicResponse {
  matched: boolean;
  window: { start_s: number; end_s: number; auto: boolean };
  song?: Song;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  health: () => req<{ ok: boolean }>('/api/health'),
  getConfig: () => req<Config>('/api/config'),
  putConfig: (patch: Partial<Config>) =>
    req<Config>('/api/config', { method: 'PUT', body: JSON.stringify(patch) }),
  createJob: (url: string) =>
    req<{ job_id: string; job_dir: string }>('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),
  getCurrentJob: () => req<any>('/api/jobs/current'),
  cancelJob: (job_id: string) =>
    req<{ ok: boolean }>(`/api/jobs/${job_id}/cancel`, { method: 'POST' }),
  identifyMusic: (job_id: string, body: { start_s?: number; window_s?: number } = {}) =>
    req<IdentifyMusicResponse>(`/api/jobs/${job_id}/identify-music`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  assetUrl: (job_dir_name: string, relpath: string) =>
    `/api/assets/${encodeURIComponent(job_dir_name)}/${relpath.split('/').map(encodeURIComponent).join('/')}`,
};
