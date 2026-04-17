import { useRef, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';

/**
 * A playable toy that lives under the processing stages so the user has
 * something to fidget with while Demucs crunches. Three horizontal "strings"
 * — speech blue, music amber, sfx coral — each with a draggable bead at the
 * center. Drag the bead: the string curves toward it via SVG quadratic
 * bezier. Release: the bead snaps back with spring physics (motion.dev's
 * dragSnapToOrigin + bounceStiffness), the string trails slightly behind
 * (useSpring lag), and a pulse ring fires like a plucked note.
 *
 * Each string has different stiffness/damping so they feel distinct — the
 * "sfx" string is thin and snappy, "music" is medium, "speech" is thick.
 */
export function PluckToy() {
  return (
    <div className="mt-10 rounded-2xl border border-border/60 bg-surface/30 backdrop-blur-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-mute">
          while you wait
        </span>
        <div className="flex-1 h-px bg-border/50" />
        <span className="font-mono text-[10px] italic text-text-mute/70">
          drag, pluck, release
        </span>
      </div>
      <div className="space-y-5">
        <String color="#80b5ff" label="speech" stiffness={180} damping={11} />
        <String color="#e8b13a" label="music"  stiffness={140} damping={14} />
        <String color="#ff8a5b" label="sfx"    stiffness={260} damping={7}  />
      </div>
    </div>
  );
}

interface StringProps {
  color: string;
  label: string;
  stiffness: number;
  damping: number;
}

function String({ color, label, stiffness, damping }: StringProps) {
  // handleY: raw drag offset in px. stringY: slightly-lagged spring of handleY
  // so the visual string trails the bead — gives a plucked-guitar feel.
  const handleY = useMotionValue(0);
  const stringY = useSpring(handleY, {
    stiffness: stiffness * 0.85,
    damping: damping * 1.15,
    mass: 0.8,
  });

  // SVG path d: quadratic bezier from (0, 40) to (1000, 40) with control
  // point at (500, 40 + y * 2). Doubling the offset exaggerates the curve
  // compared to the bead's drag distance — looks more "plucked".
  const pathD = useTransform(
    stringY,
    (y) => `M 0 40 Q 500 ${40 + y * 2} 1000 40`,
  );

  // Each pluck release bumps pluckKey so the pulse ring re-renders.
  const [pluckKey, setPluckKey] = useState(0);
  const lastOffset = useRef(0);

  return (
    <div className="relative h-16 select-none">
      {/* Label on the left */}
      <div className="absolute left-0 top-1/2 -translate-y-1/2 font-mono text-[9px] uppercase tracking-[0.2em] text-text-mute/60 w-14">
        {label}
      </div>

      {/* The string itself — SVG spans the whole width, overflow-visible so
          the drop-shadow glow doesn't clip */}
      <svg
        viewBox="0 0 1000 80"
        preserveAspectRatio="none"
        className="absolute left-14 right-0 top-0 h-full overflow-visible"
      >
        <motion.path
          d={pathD}
          stroke={color}
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 10px ${color}80)` }}
        />
        {/* Faint ghost line so you can see where the baseline is */}
        <line x1="0" y1="40" x2="1000" y2="40" stroke={color} strokeOpacity="0.08" strokeWidth="1" />
      </svg>

      {/* Draggable bead — positioned at the midpoint of the string */}
      <div
        className="absolute left-[calc(50%+28px)] top-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ willChange: 'transform' }}
      >
        <motion.button
          drag="y"
          dragConstraints={{ top: -36, bottom: 36 }}
          dragElastic={0.4}
          dragSnapToOrigin
          dragTransition={{ bounceStiffness: stiffness, bounceDamping: damping }}
          style={{ y: handleY, background: color }}
          className="block w-5 h-5 rounded-full cursor-grab active:cursor-grabbing border border-white/10"
          whileHover={{ scale: 1.4 }}
          whileTap={{ scale: 1.15 }}
          animate={{
            boxShadow: `0 0 18px ${color}aa, 0 0 2px ${color}`,
          }}
          onDragStart={() => { lastOffset.current = 0; }}
          onDrag={(_e, info) => { lastOffset.current = info.offset.y; }}
          onDragEnd={() => {
            // Only fire a pluck pulse if there was meaningful movement.
            if (Math.abs(lastOffset.current) > 6) {
              setPluckKey((k) => k + 1);
            }
          }}
          aria-label={`Pluck ${label}`}
        />
      </div>

      {/* Pluck pulse ring — re-mounts on every release, fires an outward ring */}
      {pluckKey > 0 && (
        <motion.div
          key={pluckKey}
          initial={{ scale: 0.4, opacity: 0.9 }}
          animate={{ scale: 4.5, opacity: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          className="absolute left-[calc(50%+28px)] top-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full border-[1.5px] pointer-events-none"
          style={{ borderColor: color }}
        />
      )}
    </div>
  );
}
