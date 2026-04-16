import { LeftPanel } from '@/components/LeftPanel';
import { RightPanel } from '@/components/RightPanel';

export default function App() {
  return (
    <div className="min-h-screen grid grid-cols-[320px_1fr]">
      <LeftPanel />
      <RightPanel />
    </div>
  );
}
