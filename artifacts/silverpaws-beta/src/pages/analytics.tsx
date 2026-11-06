import { useMemo, useState } from 'react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, ChartNoAxesCombined, Minus, Play } from 'lucide-react';
import { Link } from 'wouter';
import { ANALYTICS_METRICS, buildAnalyticsCohorts, metricComparisons, type AnalyticsCohort, type AnalyticsMetric, type AnalyticsMetricKey, type AnalyticsPoint } from '@/lib/analytics';
import { formatTrendScore, pipelineLabel } from '@/lib/trends';
import { formatDate } from '@/lib/format';
import type { Analysis, Pet } from '@/lib/storage';
import ProductTour from '@/components/ProductTour';

type Props = {
  analyses: Analysis[];
  pets: Pet[];
};

const CHART = { width: 720, height: 250, left: 44, right: 16, top: 16, bottom: 40 };

function scoreY(value: number) {
  return CHART.top + ((100 - value) / 100) * (CHART.height - CHART.top - CHART.bottom);
}

function scoreX(points: AnalyticsPoint[], index: number) {
  const plotWidth = CHART.width - CHART.left - CHART.right;
  return points.length === 1
    ? CHART.left + plotWidth / 2
    : CHART.left + (index / (points.length - 1)) * plotWidth;
}

function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? formatDate(value) : 'Unknown date';
}

function scoreSegments(points: AnalyticsPoint[], metric: AnalyticsMetricKey) {
  const segments: string[] = [];
  let segment: string[] = [];

  const flush = () => {
    if (segment.length > 1) segments.push(segment.join(' '));
    segment = [];
  };

  points.forEach((point, index) => {
    const value = point.scores[metric];
    if (value === null) {
      flush();
      return;
    }
    segment.push(`${scoreX(points, index).toFixed(1)},${scoreY(value).toFixed(1)}`);
  });
  flush();
  return segments;
}

function chartTargetId(cohort: AnalyticsCohort, metric: AnalyticsMetric) {
  return `analytics-chart-${cohort.pet.id}-${cohort.pipeline}-${metric.key}`;
}

function walkthroughTargetId(cohort: AnalyticsCohort) {
  return `analytics-walkthrough-${cohort.pet.id}-${cohort.pipeline}`;
}

