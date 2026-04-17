import { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import WaveSurfer from 'wavesurfer.js';
import { fmtDurationPrecise } from '@/lib/format';

interface Props {
  url: string;
  repeats: number;
  duration: number;
  index: number;
}

const SFX = '#ff8a5b';

export function SfxTile({ url, repeats, duration, index }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const instance = WaveSurfer.create({
      container: el.current,
      url,
      waveColor: `${SFX}40`,
      progressColor: SFX,
      height: 36,
      barWidth: 1.8,
      barGap: 1.8,
      barRadius: 1,
      cursorColor: SFX,
      interact: true,
    });
    instance.on('play',   () => setPlaying(true));
    instance.on('pause',  () => setPlaying(false));
    instance.on('finish', () => setPlaying(false));
    ws.current = instance;
    return () => { instance.destroy(); };
  }, [url]);

  return (
    <motion.button
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 340, damping: 22 }}
      onClick={() => ws.current?.playPause()}
      className="group w-full text-left rounded-xl border border-border/60 bg-surface-2/60
                 hover:border-sfx/60 hover:bg-surface-2/90 transition-colors p-4 space-y-2.5"
      style={{
        boxShadow: playing ? `0 12px 40px -12px ${SFX}55` : undefined,
      }}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-sfx">
          sfx_{String(index).padStart(2, '0')}
        </span>
        <span className="font-mono tabular text-[10px] text-text-mute">
          ×{repeats}
        </span>
      </div>
      <div ref={el} className="relative" />
      <div className="flex items-center justify-between">
        <span className="font-mono tabular text-[10px] text-text-mute">
          {fmtDurationPrecise(duration)}
        </span>
        <span className={`font-mono text-[10px] transition-colors ${playing ? 'text-sfx' : 'text-text-mute/60'}`}>
          {playing ? '▶ playing' : 'tap to play'}
        </span>
      </div>
    </motion.button>
  );
}
