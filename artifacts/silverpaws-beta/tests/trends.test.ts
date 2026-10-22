/**
 * Trend grouping. Walks from different pipelines must never share a series,
 * and a missing score must stay null rather than become zero.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { formatTrendScore, sparklineLayout, trendSeries, type TrendInput } from "../src/lib/trends.ts";

function walk(overrides: Partial<TrendInput> & Pick<TrendInput, "id" | "createdAt">): TrendInput {
  return {
    pipeline: "opencv-motion",
    status: "complete",
    overallScore: 80,
    factors: { movementConsistency: 70, symmetry: null },
    ...overrides,
  };
}

test("an empty history produces no series and no invented points", () => {
  assert.deepEqual(trendSeries([]), []);
});

test("one saved walk stays a single point", () => {
  const series = trendSeries([
    walk({ id: "a", createdAt: "2026-10-01T12:00:00.000Z", overallScore: 81.2 }),
  ]);

  assert.equal(series.length, 1);
  assert.equal(series[0]?.points.length, 1);
  assert.equal(series[0]?.points[0]?.overallScore, 81.2);
  assert.equal(series[0]?.points[0]?.symmetry, null);
  assert.equal(formatTrendScore(null), "Not scored");
});

test("many walks are ordered oldest first and a missing score is not zero", () => {
  const series = trendSeries([
    walk({ id: "new", createdAt: "2026-10-18T12:00:00.000Z", overallScore: 90 }),
    walk({ id: "old", createdAt: "2026-10-01T12:00:00.000Z", overallScore: null }),
  ]);

  assert.deepEqual(
    series[0]?.points.map((point) => point.id),
    ["old", "new"],
  );
  assert.equal(series[0]?.points[0]?.overallScore, null);

  const layout = sparklineLayout([null, 90], 280, 56);
  assert.equal(layout.dots.length, 1);
  assert.equal(layout.dots[0]?.score, 90);
  assert.equal(layout.segments.length, 0);
});

test("movenet and opencv-motion walks are never charted together", () => {
  const series = trendSeries([
    walk({ id: "motion", createdAt: "2026-10-02T12:00:00.000Z", pipeline: "opencv-motion" }),
    walk({ id: "pose", createdAt: "2026-10-03T12:00:00.000Z", pipeline: "movenet", overallScore: 70 }),
  ]);

  assert.equal(series.length, 2);
  assert.deepEqual(
    series.map((item) => item.points.map((point) => point.id)),
    [["pose"], ["motion"]],
  );
});

test("a gap in the sparkline does not connect through an unscored walk", () => {
  const layout = sparklineLayout([80, null, 90], 100, 40);
  assert.equal(layout.segments.length, 0);
  assert.equal(layout.dots.length, 2);
});

test("consecutive scored walks produce one sparkline segment", () => {
  const layout = sparklineLayout([80, 90], 100, 40);
  assert.equal(layout.segments.length, 1);
  assert.equal(layout.dots.length, 2);
});
