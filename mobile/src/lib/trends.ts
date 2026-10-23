/**
 * Group saved walks for the phone trend view.
 *
 * Same rules as artifacts/silverpaws-beta/src/lib/trends.ts: one series per
 * pipeline, oldest first, and a missing score stays null.
 */

export type TrendInput = {
  id: string;
  createdAt: string;
  pipeline?: string | null;
  status?: string | null;
  overallScore?: number | null;
  factors?: {
    movementConsistency?: number | null;
    symmetry?: number | null;
  } | null;
};

export type TrendPoint = {
  id: string;
  createdAt: string;
  overallScore: number | null;
  movementConsistency: number | null;
  symmetry: number | null;
};

export type TrendSeries = {
  pipeline: string;
  points: TrendPoint[];
};

export type SparkPoint = { x: number; y: number; score: number };

const PIPELINE_LABELS: Record<string, string> = {
  "coco-pose": "COCO-17 output (canine interpretation unvalidated)",
  "dog-pose": "COCO-17 output (canine interpretation unvalidated)",
  movenet: "Pose landmarks (MoveNet)",
  "opencv-motion": "Picture motion only",
  unspecified: "Measurement method not recorded",
};

export function pipelineLabel(pipeline: string): string {
  return PIPELINE_LABELS[pipeline] ?? pipeline;
}

function finiteOrNull(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function trendSeries(analyses: TrendInput[]): TrendSeries[] {
  const groups = new Map<string, TrendPoint[]>();

  for (const item of analyses) {
    if (item.status && item.status !== "complete") continue;

    const pipeline = item.pipeline?.trim() || "unspecified";
    const point: TrendPoint = {
      id: item.id,
      createdAt: item.createdAt,
      overallScore: finiteOrNull(item.overallScore),
      movementConsistency: finiteOrNull(item.factors?.movementConsistency),
      symmetry: finiteOrNull(item.factors?.symmetry),
    };
    const list = groups.get(pipeline) ?? [];
    list.push(point);
    groups.set(pipeline, list);
  }

  const series = [...groups.entries()].map(([pipeline, points]) => ({
    pipeline,
    points: points
      .slice()
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id)),
  }));

  series.sort((a, b) => {
    const aNewest = a.points[a.points.length - 1]?.createdAt ?? "";
    const bNewest = b.points[b.points.length - 1]?.createdAt ?? "";
    return bNewest.localeCompare(aNewest) || a.pipeline.localeCompare(b.pipeline);
  });

  return series;
}

export function sparklineLayout(
  scores: (number | null)[],
  width: number,
  height: number,
  pad = 6,
): { segments: string[]; dots: SparkPoint[] } {
  const count = scores.length;
  if (count === 0) return { segments: [], dots: [] };

  const xAt = (index: number) =>
    count === 1 ? width / 2 : pad + (index * (width - pad * 2)) / (count - 1);
  const yAt = (score: number) => {
    const clamped = Math.max(0, Math.min(100, score));
    return pad + (1 - clamped / 100) * (height - pad * 2);
  };

  const dots: SparkPoint[] = [];
  const segments: string[] = [];
  let run: string[] = [];

  const flush = () => {
    if (run.length > 1) segments.push(run.join(" "));
    run = [];
  };

  scores.forEach((score, index) => {
    if (score === null) {
      flush();
      return;
    }
    const x = xAt(index);
    const y = yAt(score);
    dots.push({ x, y, score });
    run.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  });
  flush();

  return { segments, dots };
}

export function formatTrendScore(value: number | null): string {
  if (value === null) return "Not scored";
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10);
}
