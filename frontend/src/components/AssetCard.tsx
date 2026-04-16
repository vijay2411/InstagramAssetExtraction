import type { ReactNode } from 'react';

interface Props {
  title: string;
  subtitle?: string;
  color: 'speech' | 'music' | 'sfx';
  children: ReactNode;
  pills?: Array<{ label: string; href?: string }>;
}

const dotClass = { speech: 'bg-speech', music: 'bg-music', sfx: 'bg-sfx' };

export function AssetCard({ title, subtitle, color, children, pills }: Props) {
  return (
    <div className="bg-surface-2 border border-border-soft rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">{title}</div>
          {subtitle && <div className="text-[11px] text-text-mute mt-0.5">{subtitle}</div>}
        </div>
        <div className={`w-2 h-2 rounded-full ${dotClass[color]}`} />
      </div>
      {children}
      {pills && pills.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {pills.map((p, i) => p.href ? (
            <a key={i} href={p.href} download className="bg-surface-3 border border-border rounded px-2 py-1 text-[11px] text-text-dim hover:text-text">{p.label}</a>
          ) : (
            <span key={i} className="bg-surface-3 border border-border rounded px-2 py-1 text-[11px] text-text-dim">{p.label}</span>
          ))}
        </div>
      )}
    </div>
  );
}
