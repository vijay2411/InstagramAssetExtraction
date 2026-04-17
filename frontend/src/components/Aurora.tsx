import { useRef } from 'react';
import { motion, useMotionValue, useAnimationFrame, useTransform } from 'motion/react';
import { createNoise2D } from 'simplex-noise';

/**
 * Ambient background: three large blurred color orbs that drift slowly
 * through a simplex-noise field. Drift driven by useAnimationFrame +
 * useMotionValue so no re-render churn; orbs reposition via CSS transforms
 * every frame. A noise-grain SVG + a dot grid sit on top for texture.
 *
 * Palette intentionally avoids purple — warm amber / coral / plum / sea.
 * This is the whole room the app lives in; it should feel like a space.
 */
export function Aurora() {
  return (
    // z-0, not -z-10 — previously the body's bg-bg covered the orbs entirely.
    // Aurora paints the base color itself so we don't need body bg.
    <div className="fixed inset-0 z-0 overflow-hidden bg-bg pointer-events-none">
      {/* Deep warm base wash — two dominant color pools plus a vertical gradient */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(1400px 900px at 25% 15%, rgba(232,177,58,0.18), transparent 62%),' +
            'radial-gradient(1100px 800px at 82% 88%, rgba(255,138,91,0.14), transparent 58%),' +
            'radial-gradient(900px 700px at 50% 50%, rgba(159,76,109,0.10), transparent 65%),' +
            'linear-gradient(180deg, #0b0908 0%, #15100b 50%, #0b0908 100%)',
        }}
      />

      {/* Three drifting orbs — stronger alpha now that we're above body bg */}
      <DriftOrb seed={3}  color="#e8b13a" size={720} baseX="18vw" baseY="22vh" />
      <DriftOrb seed={11} color="#ff8a5b" size={640} baseX="78vw" baseY="72vh" speed={0.35} />
      <DriftOrb seed={19} color="#9f4c6d" size={820} baseX="46vw" baseY="52vh" speed={0.22} />

      {/* Texture overlays */}
      <div className="absolute inset-0 dot-grid" />
      <div className="absolute inset-0 noise-grain" />

      {/* Vignette — pulls focus toward center */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(closest-side at 50% 50%, transparent 55%, rgba(11,9,8,0.55) 100%)',
        }}
      />
    </div>
  );
}

interface OrbProps {
  seed: number;
  color: string;
  size: number;
  baseX: string;
  baseY: string;
  speed?: number;
}

function DriftOrb({ seed, color, size, baseX, baseY, speed = 0.5 }: OrbProps) {
  // Raw noise value in range [-1, 1], which we map to a ±16% translate.
  const nx = useMotionValue(0);
  const ny = useMotionValue(0);
  const tx = useTransform(nx, (v) => `${v * 16}%`);
  const ty = useTransform(ny, (v) => `${v * 16}%`);
  const noise = useRef(createNoise2D()).current;

  useAnimationFrame((t) => {
    const seconds = t / 1000;
    nx.set(noise(seed, seconds * 0.05 * speed));
    ny.set(noise(seed + 99, seconds * 0.04 * speed));
  });

  return (
    <motion.div
      className="aurora-orb"
      style={{
        width: size,
        height: size,
        // Base position: absolute top-left at baseX/baseY minus half-size.
        // Orb drifts around that anchor via transform.
        left: `calc(${baseX} - ${size / 2}px)`,
        top:  `calc(${baseY} - ${size / 2}px)`,
        x: tx,
        y: ty,
        background: `radial-gradient(circle at 50% 50%, ${color}66 0%, ${color}33 40%, transparent 72%)`,
      }}
    />
  );
}