function AnalyticsChart({ cohort, metric }: { cohort: AnalyticsCohort; metric: AnalyticsMetric }) {
  const points = cohort.points;
  const hasScores = points.some((point) => point.scores[metric.key] !== null);

  return (
    <section
      className="panel panel-padded min-w-0"
      id={chartTargetId(cohort, metric)}
      aria-label={`${metric.label} graph for ${cohort.pet.name}`}
      data-testid={`analytics-chart-${metric.key}-${cohort.pet.id}-${cohort.pipeline}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-sm">{metric.label}</h3>
          <p className="body-muted mt-1 text-xs">Score out of 100 · oldest to newest</p>
        </div>
        <span className="font-mono text-xs" style={{ color: metric.color }}>
          {points.filter((point) => point.scores[metric.key] !== null).length} scored
        </span>
      </div>
      {hasScores ? (
        <div className="mt-4 overflow-hidden">
          <svg
            aria-label={`${metric.label} scores over ${points.length} walks, from 0 to 100`}
            className="analytics-chart-svg w-full"
            role="img"
            viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          >
            {[0, 25, 50, 75, 100].map((value) => {
              const y = scoreY(value);
              return (
                <g key={value}>
                  <line className="analytics-chart-grid" x1={CHART.left} x2={CHART.width - CHART.right} y1={y} y2={y} />
                  <text fontSize="10" textAnchor="end" x={CHART.left - 8} y={y + 3}>{value}</text>
                </g>
              );
            })}
            {scoreSegments(points, metric.key).map((segment, index) => (
              <polyline
                key={index}
                fill="none"
                points={segment}
                stroke={metric.color}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="3"
              />
            ))}
            {points.map((point, index) => {
              const value = point.scores[metric.key];
              if (value === null) return null;
              return (
                <circle
                  key={point.id}
                  cx={scoreX(points, index)}
                  cy={scoreY(value)}
                  fill={metric.color}
                  r="5"
                >
                  <title>{`${dateLabel(point.createdAt)} · ${point.fileName}: ${formatTrendScore(value)}/100`}</title>
                </circle>
              );
            })}
            <text fontSize="10" textAnchor="start" x={CHART.left} y={CHART.height - 14}>
              {dateLabel(points[0]?.createdAt ?? '')}
            </text>
            <text fontSize="10" textAnchor="end" x={CHART.width - CHART.right} y={CHART.height - 14}>
              {dateLabel(points[points.length - 1]?.createdAt ?? '')}
            </text>
          </svg>
        </div>
      ) : (
        <p className="body-muted mt-5 rounded-xl border border-slate-700/70 bg-slate-950/30 p-4 text-sm">
          This measure has not been scored in these walks.
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2" aria-label={`${metric.label} walks`}>
        {points.map((point) => (
          <Link
            className="rounded-lg border border-slate-700/70 px-2.5 py-1.5 text-xs text-slate-300 no-underline hover:border-petlens-azure"
            href={`/history/${point.id}`}
            key={point.id}
            title={point.fileName}
          >
            {dateLabel(point.createdAt)} · {formatTrendScore(point.scores[metric.key])}{point.scores[metric.key] === null ? '' : '/100'}
            {point.sampleData ? ' · Sample' : ''}
          </Link>
        ))}
      </div>
    </section>
  );
}

function Walkthrough({ cohort }: { cohort: AnalyticsCohort }) {
  const comparisons = metricComparisons(cohort);

  return (
    <section
      className="panel panel-padded mt-5"
      id={walkthroughTargetId(cohort)}
      aria-label={`Score walkthrough for ${cohort.pet.name}`}
    >
      <div className="eyebrow">Walk-through</div>
      <h3 className="display-title mt-2 text-2xl">What changed between walks?</h3>
      {comparisons.length ? (
        <ol className="mt-5 grid gap-3">
          {comparisons.map(({ metric, previous, current, delta }, index) => {
            const direction = delta > 0 ? 'improvement' : delta < 0 ? 'negative growth' : 'no change';
            const Icon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
            const previousScore = previous.scores[metric.key];
            const currentScore = current.scores[metric.key];
            const deltaLabel = formatTrendScore(Math.abs(delta));
            return (
              <li
                className="soft-note flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                key={`${metric.key}-${previous.id}-${current.id}`}
                data-testid={`analytics-comparison-${index + 1}`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`analytics-growth-badge inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${delta > 0 ? 'bg-emerald-400/15 text-emerald-300' : delta < 0 ? 'bg-rose-400/15 text-rose-300' : 'bg-slate-700 text-slate-200'}`}>
                      <Icon aria-hidden="true" size={14} />
                      {direction}
                    </span>
                    <span className="font-semibold text-sm">{metric.label}</span>
                    <span className="font-mono text-xs" style={{ color: metric.color }}>
                      {formatTrendScore(previousScore)} → {formatTrendScore(currentScore)} ({delta > 0 ? '+' : delta < 0 ? '−' : ''}{deltaLabel} pts)
                    </span>
                  </div>
                  <p className="body-muted mt-2 text-xs">
                    {dateLabel(previous.createdAt)} to {dateLabel(current.createdAt)}
                    {previous.sampleData || current.sampleData ? ' · Includes sample data' : ''}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Link className="btn-quiet text-xs" href={`/history/${previous.id}`}>Earlier walk <ArrowRight size={13} /></Link>
                  <Link className="btn-quiet text-xs" href={`/history/${current.id}`}>Later walk <ArrowRight size={13} /></Link>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="body-muted mt-3 text-sm leading-relaxed">
          At least two walks with a scored measure from the same measurement method are needed for a comparison.
        </p>
      )}
      <p className="body-muted mt-4 text-xs leading-relaxed">
        A higher score is labeled improvement and a lower score negative growth.
      </p>
    </section>
  );
}

function SimpleAnalyticsExplanations({ cohort }: { cohort: AnalyticsCohort }) {
  const comparisons = metricComparisons(cohort);

  return (
    <section
      className="normal-mode-only panel panel-padded mt-5"
      aria-label={`Plain-language score changes for ${cohort.pet.name}`}
      data-testid={`analytics-explanations-${cohort.pet.id}-${cohort.pipeline}`}
    >
      <div className="eyebrow">In plain language</div>
      <h3 className="display-title mt-2 text-2xl">What happened across walks?</h3>
      {comparisons.length ? (
        <ol className="mt-5 grid gap-3">
          {comparisons.map(({ metric, previous, current, delta }, index) => {
            const direction = delta > 0 ? 'Positive growth' : delta < 0 ? 'Negative growth' : 'No score change';
            const explanation = delta > 0
              ? `The ${metric.label.toLowerCase()} score went up from ${formatTrendScore(previous.scores[metric.key])} to ${formatTrendScore(current.scores[metric.key])}, an increase of ${formatTrendScore(delta)} points.`
              : delta < 0
                ? `The ${metric.label.toLowerCase()} score went down from ${formatTrendScore(previous.scores[metric.key])} to ${formatTrendScore(current.scores[metric.key])}, a decrease of ${formatTrendScore(Math.abs(delta))} points.`
                : `The ${metric.label.toLowerCase()} score stayed the same at ${formatTrendScore(current.scores[metric.key])} in both walks.`;

            return (
              <li className="soft-note p-4" key={`${metric.key}-${previous.id}-${current.id}`} data-testid={`analytics-explanation-${index + 1}`}>
                <h4 className="font-bold text-sm">{direction}: {metric.label}</h4>
                <p className="mt-2 text-sm leading-relaxed">{explanation}</p>
                <p className="body-muted mt-2 text-xs">
                  Comparing {dateLabel(previous.createdAt)} with {dateLabel(current.createdAt)}
                  {previous.sampleData || current.sampleData ? ' · Includes sample data' : ''}.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link className="btn-quiet text-xs" href={`/history/${previous.id}`}>Earlier walk <ArrowRight size={13} /></Link>
                  <Link className="btn-quiet text-xs" href={`/history/${current.id}`}>Later walk <ArrowRight size={13} /></Link>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="body-muted mt-3 text-sm leading-relaxed">
          {cohort.points.length < 2
            ? 'There is only one saved walk for this measurement method so far. Add another comparable walk to see what changed.'
            : 'There are not yet two walks with the same scored measure to compare. Measures that could not be scored are left out rather than treated as zero.'}
        </p>
      )}
      <p className="body-muted mt-4 text-xs leading-relaxed">
        Positive growth means the score went up; negative growth means it went down. These describe score changes only and do not explain why movement changed or diagnose a health condition.
      </p>
    </section>
  );
}

export default function Analytics({ analyses, pets }: Props) {
  const cohorts = useMemo(() => buildAnalyticsCohorts(analyses, pets), [analyses, pets]);
  const scoredCount = cohorts.reduce(
    (total, cohort) =>
      total + cohort.points.filter((point) => Object.values(point.scores).some((value) => value !== null)).length,
    0,
  );
  const [tourActive, setTourActive] = useState(false);
  const tourSteps = useMemo(() => {
    const steps = cohorts.flatMap((cohort) => {
      const availableMetrics = ANALYTICS_METRICS.filter((metric) =>
        cohort.points.some((point) => point.scores[metric.key] !== null),
      );
      const comparisons = metricComparisons(cohort);
      return [
        ...availableMetrics.map((metric) => {
          const metricComparisonsForChart = comparisons.filter(
            (comparison) => comparison.metric.key === metric.key,
          );
          const latestComparison = metricComparisonsForChart[metricComparisonsForChart.length - 1];
          const changeDescription = latestComparison
            ? latestComparison.delta > 0
              ? ` In the latest comparable walks, this score rose from ${formatTrendScore(latestComparison.previous.scores[metric.key])} to ${formatTrendScore(latestComparison.current.scores[metric.key])}, an improvement of ${formatTrendScore(latestComparison.delta)} points.`
              : latestComparison.delta < 0
                ? ` In the latest comparable walks, this score fell from ${formatTrendScore(latestComparison.previous.scores[metric.key])} to ${formatTrendScore(latestComparison.current.scores[metric.key])}, or negative growth of ${formatTrendScore(Math.abs(latestComparison.delta))} points.`
                : ' The latest comparable walks have the same score.'
            : ' At least two walks with a score for this measure are needed to identify a change.';
          return {
            targetId: chartTargetId(cohort, metric),
            title: `${metric.label} graph`,
            description: `Each dot is one scored walk, ordered from oldest to newest. Scores run from 0 to 100. Missing scores are left blank and are not treated as zero.${changeDescription}`,
          };
        }),
        {
          targetId: walkthroughTargetId(cohort),
          title: 'Positive and negative growth',
          description: 'This section compares each measure with the previous scored walk using the same measurement method. A higher score is called positive growth or improvement; a lower score is called negative growth. These labels describe score direction only, not your pet’s health or the cause of a change.',
        },
      ];
    });
    return [
      ...steps,
      {
        targetId: 'analytics-growth-guide',
        title: 'What growth means',
        description: 'Positive growth means a measure’s score increased compared with a prior comparable walk. Negative growth means it decreased.',
      },
    ];
  }, [cohorts]);

  return (
    <div className="page-frame analytics-page max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-5 stagger">
        <div>
          <h1 className="display-title mt-2 text-5xl">Movement <span className="text-petlens-trim">analytics</span></h1>
          <p className="analytical-only body-muted mt-3 max-w-2xl text-sm leading-relaxed">
            Compare scored measures across walks. Graphs are grouped by pet and measurement method so unlike results are never mixed.
          </p>
          <p className="normal-mode-only body-muted mt-3 max-w-2xl text-sm leading-relaxed">
            Here’s a simple explanation of how the scored movement measures changed between comparable walks.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {scoredCount > 0 && (
            <button className="analytical-only btn-secondary" onClick={() => setTourActive(true)} type="button" data-testid="button-analytics-tour">
              <Play size={15} /> Take graph tour
            </button>
          )}
          <Link className="btn-primary" href="/history">View walk history <ArrowRight size={15} /></Link>
        </div>
      </div>

      <section id="analytics-growth-guide" className="mt-5 grid gap-3 sm:grid-cols-2" aria-label="Positive and negative growth explanation">
        <div className="panel panel-padded border border-emerald-400/25">
          <div className="analytics-growth-positive flex items-center gap-2 font-semibold text-sm text-emerald-300">
            <ArrowUpRight aria-hidden="true" size={17} /> Positive growth
          </div>
          <p className="body-muted mt-2 text-sm leading-relaxed">
            A higher score than the previous comparable walk. Working towards a better life.
          </p>
        </div>
        <div className="panel panel-padded border border-rose-400/25">
          <div className="analytics-growth-negative flex items-center gap-2 font-semibold text-sm text-rose-300">
            <ArrowDownRight aria-hidden="true" size={17} /> Negative growth
          </div>
          <p className="body-muted mt-2 text-sm leading-relaxed">
            A lower score than the previous comparable walk. Discuss any concerns with your veterinarian.
          </p>
        </div>
      </section>

      {cohorts.length === 0 ? (
        <section className="panel panel-padded mt-6 text-center">
          <h2 className="display-title text-3xl">No saved walks to graph yet</h2>
          <p className="body-muted mt-3 text-sm">Complete an analysis to see its available scores here.</p>
          <Link className="btn-primary mt-5" href="/analyze">Analyze a walk <ArrowRight size={15} /></Link>
        </section>
      ) : (
        <>
          {scoredCount === 0 && (
            <p className="body-muted mt-6 text-sm">
              Saved walks are available, but none has a scored measure to graph yet.
            </p>
          )}
          {cohorts.map((cohort) => {
            const availableMetrics = ANALYTICS_METRICS.filter((metric) =>
              cohort.points.some((point) => point.scores[metric.key] !== null),
            );
            return (
              <section className="mt-8" key={`${cohort.pet.id}-${cohort.pipeline}`} data-testid="analytics-cohort">
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <div className="eyebrow">{cohort.pet.name}{cohort.points.some((point) => point.sampleData) ? ' · includes sample walks' : ''}</div>
                    <h2 className="display-title mt-1 text-2xl">{pipelineLabel(cohort.pipeline)}</h2>
                  </div>
                  <span className="tag">{cohort.points.length} walk{cohort.points.length === 1 ? '' : 's'}</span>
                </div>
                <div className="analytical-only">
                  {availableMetrics.length ? (
                    <div className="grid gap-4 lg:grid-cols-2">
                      {availableMetrics.map((metric) => (
                        <AnalyticsChart cohort={cohort} key={metric.key} metric={metric} />
                      ))}
                    </div>
                  ) : (
                    <div className="panel panel-padded">
                      <p className="body-muted text-sm">No movement measures were scored in these walks.</p>
                    </div>
                  )}
                  <Walkthrough cohort={cohort} />
                </div>
                <div className="normal-mode-only">
                  <SimpleAnalyticsExplanations cohort={cohort} />
                </div>
              </section>
            );
          })}
        </>
      )}
      {tourActive && tourSteps.length > 0 && (
        <ProductTour steps={tourSteps} onComplete={() => setTourActive(false)} />
      )}
    </div>
  );
}
