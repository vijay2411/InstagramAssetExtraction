import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useConfig } from '@/hooks/useConfig';

export function Settings() {
  const { config, update } = useConfig();
  const [open, setOpen] = useState(false);
  if (!config) return null;

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="group w-full flex items-center gap-2 text-left"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-mute group-hover:text-text-dim transition-colors">
          Settings
        </span>
        <div className="flex-1 h-px bg-border/50" />
        <motion.span
          animate={{ rotate: open ? 45 : 0 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="font-mono text-sm text-text-mute"
        >
          +
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="pt-4 space-y-5">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute mb-2">
                  Device
                </div>
                <div className="flex gap-1 bg-surface/60 p-1 rounded-lg border border-border/60">
                  {(['mps', 'cpu'] as const).map((d) => (
                    <motion.button
                      key={d}
                      whileTap={{ scale: 0.96 }}
                      onClick={() => update({ demucs_device: d })}
                      className={`flex-1 text-[11px] py-1.5 rounded-md font-mono uppercase tracking-wider transition
                        ${config.demucs_device === d
                          ? 'bg-ember text-bg font-semibold shadow-[0_4px_12px_-4px_rgba(232,177,58,0.5)]'
                          : 'text-text-mute hover:text-text-dim'
                        }`}
                    >
                      {d}
                    </motion.button>
                  ))}
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
                    SFX repeats
                  </div>
                  <div className="font-mono tabular text-ember text-sm">{config.sfx_min_cluster_size}</div>
                </div>
                <input
                  type="range"
                  min={2} max={5} step={1}
                  value={config.sfx_min_cluster_size}
                  onChange={(e) => update({ sfx_min_cluster_size: Number(e.target.value) })}
                  className="w-full accent-ember h-1"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
