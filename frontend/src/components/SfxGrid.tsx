import type { Manifest } from '@/lib/api';
import { api } from '@/lib/api';
import { SfxTile } from './SfxTile';

interface Props { manifest: Manifest; jobDirName: string; }

export function SfxGrid({ manifest, jobDirName }: Props) {
  const sfx = manifest.assets.sfx;
  return (
    <div className="bg-surface-2 border border-border-soft rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium">Sound effects</div>
          <div className="text-[11px] text-text-mute mt-0.5">{sfx.length} deduped · extracted by repetition mining</div>
        </div>
        <div className="w-2 h-2 rounded-full bg-sfx" />
      </div>
      {sfx.length === 0 ? (
        <div className="text-xs text-text-mute">No repeated SFX detected.</div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {sfx.map((s, i) => (
            <SfxTile
              key={s.path}
              url={api.assetUrl(jobDirName, s.path)}
              repeats={s.repeats}
              duration={s.duration}
              index={i + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
