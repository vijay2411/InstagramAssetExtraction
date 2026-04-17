import { Aurora } from '@/components/Aurora';
import { LeftPanel } from '@/components/LeftPanel';
import { RightPanel } from '@/components/RightPanel';

export default function App() {
  return (
    <>
      <Aurora />
      <div className="relative z-10 min-h-screen grid grid-cols-[360px_1fr]">
        <LeftPanel />
        <RightPanel />
      </div>
    </>
  );
}
