import type { Analysis, Pet } from '@/lib/storage';
import { trendSeries } from './trends.ts';

export const ANALYTICS_METRICS = [
  { key: 'overall', label: 'Overall movement', color: 'var(--analytics-color-overall, #3eb49c)' },
  { key: 'consistency', label: 'Movement consistency', color: 'var(--analytics-color-consistency, #54a9df)' },
  { key: 'symmetry', label: 'Stride symmetry', color: 'var(--analytics-color-symmetry, #e8b65c)' },
  { key: 'mobility', label: 'Mobility', color: 'var(--analytics-color-mobility, #c084fc)' },
  { key: 'activity', label: 'Activity', color: 'var(--analytics-color-activity, #fb923c)' },
  { key: 'hipStability', label: 'Hip stability', color: 'var(--analytics-color-hip, #f472b6)' },
] as const;

export type AnalyticsMetric = (typeof ANALYTICS_METRICS)[number];
export type AnalyticsMetricKey = (typeof ANALYTICS_METRICS)[number]['key'];

export type AnalyticsPoint = {
  id: string;
  createdAt: string;
  fileName: string;
  sampleData: boolean;
  scores: Record<AnalyticsMetricKey, number | null>;
};

export type AnalyticsCohort = {
  pet: Pet;
  pipeline: string;
  points: AnalyticsPoint[];
};

export type MetricComparison = {
  metric: AnalyticsMetric;
  previous: AnalyticsPoint;
  current: AnalyticsPoint;
  delta: number;
};

function score(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, value));
}

function hipScore(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return score(value >= 0 && value <= 1 ? value * 100 : value);
}

function toPoint(analysis: Analysis): AnalyticsPoint {
  return {
    id: analysis.id,
    createdAt: analysis.createdAt,
    fileName: analysis.fileName,
    sampleData: analysis.sampleData === true,
    scores: {
      overall: score(analysis.overallScore),
      consistency: score(analysis.factors?.movementConsistency),
      symmetry: score(analysis.factors?.symmetry ?? analysis.strideSymmetryScore),
      mobility: score(analysis.factors?.mobility),
      activity: score(analysis.factors?.activity),
      hipStability: hipScore(analysis.measurements?.hipStability),
    },
  };
}

/** Split completed walks by pet and measurement method before comparing them. */
export function buildAnalyticsCohorts(analyses: Analysis[], pets: Pet[]): AnalyticsCohort[] {
  const cohorts: AnalyticsCohort[] = [];

  for (const pet of pets) {
    const petAnalyses = analyses.filter(
      (analysis) => analysis.petId === pet.id && !analysis.demo,
    );
    const byId = new Map(petAnalyses.map((analysis) => [analysis.id, analysis]));

    for (const series of trendSeries(petAnalyses)) {
      const points = series.points.flatMap((trendPoint) => {
        const analysis = byId.get(trendPoint.id);
        return analysis ? [toPoint(analysis)] : [];
      });
      cohorts.push({ pet, pipeline: series.pipeline, points });
    }
  }

  return cohorts;
}

/** Compare each metric with its prior scored walk in the same pet/method cohort. */
export function metricComparisons(cohort: AnalyticsCohort): MetricComparison[] {
  const comparisons: MetricComparison[] = [];

  for (const metric of ANALYTICS_METRICS) {
    const scored = cohort.points.filter((point) => point.scores[metric.key] !== null);
    for (let index = 1; index < scored.length; index += 1) {
      const previous = scored[index - 1];
      const current = scored[index];
      if (!previous || !current) continue;
      const previousScore = previous.scores[metric.key];
      const currentScore = current.scores[metric.key];
      if (previousScore === null || currentScore === null) continue;
      comparisons.push({
        metric,
        previous,
        current,
        delta: currentScore - previousScore,
      });
    }
  }

  return comparisons.sort(
    (a, b) =>
      a.current.createdAt.localeCompare(b.current.createdAt) ||
      ANALYTICS_METRICS.findIndex((metric) => metric.key === a.metric.key) -
        ANALYTICS_METRICS.findIndex((metric) => metric.key === b.metric.key),
  );
}
