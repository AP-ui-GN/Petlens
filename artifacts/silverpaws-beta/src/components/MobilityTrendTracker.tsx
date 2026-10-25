import { useMemo, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, FileVideo } from 'lucide-react';
import { formatDate } from '@/lib/format';
import { trendSeries } from '@/lib/trends';
import type { Analysis } from '@/lib/storage';

type TimeRange = '30' | '60' | '90' | 'all';
type MetricKey = 'overall' | 'symmetry' | 'hip';
type TrackerPoint = {
  id: string;
  createdAt: string;
  fileName: string;
  demo: boolean;
  overall: number | null;
  symmetry: number | null;
  hip: number | null;
};

type MetricDefinition = {
  key: MetricKey;
  label: string;
  color: string;
};

const METRICS: MetricDefinition[] = [
  { key: 'overall', label: 'Overall mobility', color: '#3eb49c' },
  { key: 'hip', label: 'Hip stability', color: '#1669aa' },
];

function previewPoints(): TrackerPoint[] {
  const now = Date.now();
  return [
    { id: 'preview-1', daysAgo: 28, fileName: 'Sample walk · Week 1', overall: 68, symmetry: 64, hip: 61 },
    { id: 'preview-2', daysAgo: 19, fileName: 'Sample walk · Week 2', overall: 71, symmetry: 69, hip: 66 },
    { id: 'preview-3', daysAgo: 9, fileName: 'Sample walk · Week 3', overall: 75, symmetry: 72, hip: 70 },
    { id: 'preview-4', daysAgo: 1, fileName: 'Sample walk · Week 4', overall: 78, symmetry: 76, hip: 74 },
  ].map((item) => ({
    ...item,
    id: item.id,
    createdAt: new Date(now - item.daysAgo * 24 * 60 * 60 * 1000).toISOString(),
    demo: true,
  }));
}

const CHART = { width: 760, height: 250, left: 42, right: 18, top: 18, bottom: 34 };

function normalizedHipScore(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, value >= 0 && value <= 1 ? value * 100 : value));
}

function score(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.max(0, Math.min(100, value))
    : null;
}

function toPoint(analysis: Analysis): TrackerPoint {
  return {
    id: analysis.id,
    createdAt: analysis.createdAt,
    fileName: analysis.fileName,
    demo: analysis.demo === true,
    overall: score(analysis.overallScore),
    symmetry: score(analysis.factors?.symmetry ?? analysis.strideSymmetryScore),
    hip: normalizedHipScore(analysis.measurements?.hipStability),
  };
}

function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(date)
    : 'Unknown date';
}

function linePath(points: TrackerPoint[], key: MetricKey): string {
  const plotWidth = CHART.width - CHART.left - CHART.right;
  const plotHeight = CHART.height - CHART.top - CHART.bottom;
  const firstTime = new Date(points[0]?.createdAt ?? 0).getTime();
  const lastTime = new Date(points[points.length - 1]?.createdAt ?? 0).getTime();
  const xFor = (point: TrackerPoint, index: number) =>
    lastTime <= firstTime
      ? CHART.left + plotWidth / 2
      : CHART.left + ((new Date(point.createdAt).getTime() - firstTime) / (lastTime - firstTime)) * plotWidth;
  const yFor = (value: number) => CHART.top + ((100 - value) / 100) * plotHeight;
  let path = '';
  let inSegment = false;
  points.forEach((point, index) => {
    const value = point[key];
    if (value === null) {
      inSegment = false;
      return;
    }
    path += `${inSegment ? 'L' : 'M'} ${xFor(point, index).toFixed(1)} ${yFor(value).toFixed(1)} `;
    inSegment = true;
  });
  return path.trim();
}

function pointPosition(points: TrackerPoint[], index: number, value: number) {
  const plotWidth = CHART.width - CHART.left - CHART.right;
  const plotHeight = CHART.height - CHART.top - CHART.bottom;
  const firstTime = new Date(points[0]?.createdAt ?? 0).getTime();
  const lastTime = new Date(points[points.length - 1]?.createdAt ?? 0).getTime();
  const timestamp = new Date(points[index]?.createdAt ?? 0).getTime();
  return {
    x: lastTime <= firstTime
      ? CHART.left + plotWidth / 2
      : CHART.left + ((timestamp - firstTime) / (lastTime - firstTime)) * plotWidth,
    y: CHART.top + ((100 - value) / 100) * plotHeight,
  };
}

function withinRange(points: TrackerPoint[], range: TimeRange): TrackerPoint[] {
  if (range === 'all') return points;
  const cutoff = Date.now() - Number(range) * 24 * 60 * 60 * 1000;
  return points.filter((point) => new Date(point.createdAt).getTime() >= cutoff);
}

