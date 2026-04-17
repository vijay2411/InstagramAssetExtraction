import { motion } from 'motion/react';

export function IdleState() {
  return (
    <div className="h-full flex items-center px-10 py-16">
      <div className="max-w-3xl">
        {/* The three stems, announced as typographic equation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="flex items-center gap-2 mb-8 flex-wrap"
        >
          <StemChip color="speech" label="speech" />
          <Plus />
          <StemChip color="music"  label="music" />
          <Plus />
          <StemChip color="sfx"    label="sfx" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="font-display font-light text-display-lg tracking-display text-text"
        >
          Three layers.
          <br />
          <span className="font-display-wonk italic text-ember">One reel.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="mt-8 max-w-xl text-[15px] text-text-dim leading-relaxed"
        >
          Drop any Instagram Reel or YouTube Short link. We'll pull the creator's
          voice, the background music, and the sound effects out as separate,
          playable assets — all locally, no keys, no telemetry.
        </motion.p>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="mt-12 font-mono text-[11px] uppercase tracking-[0.2em] text-text-mute/80 flex items-center gap-3"
        >
          <span className="inline-block w-8 h-px bg-ember/50" />
          paste a link on the left to begin
        </motion.div>
      </div>
    </div>
  );
}

function StemChip({ color, label }: { color: 'speech' | 'music' | 'sfx'; label: string }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border border-${color}/30 bg-${color}/10 backdrop-blur-sm`}>
      <div className={`w-1.5 h-1.5 rounded-full bg-${color}`} />
      <span className={`font-mono text-[10px] uppercase tracking-[0.2em] text-${color}`}>{label}</span>
    </div>
  );
}

function Plus() {
  return <span className="font-mono text-text-mute/40 text-xs">+</span>;
}
