import { useEffect, useMemo, useRef } from 'react';
import {
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  useAnimationFrame,
} from 'motion/react';
import { createNoise2D, type NoiseFunction2D } from 'simplex-noise';
import { stagger, createTimeline } from 'animejs';

export type StageCardStatus = 'pending' | 'running' | 'done' | 'error';

interface Props {
  title: string;
  subtitle?: string;
  status: StageCardStatus;
  progress: number;
  message?: string;
  errorMessage?: string;
  color: string; // tailwind segment: 'speech' | 'music' | 'sfx' | 'ember'
}

// Hex for our brand colors so motion can derive gradients procedurally.
// (These match tailwind.config.ts exactly.)
const COLOR_HEX: Record<string, { base: string; bright: string }> = {
  ember:  { base: '#e8b13a', bright: '#ffc85a' },
  speech: { base: '#80b5ff', bright: '#b4d1ff' },
  sfx:    { base: '#ff8a5b', bright: '#ffb089' },
  music:  { base: '#e8b13a', bright: '#ffc85a' },
  // legacy alias
  accent: { base: '#e8b13a', bright: '#ffc85a' },
};

const BAR_COUNT = 40;

/**
 * One bar of the live waveform. Self-contained:
 * - holds its own MotionValue for height,
 * - updates every frame from simplex noise,
 * - derives opacity + color from the same value,
 * - springs the raw output for organic lag/overshoot.
 *
 * Each bar calls useAnimationFrame, but motion multiplexes all subscribers onto
 * a single global RAF loop, so 40 bars ≈ 1 actual RAF call per frame.
 */
function Bar({
  index,
  noise,
  color,
}: {
  index: number;
  noise: NoiseFunction2D;
  color: { base: string; bright: string };
}) {
  const h = useMotionValue(30);
  const springH = useSpring(h, { stiffness: 180, damping: 18, mass: 0.6 });
  const heightPct = useTransform(springH, (v) => `${Math.max(6, Math.min(100, v))}%`);
  const opacity = useTransform(springH, [10, 100], [0.35, 1]);
  const bg = useTransform(springH, [20, 90], [color.base, color.bright]);

  // Envelope pulls middle bars higher than edges for a nicer overall silhouette.
  const envelope = 0.75 + 0.25 * Math.sin((index / BAR_COUNT) * Math.PI);

  useAnimationFrame((t) => {
    const seconds = t / 1000;
    // Two octaves of simplex noise for richer, less-repeating texture.
    const n1 = noise(index * 0.28, seconds * 0.9);
    const n2 = noise(index * 0.07 + 11.3, seconds * 0.35);
    const raw = 0.5 + 0.5 * (0.7 * n1 + 0.3 * n2);
    h.set(12 + raw * 78 * envelope);
  });

  return (
    <div
      data-scan
      className="flex-1 flex items-end will-change-transform"
      style={{ transformOrigin: 'bottom center' }}
    >
      <motion.div
        className="flex-1 rounded-[2px]"
        style={{ height: heightPct, opacity, background: bg }}
      />
    </div>
  );
}

/**
 * Layer 2 on top of the noise-driven bars: an anime.js traveling "scan" pulse
 * that sweeps across the row every ~2s. Each bar scales + brightens briefly as
 * the pulse passes, using stagger() for the sweep timing. This gives the
 * "something is happening" impression on top of the ambient noise motion.
 */