export default function MobilityTrendTracker({ analyses, petId, petName }: { analyses: Analysis[]; petId: string; petName?: string }) {
  const [range, setRange] = useState<TimeRange>('90');
  const [enabled, setEnabled] = useState<Record<MetricKey, boolean>>({
    overall: true,
    symmetry: false,
    hip: true,
  });
  const [hovered, setHovered] = useState<{ point: TrackerPoint; x: number; y: number } | null>(null);

  const { savedPoints, pipelineCount } = useMemo(() => {
    const petAnalyses = analyses.filter((analysis) => analysis.petId === petId && !analysis.demo);
    const series = trendSeries(petAnalyses);
    const latestPipelineSeries = series[0];
    if (!latestPipelineSeries) return { savedPoints: [], pipelineCount: 0 };
    const byId = new Map(petAnalyses.map((analysis) => [analysis.id, analysis]));
    const points = latestPipelineSeries.points
      .map((point) => {
        const analysis = byId.get(point.id);
        return analysis ? toPoint(analysis) : null;
      })
      .filter((point): point is TrackerPoint => point !== null);
    return { savedPoints: points, pipelineCount: series.length };
  }, [analyses, petId]);

  const isPreview = savedPoints.length === 0;
  const demoPoints = useMemo(previewPoints, []);
  const visiblePoints = useMemo(
    () => withinRange(isPreview ? demoPoints : savedPoints, range),
    [demoPoints, isPreview, range, savedPoints],
  );
  const displayedPoints = visiblePoints;
  const hasRangeFallback = visiblePoints.length === 0 && !isPreview;
  const selectedPoint = hovered?.point ?? displayedPoints[displayedPoints.length - 1];

  const delta = useMemo(() => {
    const scored = displayedPoints.map((point) => point.overall).filter((value): value is number => value !== null);
    if (scored.length < 2) return null;
    const first = scored[Math.max(0, scored.length - 4)];
    const last = scored[scored.length - 1];
    return first === undefined || last === undefined ? null : last - first;
  }, [displayedPoints]);

  const visibleMetrics = METRICS.filter(({ key }) => enabled[key]);
  const lineColors = Object.fromEntries(METRICS.map((metric) => [metric.key, metric.color])) as Record<MetricKey, string>;

  function toggleMetric(key: MetricKey) {
    setEnabled((current) => {
      if (current[key] && Object.values(current).filter(Boolean).length === 1) return current;
      return { ...current, [key]: !current[key] };
    });
  }

  return (
    <section
      className="mt-5 rounded-2xl border border-[#1669aa]/50 border-t-[#3794a4]/40 bg-[#0a2b3e] p-6 text-white shadow-2xl backdrop-blur-md"
      data-testid="mobility-trend-tracker"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Longitudinal mobility</div>
          <h2 className="mt-2 font-sans text-xl font-bold leading-snug tracking-normal">Gait baseline &amp; trend</h2>
          <p className="body-muted mt-2 max-w-2xl text-sm leading-relaxed">
            {isPreview
              ? `Sample trajectory shown below. Once you upload and analyze a video of ${petName ?? 'your pet'}, your real gait measurements will automatically plot here.`
              : 'Longitudinal movement trends tracked across recorded walk observations.'}
          </p>
        </div>
        <div className="flex rounded-xl border border-slate-700 bg-slate-950/50 p-1" aria-label="Trend time range" role="group">
          {(['30', '60', '90', 'all'] as const).map((item) => (
            <button
              aria-pressed={range === item}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${range === item ? 'border-[#5e17eb] bg-[#1669aa]/20 text-white' : 'border-transparent text-slate-300 hover:bg-white/5'}`}
              key={item}
              onClick={() => setRange(item)}
              type="button"
            >
              {item === 'all' ? 'All' : `${item}D`}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Chart metrics">
        {METRICS.map(({ key, label, color }) => (
          <button
            aria-pressed={enabled[key]}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-opacity ${enabled[key] ? 'border-white/20 bg-slate-950/45 text-white' : 'border-slate-700 text-slate-400 opacity-70'}`}
            key={key}
            onClick={() => toggleMetric(key)}
            type="button"
          >
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            {label}
          </button>
        ))}
      </div>

      <div className="relative mt-4">
        {hasRangeFallback ? (
          <div className="grid min-h-[250px] place-items-center rounded-xl border border-slate-700/70 bg-slate-950/30 px-6 text-center">
            <p className="body-muted max-w-md text-sm leading-relaxed">
              No saved walks fall within the selected {range}-day window. Choose another range to view this pet’s history.
            </p>
          </div>
        ) : (
          <svg
            aria-label="Mobility scores across observation dates, with a dashed baseline at 80 out of 100"
            className="w-full"
            role="img"
            viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          >
            {[0, 20, 40, 60, 80, 100].map((value) => {
              const y = CHART.top + ((100 - value) / 100) * (CHART.height - CHART.top - CHART.bottom);
              return (
                <g key={value}>
                  <line
                    x1={CHART.left}
                    x2={CHART.width - CHART.right}
                    y1={y}
                    y2={y}
                    stroke={value === 80 ? '#5e17eb' : 'rgba(148,163,184,.17)'}
                    strokeDasharray={value === 80 ? '6 5' : undefined}
                  />
                  <text fill="#94a3b8" fontSize="10" textAnchor="end" x={CHART.left - 8} y={y + 3}>{value}</text>
                </g>
              );
            })}
            <text fill="#c4b5fd" fontSize="10" x={CHART.width - CHART.right - 48} y={CHART.top + ((100 - 80) / 100) * (CHART.height - CHART.top - CHART.bottom) - 5}>Baseline 80</text>
            {visibleMetrics.map(({ key }) => (
              <path
                d={linePath(displayedPoints, key)}
                fill="none"
                key={key}
                stroke={lineColors[key]}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="3"
              />
            ))}
            {displayedPoints.map((point, index) => (
              <g key={point.id}>
                {visibleMetrics.map(({ key }) => {
                  const value = point[key];
                  if (value === null) return null;
                  const position = pointPosition(displayedPoints, index, value);
                  return (
                    <circle
                      cx={position.x}
                      cy={position.y}
                      fill={lineColors[key]}
                      key={key}
                      aria-label={`${METRICS.find((metric) => metric.key === key)?.label}: ${value}/100 on ${dateLabel(point.createdAt)}`}
                      onBlur={() => setHovered(null)}
                      onFocus={() => setHovered({ point, x: position.x / CHART.width * 100, y: position.y / CHART.height * 100 })}
                      onMouseEnter={() => setHovered({ point, x: position.x / CHART.width * 100, y: position.y / CHART.height * 100 })}
                      onMouseLeave={() => setHovered(null)}
                      r="5"
                      role="button"
                      tabIndex={0}
                    >
                      <title>{`${dateLabel(point.createdAt)} · ${METRICS.find((metric) => metric.key === key)?.label}: ${value}/100`}</title>
                    </circle>
                  );
                })}
              </g>
            ))}
            <text fill="#94a3b8" fontSize="10" textAnchor="start" x={CHART.left} y={CHART.height - 8}>{dateLabel(displayedPoints[0]?.createdAt ?? '')}</text>
            <text fill="#94a3b8" fontSize="10" textAnchor="end" x={CHART.width - CHART.right} y={CHART.height - 8}>{dateLabel(displayedPoints[displayedPoints.length - 1]?.createdAt ?? '')}</text>
          </svg>
        )}
        {hovered && !hasRangeFallback && (
          <div
            className="pointer-events-none absolute z-10 w-56 rounded-xl border border-[#1669aa]/50 bg-slate-950/95 p-3 shadow-xl"
            style={{
              left: `clamp(0px, calc(${hovered.x}% - 7rem), calc(100% - 14rem))`,
              top: `clamp(0px, calc(${hovered.y}% - 6rem), calc(100% - 7rem))`,
            }}
          >
            <div className="text-xs font-bold text-white">{dateLabel(hovered.point.createdAt)}</div>
            <div className="mt-2 flex items-center gap-2 rounded-lg bg-slate-800/80 p-2">
              <div className="grid h-9 w-12 shrink-0 place-items-center rounded bg-slate-700 text-slate-300">
                <FileVideo aria-hidden="true" size={17} />
              </div>
              <span className="truncate text-[10px] text-slate-300">{hovered.point.fileName}</span>
            </div>
            <div className="mt-2 space-y-1">
              {METRICS.map(({ key, label, color }) => (
                <div className="flex justify-between gap-2 text-[10px]" key={key}>
                  <span style={{ color }}>{label}</span>
                  <span className="font-mono text-white">{hovered.point[key] === null ? 'Not measured' : `${hovered.point[key]}/100`}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-slate-700/70 pt-4">
        <div className="flex items-center gap-2">
          {delta === null ? (
            <span className="rounded-full bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300">
              {isPreview ? 'Illustrative sample trajectory' : 'Not enough scored walks to compare'}
            </span>
          ) : (
            <>
              <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-bold ${delta >= 0 ? 'bg-emerald-400/15 text-emerald-300' : 'bg-rose-400/15 text-rose-300'}`}>
                {delta >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {delta > 0 ? '+' : ''}{Math.round(delta)} pts
              </span>
              <span className="body-muted text-xs">
                Overall change over the last {Math.min(3, Math.max(1, displayedPoints.length - 1))} walk{displayedPoints.length === 2 ? '' : 's'}
              </span>
            </>
          )}
        </div>
        {selectedPoint && (
          <span className="body-muted text-xs">
            {isPreview ? 'Sample preview' : 'Latest in view'}: <span className="font-mono text-white">{selectedPoint.overall === null ? 'Not scored' : `${selectedPoint.overall}/100`}</span>
          </span>
        )}
      </div>
      {savedPoints.length > 0 && pipelineCount > 1 && (
        <p className="body-muted mt-3 text-xs">
          Showing the newest measurement method only; different pipelines are not combined in one trend.
        </p>
      )}
    </section>
  );
}
