import { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { fmtDurationPrecise } from '@/lib/format';

interface Props {
  url: string;
  repeats: number;
  duration: number;
  index: number;
}

export function SfxTile({ url, repeats, duration, index }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const instance = WaveSurfer.create({
      container: el.current,
      url,
      waveColor: '#f472b660',
      progressColor: '#f472b6',
      height: 28,
      barWidth: 1.5,
      barGap: 1.5,
      cursorColor: '#f472b6',
      interact: true,
    });
    instance.on('play', () => setPlaying(true));
    instance.on('pause', () => setPlaying(false));
    instance.on('finish', () => setPlaying(false));
    ws.current = instance;
    return () => { instance.destroy(); };
  }, [url]);

  return (
    <button
      onClick={() => ws.current?.playPause()}
      className="bg-surface-3 border border-border-soft rounded-xl p-3 text-left hover:border-sfx transition-colors"
    >
      <div ref={el} className="mb-2" />
      <div className="flex justify-between text-[10px] text-text-mute font-mono">
        <span>sfx_{String(index).padStart(2, '0')}</span>
        <span>×{repeats} · {fmtDurationPrecise(duration)}</span>
      </div>
      {playing && <div className="text-[10px] text-sfx mt-1">Playing…</div>}
    </button>
  );
}
