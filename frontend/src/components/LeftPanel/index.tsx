import { UrlInput } from './UrlInput';
import { OutputDirPicker } from './OutputDirPicker';
import { Settings } from './Settings';

export function LeftPanel() {
  return (
    <aside className="border-r border-border bg-surface p-6 space-y-6">
      <div className="text-xs uppercase tracking-[0.1em] text-text-mute font-semibold">ExtractAssets</div>
      <UrlInput />
      <OutputDirPicker />
      <Settings />
    </aside>
  );
}
