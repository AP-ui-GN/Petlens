import { useEffect, useMemo, useRef, useState } from 'react';
import { Pause, Play, SkipBack, SkipForward } from 'lucide-react';
import type { Analysis } from '@/lib/storage';

type PosePoint = NonNullable<NonNullable<Analysis['measurements']>['poseKeypoints']>[number];
type ToggleKey = 'hind' | 'fore' | 'angles';

const FRAME_RATE_ESTIMATE = 30;
const SKELETON = [
  { from: 'left_shoulder', to: 'right_shoulder', group: 'trunk' },
  { from: 'left_shoulder', to: 'left_hip', group: 'trunk' },
  { from: 'right_shoulder', to: 'right_hip', group: 'trunk' },
  { from: 'left_hip', to: 'right_hip', group: 'trunk' },
  { from: 'left_hip', to: 'left_knee', group: 'hind' },
  { from: 'left_knee', to: 'left_ankle', group: 'hind' },
  { from: 'right_hip', to: 'right_knee', group: 'hind' },
  { from: 'right_knee', to: 'right_ankle', group: 'hind' },
  { from: 'left_shoulder', to: 'left_elbow', group: 'fore' },
  { from: 'left_elbow', to: 'left_wrist', group: 'fore' },
  { from: 'right_shoulder', to: 'right_elbow', group: 'fore' },
  { from: 'right_elbow', to: 'right_wrist', group: 'fore' },
] as const;

function validPoints(analysis?: Analysis | null): PosePoint[] {
  const candidate = analysis?.measurements?.poseKeypoints;
  if (!Array.isArray(candidate)) return [];
  return candidate.filter((point): point is PosePoint =>
    typeof point?.name === 'string' &&
    Number.isFinite(point.x) && point.x >= 0 && point.x <= 1 &&
    Number.isFinite(point.y) && point.y >= 0 && point.y <= 1 &&
    Number.isFinite(point.confidence) && point.confidence >= 0 && point.confidence <= 1,
  );
}

function jointAngle(a?: PosePoint, vertex?: PosePoint, c?: PosePoint): number | null {
  if (!a || !vertex || !c) return null;
  const ax = a.x - vertex.x;
  const ay = a.y - vertex.y;
  const cx = c.x - vertex.x;
  const cy = c.y - vertex.y;
  const denominator = Math.hypot(ax, ay) * Math.hypot(cx, cy);
  if (denominator === 0) return null;
  const cosine = Math.max(-1, Math.min(1, (ax * cx + ay * cy) / denominator));
  return Math.round(Math.acos(cosine) * 180 / Math.PI);
}

function timestamp(seconds: number) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = (safeSeconds % 60).toFixed(2).padStart(5, '0');
  return `${String(minutes).padStart(2, '0')}:${remainder}`;
}

function RangeToggle({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-200">
      <input
        checked={checked}
        className="h-4 w-4 accent-[#3eb49c] focus:ring-2 focus:ring-[#5e17eb]"
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      {label}
    </label>
  );
}

