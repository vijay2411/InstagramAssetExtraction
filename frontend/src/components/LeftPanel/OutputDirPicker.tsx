import { useState } from 'react';
import { motion } from 'motion/react';
import { useConfig } from '@/hooks/useConfig';

export function OutputDirPicker() {
  const { config, update } = useConfig();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');

  if (!config) return null;

  async function save() {
    await update({ output_base_dir: value });
    setEditing(false);
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2">
        <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-mute">
          Output
        </label>
        <div className="flex-1 h-px bg-border/50" />
      </div>
      {editing ? (
        <div className="space-y-2">
          <input
            className="w-full bg-surface border border-ember/40 rounded-lg px-3 py-2 text-xs font-mono
                       placeholder:text-text-mute focus:border-ember focus:ring-2 focus:ring-ember/10 outline-none"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="~/Desktop/assets"
            autoFocus
          />
          <div className="flex gap-2">
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={save}
              className="text-[11px] font-mono bg-ember text-bg rounded-md px-3 py-1 font-semibold"
            >
              save
            </motion.button>
            <button
              onClick={() => setEditing(false)}
              className="text-[11px] font-mono text-text-mute hover:text-text transition-colors"
            >
              cancel
            </button>
          </div>
        </div>
      ) : (
        <motion.div
          whileHover={{ borderColor: 'rgba(232,177,58,0.5)' }}
          className="flex items-center justify-between bg-surface/60 border border-border-soft rounded-lg px-3 py-2.5
                     transition-colors cursor-pointer"
          onClick={() => { setValue(config.output_base_dir); setEditing(true); }}
        >
          <div className="text-[11px] font-mono text-text-dim truncate">{config.output_base_dir}</div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-ember/80 ml-2">edit</div>
        </motion.div>
      )}
    </div>
  );
}
