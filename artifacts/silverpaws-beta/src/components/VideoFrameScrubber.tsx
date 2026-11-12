import { type ReactNode, useEffect, useRef, useState } from 'react';
import { Pause, Play, SkipBack, SkipForward } from 'lucide-react';
import { boundedVideoTime } from '@/lib/evidence-replay';

function timestamp(seconds: number) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = (safeSeconds % 60).toFixed(2).padStart(5, '0');
  return `${String(minutes).padStart(2, '0')}:${remainder}`;
}

type Props = {
  videoUrl?: string;
  title?: string;
  children?: ReactNode;
  seekRequest?: { timeSeconds: number; sequence: number };
  onTimeChange?: (seconds: number) => void;
  onDurationChange?: (seconds: number) => void;
  onPlaybackError?: (failed: boolean) => void;
};

export default function VideoFrameScrubber({
  videoUrl, title = 'Video preview', children, seekRequest,
  onTimeChange, onDurationChange, onPlaybackError,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
    setDuration(0);
    setFailed(false);
  }, [videoUrl]);

  const updateTime = () => {
    const time = boundedVideoTime(videoRef.current?.currentTime ?? 0, duration);
    setCurrentTime(time);
    onTimeChange?.(time);
  };
  const updateDuration = () => {
    const value = videoRef.current?.duration ?? 0;
    const seconds = Number.isFinite(value) && value > 0 ? value : 0;
    setDuration(seconds);
    onDurationChange?.(seconds);
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!seekRequest || !video || duration <= 0 || failed) return;
    const time = boundedVideoTime(seekRequest.timeSeconds, duration);
    video.pause();
    video.currentTime = time;
    setCurrentTime(time);
    onTimeChange?.(time);
  }, [seekRequest, duration, videoUrl, failed, onTimeChange]);

  function seekToTime(time: number) {
    const video = videoRef.current;
    if (!video || duration <= 0 || failed) return;
    const nextTime = boundedVideoTime(time, duration);
    video.currentTime = nextTime;
    setCurrentTime(nextTime);
    onTimeChange?.(nextTime);
  }

  async function togglePlayback() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      try { await video.play(); }
      catch { setIsPlaying(false); }
    } else video.pause();
  }

  return (
    <section aria-labelledby="video-frame-scrubber-title"
      className="mt-5 rounded-2xl border border-[#1669aa]/50 border-t-[#3794a4]/40 bg-[#0a2b3e] p-6 text-white shadow-2xl backdrop-blur-md"
      data-testid="video-frame-scrubber">
      <div>
        <div className="eyebrow">Source video</div>
        <h2 className="mt-2 font-sans text-xl font-bold leading-snug" id="video-frame-scrubber-title">{title}</h2>
        <p className="body-muted mt-2 text-sm leading-relaxed">
          {children ? 'Review the uploaded clip alongside its measured motion activity.' : 'Review the source clip while analysis runs.'}
          {' '}This preview does not measure joint angles, stride symmetry, or gait.
        </p>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,1fr)]">
        <div className="min-w-0">
          {videoUrl ? (
            <div className="relative mx-auto aspect-video w-full max-w-3xl overflow-hidden rounded-xl bg-slate-950">
              <video className="absolute inset-0 h-full w-full object-contain" controls playsInline
                data-testid="video-scrubber-video" preload="metadata" ref={videoRef} src={videoUrl}
                onLoadedMetadata={updateDuration} onDurationChange={updateDuration}
                onTimeUpdate={updateTime} onSeeked={updateTime}
                onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)}
                onEnded={() => { setIsPlaying(false); updateTime(); }}
                onError={() => { setFailed(true); setIsPlaying(false); onPlaybackError?.(true); }} />
            </div>
          ) : (
            <div className="grid aspect-video place-items-center rounded-xl border border-slate-700 bg-slate-950/70 p-6 text-center">
              <p className="text-sm font-semibold">Source video unavailable in this session</p>
            </div>
          )}
          {failed && <p role="alert" className="mt-3 text-sm text-amber-200">
            This browser could not play the video. Use a browser-supported MP4 or WebM and analyze that file; graph seeking is unavailable.
          </p>}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button aria-label="Step backward 0.1 seconds" className="btn-quiet" type="button"
              disabled={!videoUrl || duration <= 0 || failed} onClick={() => seekToTime(currentTime - 0.1)}>
              <SkipBack size={17} />
            </button>
            <button aria-label={isPlaying ? 'Pause video' : 'Play video'} className="btn-quiet" type="button"
              disabled={!videoUrl || duration <= 0 || failed} onClick={togglePlayback}>
              {isPlaying ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button aria-label="Step forward 0.1 seconds" className="btn-quiet" type="button"
              disabled={!videoUrl || duration <= 0 || failed} onClick={() => seekToTime(currentTime + 0.1)}>
              <SkipForward size={17} />
            </button>
            <input aria-label="Video time in seconds" className="min-w-[8rem] flex-1 accent-[#3eb49c]"
              disabled={!videoUrl || duration <= 0 || failed} max={duration || 1} min={0} step="0.01"
              onChange={(event) => seekToTime(Number(event.target.value))} type="range"
              value={boundedVideoTime(currentTime, duration)} />
          </div>
          <div className="mt-2 flex justify-between gap-3 font-mono text-[11px] text-slate-300">
            <span>{timestamp(currentTime)}</span><span>{duration > 0 ? timestamp(duration) : 'Duration unavailable'}</span>
          </div>
        </div>
        <aside className="min-w-0 rounded-xl border border-slate-700/80 bg-slate-950/35 p-4">
          {children ?? <><h3 className="text-sm font-bold">What this preview shows</h3>
            <p className="body-muted mt-3 text-sm leading-relaxed">This is the uploaded video only. Canine pose landmarks and gait measurements are not available in this preview.</p></>}
        </aside>
      </div>
    </section>
  );
}
