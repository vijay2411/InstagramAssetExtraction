import { motion } from 'motion/react';
import { UrlInput } from './UrlInput';
import { OutputDirPicker } from './OutputDirPicker';
import { Settings } from './Settings';

export function LeftPanel() {
  return (
    <aside className="relative border-r border-border/60 bg-surface/40 backdrop-blur-xl p-8 flex flex-col gap-10">
      {/* Brand mark — serif wordmark with a deliberate WONK italic on the second word */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="flex flex-col gap-1"
      >
        <div className="flex items-baseline gap-2">
          <span className="font-display text-3xl font-semibold tracking-display">Extract</span>
          <span className="font-display-wonk text-3xl italic text-ember tracking-display">Assets</span>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
          three layers · one reel
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
      >
        <UrlInput />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.14, ease: [0.22, 1, 0.36, 1] }}
      >
        <OutputDirPicker />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
      >
        <Settings />
      </motion.div>

      {/* Colophon at bottom */}
      <div className="mt-auto font-mono text-[9px] uppercase tracking-[0.25em] text-text-mute/60 leading-relaxed">
        <div>demucs · librosa · yt-dlp</div>
        <div className="mt-1 text-text-mute/40">local · no keys · no telemetry</div>
      </div>
    </aside>
  );
}
