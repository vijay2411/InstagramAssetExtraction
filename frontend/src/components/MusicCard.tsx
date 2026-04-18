import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { api, type Manifest, type Song, type IdentifyMusicResponse } from '@/lib/api';
import { Waveform } from './Waveform';
import { fmtDuration } from '@/lib/format';

interface Props {
  manifest: Manifest;
  jobId: string;
  jobDirName: string;
}

const MUSIC_HEX = '#e8b13a';

export function MusicCard({ manifest, jobId, jobDirName }: Props) {
  const music = manifest.assets.music;
  const musicUrl = api.assetUrl(jobDirName, music.path);

  // Local state: starts from whatever yt-dlp gave us (case 2) and can be
  // overwritten by an AudD identification (case 1).
  const [song, setSong] = useState<Song | undefined>(music.song);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Window controls (only used when we do AudD identification).
  const [windowStart, setWindowStart] = useState<number | null>(null);
  const [windowLen] = useState(20);
  // Auto-cut if windowStart is null.
  const maxStart = Math.max(0, Math.floor(music.duration - windowLen));

  // Playback gain. Shared with AudD fingerprint — whatever the user is
  // hearing is what gets sent for matching. Range 0.5x – 4.0x.
  const [gain, setGain] = useState(1.0);

  // Case 2 = Instagram has already tagged a known song on the reel (either
  // via yt-dlp's own metadata or via our embed-page fallback scrape).
  const isCase2 = !!song && (song.source === 'yt_dlp_meta' || song.source === 'ig_embed');
  // Case 1 = user fingerprinted via AudD. AudD results have no `source` set.
  const isCase1FromAudD = !!song && !isCase2;
  const noSong = !song;

  async function runIdentify() {
    setBusy(true);
    setErr(null);
    try {
      const body: { start_s?: number; window_s?: number; gain?: number } = {
        window_s: windowLen,
        gain,  // send the current slider value so AudD fingerprints what you hear
      };
      if (windowStart !== null) body.start_s = windowStart;
      const resp: IdentifyMusicResponse = await api.identifyMusic(jobId, body);
      if (resp.matched && resp.song) {
        setSong(resp.song);
        // If it was auto-picked, show the window that was chosen.
        setWindowStart(resp.window.start_s);
      } else {
        setErr('no match — try a different window');
      }
    } catch (e: any) {
      setErr(e.message || 'identify failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
      className="group relative overflow-hidden rounded-2xl border border-border/60 bg-surface/70 backdrop-blur-xl
                 hover:border-music/50 transition-colors shadow-[0_20px_50px_-20px_rgba(232,177,58,0.45)]"
    >
      {/* Top ember glow on hover */}
      <div
        className="absolute inset-x-0 -top-24 h-48 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{ background: `radial-gradient(600px 200px at 50% 100%, ${MUSIC_HEX}22 0%, transparent 70%)` }}
      />

      <div className="relative p-6 space-y-5">
        {/* Header: label + title + download */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <div className="w-1.5 h-1.5 rounded-full bg-music" />
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-music">music</span>
              {isCase2 && (
                <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-text-mute/80 ml-2 px-2 py-[2px] rounded-full border border-border-soft">
                  from instagram audio
                </span>
              )}
              {isCase1FromAudD && (
                <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-ember ml-2 px-2 py-[2px] rounded-full border border-ember/40 bg-ember/10">
                  matched via audd
                </span>
              )}
            </div>
            <h3 className="font-display text-[28px] leading-[1.05] font-light tracking-tighter text-text truncate">
              {song ? song.title : 'Unknown song'}
            </h3>
            <div className="mt-1.5 font-mono text-[11px] text-text-mute tracking-tight truncate">
              {song ? (
                [song.artist, song.album].filter(Boolean).join(' · ')
              ) : (
                `${fmtDuration(music.duration)} · demucs non-vocals`
              )}
            </div>
          </div>
          <a
            href={musicUrl}
            download="music.wav"
            className="shrink-0 flex items-center gap-2 rounded-lg border border-border/60 bg-surface-3/80
                       hover:border-music hover:bg-music/10 px-3 py-2 text-[11px] font-mono
                       uppercase tracking-wider text-text-dim hover:text-text transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 1.5v7M3 6l3 3 3-3M1.5 10.5h9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            wav
          </a>
        </div>

        {/* Waveform + gain slider */}
        <div className="space-y-3">
          <Waveform url={musicUrl} color={MUSIC_HEX} gain={gain} />
          <GainSlider gain={gain} onChange={setGain} />
        </div>

        {/* Streaming links — shown when we have a song, any source */}
        {song && (
          <div className="flex flex-wrap gap-2">
            {song.spotify_url && (
              <StreamLink href={song.spotify_url} label="Spotify" />
            )}
            {song.apple_music_url && (
              <StreamLink href={song.apple_music_url} label="Apple Music" />
            )}
            {song.youtube_url && (
              <StreamLink href={song.youtube_url} label="YouTube" />
            )}
            {song.song_link && (
              <StreamLink href={song.song_link} label="All links" />
            )}
          </div>
        )}

        {/* Case 1: Find song button + window slider */}
        {noSong && (
          <div className="rounded-xl border border-border/60 bg-surface-3/40 p-4 space-y-4">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-mute mb-1">
                Original audio detected
              </div>
              <p className="text-[12.5px] text-text-dim leading-relaxed">
                Instagram didn't tag this reel with a library track — the creator
                uploaded a custom mix. Fingerprint the music to find the underlying song.
              </p>
            </div>

            {/* Window slider — pick a start-offset, fixed 20s window */}
            <div>
              <div className="flex items-baseline justify-between mb-2">
                <label className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
                  Window start
                </label>
                <span className="font-mono tabular text-[11px] text-ember">
                  {windowStart === null
                    ? 'auto'
                    : `${fmtDuration(windowStart)} → ${fmtDuration(windowStart + windowLen)}`}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={maxStart}
                step={1}
                value={windowStart === null ? Math.floor(maxStart / 2) : windowStart}
                onChange={(e) => setWindowStart(Number(e.target.value))}
                disabled={busy || maxStart === 0}
                className="w-full accent-ember h-1"
              />
              <div className="flex justify-between items-center mt-1">
                <button
                  className="font-mono text-[10px] uppercase tracking-wider text-text-mute hover:text-ember transition-colors disabled:opacity-40"
                  onClick={() => setWindowStart(null)}
                  disabled={busy || windowStart === null}
                >
                  reset to auto
                </button>
                <span className="font-mono text-[10px] text-text-mute">
                  {windowLen}s clip · 0:00 — {fmtDuration(music.duration)}
                </span>
              </div>
            </div>

            <motion.button
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={runIdentify}
              disabled={busy}
              className="w-full rounded-xl py-3 font-display text-[16px] font-semibold tracking-tighter
                         bg-gradient-to-br from-ember via-ember to-ember-hot text-bg
                         shadow-[0_10px_30px_-8px_rgba(232,177,58,0.5)]
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? 'searching…' : 'find song'}
            </motion.button>

            <AnimatePresence>
              {err && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="text-[11px] text-coral font-mono"
                >
                  {err}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Case 1 matched: offer "search again" with a different window */}
        {isCase1FromAudD && (
          <div className="pt-2 border-t border-border-soft/50">
            <details className="group/detail">
              <summary className="cursor-pointer font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute hover:text-text-dim transition-colors list-none flex items-center gap-2">
                <span>rerun on a different window</span>
                <span className="text-[10px] group-open/detail:rotate-180 transition-transform">▾</span>
              </summary>
              <div className="mt-4 space-y-4">
                <div>
                  <div className="flex items-baseline justify-between mb-2">
                    <label className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
                      Window start
                    </label>
                    <span className="font-mono tabular text-[11px] text-ember">
                      {windowStart === null
                        ? 'auto'
                        : `${fmtDuration(windowStart)} → ${fmtDuration(windowStart + windowLen)}`}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={maxStart}
                    step={1}
                    value={windowStart === null ? 0 : windowStart}
                    onChange={(e) => setWindowStart(Number(e.target.value))}
                    disabled={busy || maxStart === 0}
                    className="w-full accent-ember h-1"
                  />
                </div>
                <div className="flex gap-2">
                  <motion.button
                    whileTap={{ scale: 0.98 }}
                    onClick={runIdentify}
                    disabled={busy}
                    className="flex-1 rounded-lg bg-ember/20 border border-ember/40 hover:bg-ember/30 py-2
                               font-mono text-[11px] uppercase tracking-wider text-ember disabled:opacity-50"
                  >
                    {busy ? 'searching…' : 'search again'}
                  </motion.button>
                  <button
                    className="font-mono text-[10px] uppercase tracking-wider text-text-mute hover:text-ember transition-colors px-3"
                    onClick={() => setWindowStart(null)}
                    disabled={busy || windowStart === null}
                  >
                    auto
                  </button>
                </div>
                {err && <div className="text-[11px] text-coral font-mono">{err}</div>}
              </div>
            </details>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function StreamLink({ href, label }: { href: string; label: string }) {
  return (
    <motion.a
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg bg-music/10 border border-music/30
                 hover:bg-music/20 hover:border-music/50 px-3 py-1.5 transition-colors"
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-music">{label}</span>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M3 7l4-4M7 3H3.5M7 3v3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" className="text-music" />
      </svg>
    </motion.a>
  );
}

function GainSlider({ gain, onChange }: { gain: number; onChange: (v: number) => void }) {
  const clipping = gain > 2.5;
  return (
    <div className="flex items-center gap-3 px-1">
      <button
        onClick={() => onChange(1.0)}
        title="Reset to unity"
        className={`font-mono text-[9px] uppercase tracking-[0.2em] transition-colors
                    ${gain === 1.0 ? 'text-text-mute/60' : 'text-ember hover:text-ember-hot'}`}
      >
        boost
      </button>
      <input
        type="range"
        min={0.5}
        max={4}
        step={0.05}
        value={gain}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 accent-ember h-1"
        aria-label="Music playback gain"
      />
      <span className={`font-mono tabular text-[11px] w-12 text-right transition-colors
                        ${clipping ? 'text-coral' : gain === 1.0 ? 'text-text-mute' : 'text-ember'}`}>
        {gain.toFixed(2)}×
      </span>
    </div>
  );
}
