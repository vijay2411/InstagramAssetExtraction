import { motion } from 'motion/react';
import { api, type Manifest } from '@/lib/api';
import { VideoPreview } from '@/components/VideoPreview';
import { AssetCard } from '@/components/AssetCard';
import { Waveform } from '@/components/Waveform';
import { SfxGrid } from '@/components/SfxGrid';
import { fmtDuration } from '@/lib/format';

interface Props { manifest: Manifest; jobDirName: string; }

export function ResultsState({ manifest, jobDirName }: Props) {
  const { video, speech, music } = manifest.assets;
  const videoUrl = api.assetUrl(jobDirName, video.path);
  const speechUrl = api.assetUrl(jobDirName, speech.path);
  const musicUrl = api.assetUrl(jobDirName, music.path);
  const song = music.song;
  const hasSfx = manifest.assets.sfx.length > 0;

  // Staggered entrance; each asset slides in with a spring.
  const item = {
    initial: { opacity: 0, y: 24 },
    animate: { opacity: 1, y: 0 },
    transition: { type: 'spring' as const, stiffness: 120, damping: 22 },
  };

  return (
    <div className="px-10 py-10 max-w-5xl">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-ember">complete</span>
          <div className="flex-1 h-px bg-ember/30" />
          <span className="font-mono text-[10px] tabular text-text-mute">
            {fmtDuration(manifest.duration_seconds)}
          </span>
        </div>
        <h2 className="font-display font-light text-display-sm tracking-display text-text">
          Your three layers —
          <span className="font-display-wonk italic text-ember ml-2">ready.</span>
        </h2>
      </motion.div>

      {/* Hero: video player — the visual anchor of the results */}
      <motion.div {...item} transition={{ ...item.transition, delay: 0.05 }}>
        <VideoPreview src={videoUrl} />
      </motion.div>

      {/* Stem cards */}
      <div className="grid gap-4 mt-6">
        <motion.div {...item} transition={{ ...item.transition, delay: 0.15 }}>
          <AssetCard
            color="speech"
            label="speech"
            title="Creator's voice"
            subtitle={fmtDuration(speech.duration)}
            downloadUrl={speechUrl}
            downloadName="speech.wav"
          >
            <Waveform url={speechUrl} color="#80b5ff" />
          </AssetCard>
        </motion.div>

        <motion.div {...item} transition={{ ...item.transition, delay: 0.25 }}>
          <AssetCard
            color="music"
            label="music"
            title={song ? song.title : 'Background music'}
            subtitle={
              song
                ? [song.artist, 'identified via yt-dlp metadata'].filter(Boolean).join(' · ')
                : `${fmtDuration(music.duration)} · demucs non-vocals`
            }
            downloadUrl={musicUrl}
            downloadName="music.wav"
          >
            <Waveform url={musicUrl} color="#e8b13a" />
          </AssetCard>
        </motion.div>

        {hasSfx && (
          <motion.div {...item} transition={{ ...item.transition, delay: 0.35 }}>
            <SfxGrid manifest={manifest} jobDirName={jobDirName} />
          </motion.div>
        )}
      </div>
    </div>
  );
}
