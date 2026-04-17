import { motion } from 'motion/react';
import type { Manifest } from '@/lib/api';
import { api } from '@/lib/api';
import { SfxTile } from './SfxTile';

interface Props { manifest: Manifest; jobDirName: string; }

export function SfxGrid({ manifest, jobDirName }: Props) {
  const sfx = manifest.assets.sfx;
  return (
    <div className="rounded-2xl border border-border/60 bg-surface/70 backdrop-blur-xl p-6">
      <div className="flex items-end justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-1.5 h-1.5 rounded-full bg-sfx" />
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-sfx">sfx</span>
          </div>
          <h3 className="font-display text-[28px] leading-[1.05] font-light tracking-tighter text-text">
            Sound effects
          </h3>
          <div className="mt-1.5 font-mono text-[11px] text-text-mute tracking-tight">
            {sfx.length} deduped · repetition-mined
          </div>
        </div>
      </div>
      {sfx.length === 0 ? (
        <div className="font-mono text-[11px] text-text-mute italic">no repeated sfx detected in this reel.</div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {sfx.map((s, i) => (
            <motion.div
              key={s.path}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.04 }}
            >
              <SfxTile
                url={api.assetUrl(jobDirName, s.path)}
                repeats={s.repeats}
                duration={s.duration}
                index={i + 1}
              />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
