export function fmtDuration(seconds: number): string {
  if (!isFinite(seconds)) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function fmtDurationPrecise(seconds: number): string {
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return fmtDuration(seconds);
}
