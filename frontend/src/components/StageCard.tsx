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
  status: StageCardStatus;
  progress: number;
  message?: string;
  errorMessage?: string;
  color: string; // tailwind segment: 'speech' | 'music' | 'sfx' | 'accent'
}

// Hex for our brand colors so motion can derive gradients procedurally.
// (These match tailwind.config.ts exactly.)
const COLOR_HEX: Record<string, { base: string; bright: string }> = {
  accent: { base: '#7c83ff', bright: '#aab0ff' },
  speech: { base: '#60a5fa', bright: '#93c5fd' },
  sfx:    { base: '#f472b6', bright: '#fb9cc9' },
  music:  { base: '#fbbf24', bright: '#fde68a' },
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

export function StageCard({ title, status, progress, message, errorMessage, color }: Props) {
  const borderClass =
    status === 'done' ? 'border-good/50' :
    status === 'error' ? 'border-red-500/60' :
    status === 'running' ? `border-${color}` :
    'border-border-soft';

  return (
    <motion.div
      layout
      className={`bg-surface-2 border ${borderClass} rounded-xl p-4 space-y-3`}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{title}</div>
        <StatusDot status={status} color={color} />
      </div>

      {status === 'running' && (
        <>
          <WaveAnim colorKey={color} />
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1 bg-surface-3 rounded overflow-hidden">
              <motion.div
                className={`h-full bg-${color}`}
                animate={{ width: `${Math.round(progress * 100)}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
            <div className="text-[11px] tabular-nums text-text-mute font-mono shrink-0">
              {Math.round(progress * 100)}%
            </div>
          </div>
          {message && (
            <div className="text-[11px] text-text-mute truncate" title={message}>
              {message}
            </div>
          )}
        </>
      )}
      {status === 'error' && (
        <div className="text-[11px] text-red-400 whitespace-pre-wrap break-words leading-relaxed max-h-32 overflow-auto font-mono">
          {errorMessage}
        </div>
      )}
      {status === 'done' && <div className="text-[11px] text-good">Done</div>}
    </motion.div>
  );
}

function StatusDot({ status, color }: { status: StageCardStatus; color: string }) {
  if (status === 'done') return <div className="w-2 h-2 rounded-full bg-good" />;
  if (status === 'error') return <div className="w-2 h-2 rounded-full bg-red-500" />;
  if (status === 'running') return <div className={`w-2 h-2 rounded-full bg-${color} animate-pulse`} />;
  return <div className="w-2 h-2 rounded-full bg-text-mute/40" />;
}
