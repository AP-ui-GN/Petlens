import { useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import type { Analysis } from '@/lib/storage';
import { boundedVideoTime, motionPoints, nearestMotionPoint, replayTimingMatches } from '@/lib/evidence-replay';
import VideoFrameScrubber from './VideoFrameScrubber';

export default function EvidenceReplay({ analysis, sourceFile }: { analysis: Analysis; sourceFile?: File }) {
  const trace = analysis.measurements?.motionTrace;
  const points = useMemo(() => motionPoints(trace?.points), [trace]);
  const [videoUrl, setVideoUrl] = useState('');
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekRequest, setSeekRequest] = useState<{ timeSeconds: number; sequence: number }>();
  const [playbackError, setPlaybackError] = useState(false);

  useEffect(() => {
    setDuration(0);
    setCurrentTime(0);
    setSeekRequest(undefined);
    setPlaybackError(false);
    if (!sourceFile) { setVideoUrl(''); return; }
    const url = URL.createObjectURL(sourceFile);
    setVideoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [sourceFile]);

  const timed = replayTimingMatches(trace?.timingSource, points, duration);
  const enabled = Boolean(videoUrl) && timed && !playbackError;
  const measuredDuration = analysis.measurements?.durationSeconds;
  // Older summaries estimate length from nominal FPS. Never crop observed
  // source times to that estimate, especially for variable-rate clips.
  const axisDuration = duration || Math.max(
    typeof measuredDuration === 'number' && Number.isFinite(measuredDuration) ? measuredDuration : 0,
    points.at(-1)?.timeSeconds ?? 0, 1,
  );
  const nearest = nearestMotionPoint(points, currentTime);
  const selectTime = (time: number) => {
    if (!enabled) return;
    const selected = nearestMotionPoint(points, boundedVideoTime(time, duration));
    if (selected) setSeekRequest((previous) => ({
      timeSeconds: boundedVideoTime(selected.timeSeconds, duration), sequence: (previous?.sequence ?? 0) + 1,
    }));
  };

  return (
    <VideoFrameScrubber
      videoUrl={videoUrl}
      title="Evidence Replay"
      onTimeChange={setCurrentTime}
      onDurationChange={setDuration}
      onPlaybackError={setPlaybackError}
      seekRequest={seekRequest}
    >
      <div data-testid="evidence-replay">
        <h3 className="text-sm font-bold">Motion activity</h3>
        <p className="body-muted mt-2 text-xs leading-relaxed">
          Whole-picture grayscale change, not limb motion, contact timing, or gait health.
          Select a measured point to pause and replay that moment.
        </p>
        {points.length > 0 ? (
          <>
            <div className="mt-4 h-52 w-full" data-testid="motion-activity-graph" aria-label="Motion activity over recorded trace time">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: 12, right: 16, bottom: 12, left: 0 }}
                  onClick={(state) => {
                    const time = Number(state?.activeLabel);
                    if (state?.activeLabel !== undefined && Number.isFinite(time)) selectTime(time);
                  }}>
                  <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                  <XAxis dataKey="timeSeconds" type="number" domain={[0, axisDuration]} stroke="#94a3b8"
                    tickFormatter={(value: number) => `${value.toFixed(1)}s`} />
                  <YAxis width={48} stroke="#94a3b8" tick={{ fontSize: 11 }} tickFormatter={(value: number) => value.toPrecision(2)} />
                  <Line type="linear" dataKey="movement" stroke="#3eb49c" strokeWidth={2}
                    dot={points.length === 1} activeDot={false} isAnimationActive={false} />
                  {enabled && <ReferenceLine x={boundedVideoTime(currentTime, duration)} stroke="#fff" />}
                  {enabled && nearest && <ReferenceDot x={nearest.timeSeconds} y={nearest.movement} r={4} fill="#3eb49c" stroke="#fff" />}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <label className="body-muted mt-2 block text-xs" htmlFor={`replay-time-${analysis.id}`}>
              Select a source-video time (seconds)
            </label>
            <input id={`replay-time-${analysis.id}`} aria-label="Motion activity time" type="range"
              data-testid="motion-activity-time" min={0} max={axisDuration} step="any"
              value={boundedVideoTime(currentTime, axisDuration)} disabled={!enabled}
              onChange={(event) => selectTime(Number(event.target.value))}
              className="mt-2 w-full accent-[#3eb49c]" />
            <p className="mt-2 font-mono text-xs" data-testid="replay-selected-time">
              Video {currentTime.toFixed(3)} s
              {enabled && nearest ? ` · nearest sample ${nearest.timeSeconds.toFixed(4)} s · motion ${nearest.movement.toFixed(6)}` : ''}
            </p>
            <p className="body-muted mt-2 text-xs">
              {analysis.measurements?.frameCount} decoded frames · {trace?.sampleCount} frame comparisons · {points.length} plotted points.
              Each point represents the middle of its compared interval; sparse traces select the nearest measured point.
              The y-axis uses this clip’s scale.
            </p>
          </>
        ) : <p className="body-muted mt-3 text-sm">No timed motion samples are available. Video playback is still independent of the graph.</p>}
        {points.length > 0 && trace?.timingSource !== 'decoder' && <p className="body-muted mt-3 text-sm" role="status">
          Source timing is unverified for this trace. Graph seeking is disabled; analyze the original video again to establish its source times.
        </p>}
        {!sourceFile && <p className="body-muted mt-3 text-sm" role="status">
          Replay uses the most recently analyzed video in this browser session. Analyze a video to use Evidence Replay; source videos are not saved in browser history and are released on reload.
        </p>}
        {sourceFile && !playbackError && !enabled && <p className="body-muted mt-3 text-sm" role="status">
          {duration === 0 ? 'Waiting for playable video metadata.' : !timed
            ? 'Verified source timing is unavailable or does not match this video. Graph seeking is disabled; analyze the original clip again.' : ''}
        </p>}
      </div>
    </VideoFrameScrubber>
  );
}
