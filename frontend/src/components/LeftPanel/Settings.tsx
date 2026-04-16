import { useState } from 'react';
import { useConfig } from '@/hooks/useConfig';

export function Settings() {
  const { config, update } = useConfig();
  const [open, setOpen] = useState(false);
  if (!config) return null;

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold flex items-center justify-between"
      >
        <span>Settings</span>
        <span>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          <div>
            <div className="text-xs text-text-dim mb-1">Demucs device</div>
            <div className="flex gap-1 bg-surface-2 p-1 rounded-lg border border-border-soft">
              {(['mps', 'cpu'] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => update({ demucs_device: d })}
                  className={`flex-1 text-xs py-1 rounded ${config.demucs_device === d ? 'bg-accent text-white' : 'text-text-dim'}`}
                >
                  {d.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-text-dim mb-1">
              SFX min repeats: <span className="font-mono text-text">{config.sfx_min_cluster_size}</span>
            </div>
            <input
              type="range"
              min={2} max={5} step={1}
              value={config.sfx_min_cluster_size}
              onChange={(e) => update({ sfx_min_cluster_size: Number(e.target.value) })}
              className="w-full accent-accent"
            />
          </div>
        </div>
      )}
    </div>
  );
}