export default function PoseFrameScrubber({
  analysis,
  videoUrl,
}: {
  analysis?: Analysis | null;
  videoUrl?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [duration, setDuration] = useState(analysis?.durationSeconds ?? 0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [toggle, setToggle] = useState<Record<ToggleKey, boolean>>({
    hind: true,
    fore: true,
    angles: true,
  });

  const points = useMemo(() => validPoints(analysis), [analysis]);
  const pointsByName = useMemo(() => new Map(points.map((point) => [point.name, point])), [points]);
  const frameCount = Math.max(0, Math.round(duration * FRAME_RATE_ESTIMATE));
  const frameIndex = Math.min(frameCount, Math.round(currentTime * FRAME_RATE_ESTIMATE));
  const hipAngles = [
    jointAngle(pointsByName.get('left_shoulder'), pointsByName.get('left_hip'), pointsByName.get('left_knee')),
    jointAngle(pointsByName.get('right_shoulder'), pointsByName.get('right_hip'), pointsByName.get('right_knee')),
  ];
  const kneeAngles = [
    jointAngle(pointsByName.get('left_hip'), pointsByName.get('left_knee'), pointsByName.get('left_ankle')),
    jointAngle(pointsByName.get('right_hip'), pointsByName.get('right_knee'), pointsByName.get('right_ankle')),
  ];

  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
    setDuration(analysis?.durationSeconds ?? 0);
  }, [analysis?.id, analysis?.durationSeconds, videoUrl]);

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
      aria-labelledby="pose-frame-scrubber-title"
      className="mt-5 rounded-2xl border border-[#1669aa]/50 border-t-[#3794a4]/40 bg-gradient-to-b from-[#0a4267]/60 to-[#061826]/95 p-6 text-white shadow-2xl backdrop-blur-md"
      data-testid="pose-frame-scrubber"
    >
      <div>
        <div className="eyebrow">Pose inspection</div>
        <h2 className="mt-2 font-sans text-xl font-bold leading-snug" id="pose-frame-scrubber-title">MoveNet frame scrubber</h2>
        <p className="body-muted mt-2 text-sm leading-relaxed">
          {points.length > 0
            ? 'The overlay shows confidence-filtered mean landmarks across usable frames. Frame-specific landmarks and clinical joint angles are not included in the saved telemetry.'
            : 'Scrub the selected video. MoveNet landmarks appear here only when the analysis has saved pose data.'}
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
                data-testid="pose-scrubber-video"
                preload="metadata"
                ref={videoRef}
                src={videoUrl}
              />
              {points.length > 0 && (
                <svg
                  aria-label="Confidence-filtered mean pose landmark overlay"
                  className="pointer-events-none absolute inset-0 h-full w-full"
                  preserveAspectRatio="none"
                  role="img"
                  viewBox="0 0 1 1"
                >
                  {SKELETON.map(({ from, to, group }) => {
                    const groupVisible = group === 'trunk' || (group === 'hind' ? toggle.hind : toggle.fore);
                    const start = pointsByName.get(from);
                    const end = pointsByName.get(to);
                    if (!groupVisible || !start || !end) return null;
                    const color = group === 'trunk' ? '#3794a4' : group === 'hind' ? '#3eb49c' : '#1669aa';
                    return <line key={`${from}-${to}`} x1={start.x} y1={start.y} x2={end.x} y2={end.y} stroke={color} strokeWidth=".008" vectorEffect="non-scaling-stroke" />;
                  })}
                  {points.map((point) => (
                    <circle cx={point.x} cy={point.y} fill="#fff" key={point.name} r=".012">
                      <title>{`${point.name.replaceAll('_', ' ')} mean landmark, ${Math.round(point.confidence * 100)}% confidence`}</title>
                    </circle>
                  ))}
                </svg>
              )}
            </div>
          ) : (
            <div className="grid aspect-video place-items-center rounded-xl border border-slate-700 bg-slate-950/70 p-6 text-center">
              <div>
                <Play aria-hidden="true" className="mx-auto text-[#3794a4]" size={30} />
                <p className="mt-3 text-sm font-semibold text-white">Video not retained with this observation</p>
                <p className="body-muted mt-1 max-w-md text-xs leading-relaxed">
                  The source clip was deleted after analysis. Saved history contains summary landmarks, not video frames, so playback and frame overlays are unavailable here.
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
          <h3 className="text-sm font-bold text-white">Landmark &amp; angle reference</h3>
          <div className="mt-4 space-y-3">
            <RangeToggle checked={toggle.hind} label="Hind Limbs" onChange={(checked) => setToggle((value) => ({ ...value, hind: checked }))} />
            <RangeToggle checked={toggle.fore} label="Forelimbs" onChange={(checked) => setToggle((value) => ({ ...value, fore: checked }))} />
            <RangeToggle checked={toggle.angles} label="Joint Angle Arc Labels" onChange={(checked) => setToggle((value) => ({ ...value, angles: checked }))} />
          </div>
          {toggle.angles && (
            <div className="mt-5 space-y-2 border-t border-slate-700 pt-4">
              {[
                ['Hip extension · left', hipAngles[0]],
                ['Hip extension · right', hipAngles[1]],
                ['Stifle flexion · left', kneeAngles[0]],
                ['Stifle flexion · right', kneeAngles[1]],
                ['Hock angle', null],
              ].map(([label, value]) => (
                <div className="flex items-center justify-between gap-2" key={label as string}>
                  <span className="text-xs text-slate-300">{label as string}</span>
                  {typeof value === 'number' ? (
                    <span className="font-mono text-sm font-bold text-emerald-400">{value}°</span>
                  ) : (
                    <span className="font-mono text-xs text-slate-400">Not measured</span>
                  )}
                </div>
              ))}
              {(hipAngles.some((value) => value !== null) || kneeAngles.some((value) => value !== null)) && (
                <span className="inline-flex rounded border border-[#5e17eb] bg-[#5e17eb]/10 px-2 py-0.5 font-mono text-[10px] text-violet-200">
                  2D mean-landmark estimates · not clinical angles
                </span>
              )}
            </div>
          )}
          <p className="body-muted mt-4 text-[11px] leading-relaxed">
            Angles are simple 2D estimates from mean landmark positions. They are not frame-specific or clinically validated; hock landmarks are not saved.
          </p>
        </aside>
      </div>
    </section>
  );
}
