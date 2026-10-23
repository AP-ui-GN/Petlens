import { useEffect, useRef, useState } from 'react';
import { Pause, Play, SkipBack, SkipForward } from 'lucide-react';

const FRAME_RATE_ESTIMATE = 30;

function timestamp(seconds: number) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = (safeSeconds % 60).toFixed(2).padStart(5, '0');
  return `${String(minutes).padStart(2, '0')}:${remainder}`;
}

export default function VideoFrameScrubber({
  videoUrl,
}: {
  videoUrl?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const frameCount = Math.max(0, Math.round(duration * FRAME_RATE_ESTIMATE));
  const frameIndex = Math.min(frameCount, Math.round(currentTime * FRAME_RATE_ESTIMATE));

  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
    setDuration(0);
  }, [videoUrl]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const updateTime = () => setCurrentTime(video.currentTime);
    const updateDuration = () => setDuration(Number.isFinite(video.duration) ? video.duration : 0);
    const pause = () => setIsPlaying(false);
    video.addEventListener('timeupdate', updateTime);
    video.addEventListener('loadedmetadata', updateDuration);
    video.addEventListener('durationchange', updateDuration);
    video.addEventListener('pause', pause);
    video.addEventListener('ended', pause);
    return () => {
      video.removeEventListener('timeupdate', updateTime);
      video.removeEventListener('loadedmetadata', updateDuration);
      video.removeEventListener('durationchange', updateDuration);
      video.removeEventListener('pause', pause);
      video.removeEventListener('ended', pause);
    };
  }, [videoUrl]);

  function seekToFrame(frame: number) {
    const video = videoRef.current;
    if (!video || frameCount === 0) return;
    const nextTime = Math.min(duration, Math.max(0, frame / FRAME_RATE_ESTIMATE));
    video.currentTime = nextTime;
    setCurrentTime(nextTime);
  }

  async function togglePlayback() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      try {
        await video.play();
        setIsPlaying(true);
      } catch (error) {
        setIsPlaying(false);
        console.error('Unable to play the selected video.', error);
      }
    } else {
      video.pause();
      setIsPlaying(false);
    }
  }

  return (
    <section
      aria-labelledby="video-frame-scrubber-title"
      className="mt-5 rounded-2xl border border-[#1669aa]/50 border-t-[#3794a4]/40 bg-gradient-to-b from-[#0a4267]/60 to-[#061826]/95 p-6 text-white shadow-2xl backdrop-blur-md"
      data-testid="video-frame-scrubber"
    >
      <div>
        <div className="eyebrow">Video preview</div>
        <h2 className="mt-2 font-sans text-xl font-bold leading-snug" id="video-frame-scrubber-title">Frame scrubber</h2>
        <p className="body-muted mt-2 text-sm leading-relaxed">
          Review the source clip while analysis runs. This preview does not show pose landmarks or measure joint angles, stride symmetry, or gait.
        </p>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(15rem,0.75fr)]">
        <div className="min-w-0">
          {videoUrl ? (
            <div
              className="relative mx-auto w-full max-w-3xl overflow-hidden rounded-xl bg-slate-950"
              style={duration > 0 ? { aspectRatio: `${videoRef.current?.videoWidth || 16} / ${videoRef.current?.videoHeight || 9}` } : { aspectRatio: '16 / 9' }}
            >
              <video
                className="absolute inset-0 h-full w-full object-fill"
                controls
                data-testid="video-scrubber-video"
                preload="metadata"
                ref={videoRef}
                src={videoUrl}
              />
            </div>
          ) : (
            <div className="grid aspect-video place-items-center rounded-xl border border-slate-700 bg-slate-950/70 p-6 text-center">
              <div>
                <Play aria-hidden="true" className="mx-auto text-[#3794a4]" size={30} />
                <p className="mt-3 text-sm font-semibold text-white">Video preview unavailable</p>
                <p className="body-muted mt-1 max-w-md text-xs leading-relaxed">
                  The selected video is not available for playback.
                </p>
              </div>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              aria-label="Step backward one frame"
              className="rounded-lg border border-[#1669aa]/40 bg-[#1669aa]/30 p-2 text-white hover:bg-[#1669aa]/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#5e17eb] disabled:opacity-40"
              disabled={!videoUrl || frameCount === 0}
              onClick={() => seekToFrame(frameIndex - 1)}
              type="button"
            >
              <SkipBack size={17} />
            </button>
            <button
              aria-label={isPlaying ? 'Pause video' : 'Play video'}
              className="rounded-lg border border-[#1669aa]/40 bg-[#1669aa]/30 p-2 text-white hover:bg-[#1669aa]/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#5e17eb] disabled:opacity-40"
              disabled={!videoUrl}
              onClick={togglePlayback}
              type="button"
            >
              {isPlaying ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button
              aria-label="Step forward one frame"
              className="rounded-lg border border-[#1669aa]/40 bg-[#1669aa]/30 p-2 text-white hover:bg-[#1669aa]/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#5e17eb] disabled:opacity-40"
              disabled={!videoUrl || frameCount === 0}
              onClick={() => seekToFrame(frameIndex + 1)}
              type="button"
            >
              <SkipForward size={17} />
            </button>
            <input
              aria-label="Video frame timeline"
              className="min-w-[8rem] flex-1 accent-[#3eb49c]"
              disabled={!videoUrl || frameCount === 0}
              max={frameCount}
              min={0}
              onChange={(event) => seekToFrame(Number(event.target.value))}
              type="range"
              value={Math.min(frameCount, frameIndex)}
            />
          </div>
          <div className="mt-2 flex justify-between gap-3 font-mono text-[11px] text-slate-300" aria-live="polite">
            <span>FRAME {String(frameIndex).padStart(3, '0')} / {videoUrl ? frameCount : '—'}</span>
            <span>{timestamp(currentTime)}{videoUrl ? ' · approx. 30 fps' : ''}</span>
          </div>
          {videoUrl && (
            <p className="body-muted mt-2 text-[11px]">
              Frame numbering is approximate at 30 fps because the source frame rate is not stored.
            </p>
          )}
        </div>

        <aside className="rounded-xl border border-slate-700/80 bg-slate-950/35 p-4">
          <h3 className="text-sm font-bold text-white">What this preview shows</h3>
          <p className="body-muted mt-3 text-sm leading-relaxed">
            This is the uploaded video only. Canine pose landmarks and gait measurements are not available in this preview.
          </p>
        </aside>
      </div>
    </section>
  );
}
