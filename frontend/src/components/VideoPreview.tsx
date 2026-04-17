import { useRef, useState } from 'react';
import { motion } from 'motion/react';

interface Props { src: string; }

/**
 * Hero video player for the extracted reel. Designed for vertical (9:16)
 * Instagram / YT Shorts aspect — centered on a glass frame with a soft
 * outer glow in the ember tone.
 */
export function VideoPreview({ src }: Props) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const [playing, setPlaying] = useState(false);

  return (
    <div className="relative rounded-3xl overflow-hidden border border-border/60 bg-surface/60 backdrop-blur-xl
                    shadow-[0_30px_80px_-30px_rgba(232,177,58,0.3)]">
      {/* Ember glow behind */}
      <div
        className="absolute -inset-16 -z-10 opacity-50 pointer-events-none"
        style={{
          background:
            'radial-gradient(closest-side at 50% 40%, rgba(232,177,58,0.25), transparent 70%)',
        }}
      />

      <div className="flex items-start gap-6 p-6">
        {/* Left: the video itself in a tall poster frame */}
        <div className="relative shrink-0 rounded-2xl overflow-hidden bg-black border border-border/40"
             style={{ width: 300, aspectRatio: '9 / 16' }}>
          <video
            ref={ref}
            src={src}
            className="w-full h-full object-cover"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            playsInline
          />
          {/* Custom play overlay when paused */}
          {!playing && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => ref.current?.play()}
              className="absolute inset-0 grid place-items-center bg-bg/20 backdrop-blur-[2px]"
            >
              <div className="relative w-20 h-20 rounded-full bg-ember/90 backdrop-blur grid place-items-center
                              shadow-[0_10px_40px_rgba(232,177,58,0.5)]">
                <div className="w-0 h-0 border-y-[14px] border-y-transparent border-l-[22px] border-l-bg ml-[4px]" />
                <div className="absolute inset-0 rounded-full border border-ember/50 animate-pulse" />
              </div>
            </motion.button>
          )}
          {/* Floating pause button when playing */}
          {playing && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={() => ref.current?.pause()}
              className="absolute bottom-4 right-4 w-10 h-10 rounded-full bg-bg/80 backdrop-blur border border-border/60
                         grid place-items-center hover:bg-bg transition-colors"
            >
              <div className="flex gap-[3px]">
                <div className="w-[3px] h-4 bg-text rounded-sm" />
                <div className="w-[3px] h-4 bg-text rounded-sm" />
              </div>
            </motion.button>
          )}
        </div>

        {/* Right: label + caption */}
        <div className="flex-1 min-w-0 pt-3">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1.5 h-1.5 rounded-full bg-ember animate-pulse" />
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-ember">
              source reel
            </span>
          </div>
          <h3 className="font-display font-light text-[30px] leading-[1.05] tracking-tighter text-text">
            The <span className="font-display-wonk italic text-ember">original</span>
          </h3>
          <p className="mt-3 text-[13px] text-text-dim leading-relaxed max-w-sm">
            Watch the full video while you browse the extracted stems. The audio
            playing here contains everything together — voice, music, and sfx.
          </p>
          <div className="mt-5 flex items-center gap-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-mute">
            <span>·</span>
            <span>vertical · 9:16</span>
            <span className="text-text-mute/40">·</span>
            <span>served locally</span>
          </div>
        </div>
      </div>
    </div>
  );
}
