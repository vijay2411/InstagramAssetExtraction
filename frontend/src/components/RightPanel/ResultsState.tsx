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

  return (
    <div className="space-y-3">
      <VideoPreview src={videoUrl} />

      <AssetCard
        title="Speech"
        subtitle={fmtDuration(speech.duration)}
        color="speech"
        pills={[{ label: 'speech.wav', href: speechUrl }]}
      >
        <Waveform url={speechUrl} color="#60a5fa" />
      </AssetCard>

      <AssetCard
        title={song ? `Music — "${song.title}"` : 'Music'}
        subtitle={song ? [song.artist, 'via yt-dlp metadata'].filter(Boolean).join(' · ') : fmtDuration(music.duration)}
        color="music"
        pills={[{ label: 'music.wav', href: musicUrl }]}
      >
        <Waveform url={musicUrl} color="#fbbf24" />
      </AssetCard>

      <SfxGrid manifest={manifest} jobDirName={jobDirName} />
    </div>
  );
}
