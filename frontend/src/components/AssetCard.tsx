import type { ReactNode } from 'react';
import { motion } from 'motion/react';

interface Props {
  title: string;
  subtitle?: string;
  label: string;                 // short tag shown in upper-left (e.g. "speech")
  color: 'speech' | 'music' | 'sfx';
  children: ReactNode;
  downloadUrl?: string;
  downloadName?: string;
}

const DOT = { speech: 'bg-speech', music: 'bg-music', sfx: 'bg-sfx' } as const;
const RING = {
  speech: 'shadow-[0_20px_50px_-20px_rgba(128,181,255,0.4)]',
  music:  'shadow-[0_20px_50px_-20px_rgba(232,177,58,0.45)]',
  sfx:    'shadow-[0_20px_50px_-20px_rgba(255,138,91,0.45)]',
} as const;

export function AssetCard({
  title, subtitle, label, color, children,
  downloadUrl, downloadName,
}: Props) {
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
      className={`group relative overflow-hidden rounded-2xl border border-border/60 bg-surface/70 backdrop-blur-xl
                  hover:border-${color}/50 transition-colors ${RING[color]}`}
    >
      {/* Top gradient glow (revealed on hover) */}
      <div
        className="absolute inset-x-0 -top-24 h-48 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background: `radial-gradient(600px 200px at 50% 100%, ${colorHex(color)}22 0%, transparent 70%)`,
        }}
      />

      <div className="relative p-6 space-y-5">
        {/* Header: label chip + title + download */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-1.5 h-1.5 rounded-full ${DOT[color]}`} />
              <span className={`font-mono text-[10px] uppercase tracking-[0.25em] text-${color}`}>
                {label}
              </span>
            </div>
            <h3 className="font-display text-[28px] leading-[1.05] font-light tracking-tighter text-text truncate">
              {title}
            </h3>
            {subtitle && (
              <div className="mt-1.5 font-mono text-[11px] text-text-mute tracking-tight truncate">
                {subtitle}
              </div>
            )}
          </div>
          {downloadUrl && (
            <motion.a
              whileHover={{ y: -1, scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
              href={downloadUrl}
              download={downloadName}
              className={`shrink-0 flex items-center gap-2 rounded-lg border border-border/60 bg-surface-3/80
                          hover:border-${color} hover:bg-${color}/10 px-3 py-2 text-[11px] font-mono
                          uppercase tracking-wider text-text-dim hover:text-text transition-colors`}
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1.5v7M3 6l3 3 3-3M1.5 10.5h9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              wav
            </motion.a>
          )}
        </div>

        {/* The playable body (waveform) */}
        <div>{children}</div>
      </div>
    </motion.div>
  );
}

function colorHex(color: 'speech' | 'music' | 'sfx'): string {
  return { speech: '#80b5ff', music: '#e8b13a', sfx: '#ff8a5b' }[color];
}
