interface Props { src: string; }
export function VideoPreview({ src }: Props) {
  return (
    <div className="bg-black rounded-xl overflow-hidden border border-border-soft">
      <video src={src} controls className="w-full max-h-[360px] object-contain" />
    </div>
  );
}
