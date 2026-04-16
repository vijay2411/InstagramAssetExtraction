import { useState } from 'react';
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
    <div className="space-y-2">
      <label className="block text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold">Output directory</label>
      {editing ? (
        <div className="space-y-2">
          <input
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs font-mono placeholder:text-text-mute focus:border-accent outline-none"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="~/Desktop/assets"
          />
          <div className="flex gap-2">
            <button onClick={save} className="text-xs bg-accent text-white rounded px-3 py-1">Save</button>
            <button onClick={() => setEditing(false)} className="text-xs text-text-dim">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between bg-surface-2 border border-border-soft rounded-lg px-3 py-2">
          <div className="text-xs font-mono text-text-dim truncate">{config.output_base_dir}</div>
          <button
            onClick={() => { setValue(config.output_base_dir); setEditing(true); }}
            className="text-[11px] text-accent hover:underline ml-2"
          >
            Change
          </button>
        </div>
      )}
    </div>
  );
}
