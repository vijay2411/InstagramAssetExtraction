export type WsEvent =
  | { type: 'replay'; events: WsEvent[] }
  | { type: 'stage.start'; stage: string }
  | { type: 'stage.progress'; stage: string; progress?: number; message?: string }
  | { type: 'stage.done'; stage: string; artifacts: Record<string, string> }
  | { type: 'stage.error'; stage: string; message: string; retriable: boolean }
  | { type: 'job.done'; manifest: any }
  | { type: 'job.error'; stage: string; message: string }
  | { type: 'job.canceled' }
  // SFX extraction progress — piggybacks on the same WS bus so MusicCard
  // can listen without opening a second socket.
  | { type: 'sfx_extract.progress'; stage: string; progress?: number; message?: string }
  | { type: 'sfx_extract.done'; ok: boolean; sfx_count: number; error?: string | null; stage_failed?: string | null; cache_hit?: boolean };

export function openJobSocket(jobId: string, onEvent: (e: WsEvent) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/api/jobs/${jobId}/events`);
  ws.onmessage = (ev) => {
    try { onEvent(JSON.parse(ev.data) as WsEvent); }
    catch (e) { console.error('bad ws frame', e); }
  };
  return ws;
}
