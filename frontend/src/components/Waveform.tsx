import { useEffect, useImperativeHandle, useRef, forwardRef, useState } from 'react';
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

export const Waveform = forwardRef<WaveformHandle, Props>(function Waveform({ url, color, waveColor, height = 44 }, ref) {
  const el = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const instance = WaveSurfer.create({
      container: el.current,
      url,
      waveColor: waveColor ?? `${color}60`,
      progressColor: color,
      height,
      barWidth: 2,
      barGap: 2,
      barRadius: 1,
      cursorColor: color,
      interact: true,
    });
    instance.on('play', () => setPlaying(true));
    instance.on('pause', () => setPlaying(false));
    instance.on('finish', () => setPlaying(false));
    ws.current = instance;
    return () => { instance.destroy(); };
  }, [url, color, waveColor, height]);

  useImperativeHandle(ref, () => ({
    playPause: () => ws.current?.playPause(),
  }));

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => ws.current?.playPause()}
        className="w-9 h-9 rounded-full bg-surface-3 border border-border grid place-items-center shrink-0"
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? (
          <div className="flex gap-0.5"><div className="w-1 h-3 bg-text" /><div className="w-1 h-3 bg-text" /></div>
        ) : (
          <div className="w-0 h-0 border-y-[6px] border-y-transparent border-l-[9px] border-l-text ml-[2px]" />
        )}
      </button>
      <div ref={el} className="flex-1 min-w-0" />
    </div>
  );
});
