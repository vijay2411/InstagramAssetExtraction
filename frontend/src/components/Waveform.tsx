import { useEffect, useImperativeHandle, useRef, forwardRef, useState } from 'react';
import { motion } from 'motion/react';
import WaveSurfer from 'wavesurfer.js';

export interface WaveformHandle {
  playPause: () => void;
}

interface Props {
  url: string;
  color: string;        // hex or css color
  waveColor?: string;
  height?: number;
}

export const Waveform = forwardRef<WaveformHandle, Props>(function Waveform(
  { url, color, waveColor, height = 72 },
  ref,
) {
  const el = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const instance = WaveSurfer.create({
      container: el.current,
      url,
      waveColor: waveColor ?? `${color}40`,
      progressColor: color,
      height,
      barWidth: 2.5,
      barGap: 2.5,
      barRadius: 2,
      cursorColor: `${color}`,
      cursorWidth: 2,
      interact: true,
    });
    instance.on('ready', () => setReady(true));
    instance.on('play',   () => setPlaying(true));
    instance.on('pause',  () => setPlaying(false));
    instance.on('finish', () => setPlaying(false));
    ws.current = instance;
    return () => { instance.destroy(); };
  }, [url, color, waveColor, height]);

  useImperativeHandle(ref, () => ({
    playPause: () => ws.current?.playPause(),
  }));

  return (
    <div className="flex items-center gap-4">
      {/* Larger play button with color ring + glow */}
      <motion.button
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.94 }}
        onClick={() => ws.current?.playPause()}
        className="relative shrink-0 w-14 h-14 rounded-full grid place-items-center transition-colors border"
        style={{
          borderColor: `${color}55`,
          background: playing
            ? `radial-gradient(circle at 50% 50%, ${color}40, ${color}10)`
            : 'rgba(255,255,255,0.03)',
          boxShadow: playing
            ? `0 0 0 6px ${color}15, 0 8px 28px ${color}40`
            : `0 4px 16px ${color}20`,
        }}
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? (
          <div className="flex gap-1">
            <div className="w-[3px] h-5 rounded-[1px]" style={{ background: color }} />
            <div className="w-[3px] h-5 rounded-[1px]" style={{ background: color }} />
          </div>
        ) : (
          <div
            className="w-0 h-0 ml-1"
            style={{
              borderTop: '8px solid transparent',
              borderBottom: '8px solid transparent',
              borderLeft: `13px solid ${color}`,
            }}
          />
        )}
        {/* Outer pulse ring while playing */}
        {playing && (
          <motion.div
            initial={{ scale: 1, opacity: 0.6 }}
            animate={{ scale: 1.4, opacity: 0 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
            className="absolute inset-0 rounded-full border-2 pointer-events-none"
            style={{ borderColor: color }}
          />
        )}
      </motion.button>

      <div className="flex-1 min-w-0 relative">
        {/* Skeleton until wavesurfer decodes */}
        {!ready && (
          <div className="absolute inset-0 flex items-center gap-1">
            {Array.from({ length: 48 }).map((_, i) => (
              <div
                key={i}
                className="flex-1 rounded-sm shimmer-ember"
                style={{ height: `${20 + (i * 7) % 50}%`, background: `${color}15` }}
              />
            ))}
          </div>
        )}
        <div ref={el} className="w-full" />
      </div>
    </div>
  );
});