function WaveAnim({ colorKey }: { colorKey: string }) {
  const color = COLOR_HEX[colorKey] ?? COLOR_HEX.accent;
  const rowRef = useRef<HTMLDivElement | null>(null);
  // Stable noise function for this component instance.
  const noise = useMemo(() => createNoise2D(), []);
  // Stable bar index list.
  const indices = useMemo(() => Array.from({ length: BAR_COUNT }, (_, i) => i), []);

  useEffect(() => {
    const row = rowRef.current;
    if (!row) return;
    const bars = row.querySelectorAll<HTMLElement>('[data-scan]');
    if (bars.length === 0) return;

    const tl = createTimeline({ loop: true, defaults: { ease: 'inOutQuad' } })
      .add(bars, {
        scale: [
          { to: 1, duration: 0 },
          { to: 1.45, duration: 260 },
          { to: 1, duration: 340 },
        ],
        filter: [
          { to: 'brightness(1)', duration: 0 },
          { to: 'brightness(1.9)', duration: 260 },
          { to: 'brightness(1)', duration: 340 },
        ],
      }, stagger(38))
      .add({ duration: 1400 }); // pause between sweeps

    return () => {
      tl.pause();
    };
  }, []);

  return (
    <div ref={rowRef} className="relative flex items-end gap-[3px] h-10 overflow-hidden">
      {indices.map((i) => (
        <Bar key={i} index={i} noise={noise} color={color} />
      ))}
    </div>
  );
}

export function StageCard({ title, subtitle, status, progress, message, errorMessage, color }: Props) {
  const isRunning = status === 'running';
  const isDone = status === 'done';
  const isError = status === 'error';

  const borderClass =
    isDone ? 'border-good/40' :
    isError ? 'border-coral/60' :
    isRunning ? `border-${color}/60` :
    'border-border/70';

  const bgClass =
    isDone ? 'bg-surface/60' :
    isRunning ? 'bg-surface/80' :
    'bg-surface/30';

  return (
    <motion.div
      layout
      className={`relative overflow-hidden rounded-2xl border ${borderClass} ${bgClass} backdrop-blur-xl p-5 transition-colors`}
      transition={{ duration: 0.25 }}
    >
      {/* Left color bar — stage accent */}
      <div
        className={`absolute left-0 top-0 bottom-0 w-[3px] bg-${color} opacity-60 ${isRunning ? 'shadow-[0_0_24px] shadow-' + color + '/60' : ''}`}
      />

      <div className="flex items-start gap-4 pl-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3">
            <h3 className="font-display text-xl font-medium tracking-tighter text-text">{title}</h3>
            {subtitle && (
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute/80 truncate">
                {subtitle}
              </div>
            )}
          </div>
        </div>
        <StatusBadge status={status} color={color} progress={progress} />
      </div>

      {isRunning && (
        <div className="mt-4 pl-2 space-y-3">
          <WaveAnim colorKey={color} />
          {message && (
            <div className="font-mono text-[10.5px] text-text-mute truncate tracking-tight" title={message}>
              {message}
            </div>
          )}
        </div>
      )}
      {isError && (
        <div className="mt-4 pl-2">
          <div className="font-mono text-[11px] text-coral whitespace-pre-wrap break-words leading-relaxed max-h-32 overflow-auto rounded-lg bg-coral/5 border border-coral/20 p-3">
            {errorMessage}
          </div>
        </div>
      )}
      {isDone && (
        <div className="mt-3 pl-2 font-mono text-[10px] uppercase tracking-[0.2em] text-good/80">
          done
        </div>
      )}
    </motion.div>
  );
}

function StatusBadge({
  status,
  color,
  progress,
}: {
  status: StageCardStatus;
  color: string;
  progress: number;
}) {
  if (status === 'done') {
    return (
      <div className="w-8 h-8 rounded-full bg-good/15 border border-good/40 grid place-items-center">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 6.5l2.5 2.5L9.5 3.5" stroke="#6ad99a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div className="w-8 h-8 rounded-full bg-coral/15 border border-coral/40 grid place-items-center">
        <div className="w-3 h-[1.5px] bg-coral rounded-full" />
      </div>
    );
  }
  if (status === 'running') {
    return (
      <div className="shrink-0 flex items-center gap-2">
        <div className="font-mono text-[11px] tabular text-text">
          {Math.round(progress * 100)}%
        </div>
        <div className={`w-2.5 h-2.5 rounded-full bg-${color} animate-pulse shadow-[0_0_12px] shadow-${color}/80`} />
      </div>
    );
  }
  return <div className="w-2 h-2 rounded-full bg-text-mute/30" />;
}
