import assert from 'node:assert/strict';
import test from 'node:test';

import { buildTelemetryCsv, buildTelemetryJson } from '../src/lib/telemetry-export.ts';

const analysis = {
  id: 'walk-42',
  petId: 'pet-1',
  fileName: 'walk.mp4',
  durationSeconds: 5,
  createdAt: '2026-10-20T12:00:00.000Z',
  status: 'complete' as const,
  strideSymmetryScore: 81,
  confidence: 75,
  modelConfidence: 0.75,
  framesUsed: 45,
  framesTotal: 50,
  observation: 'A steady walk.',
  measurements: {
    poseKeypoints: [{ name: 'left_hip', x: 0.25, y: 0.4, confidence: 0.9 }],
    frameCount: 50,
    durationSeconds: 5,
    meanKeypointConfidence: 0.9,
    motionMean: 0.1,
    motionStd: 0.02,
    motionCoverage: 0.8,
    symmetryReliable: true,
  },
};

test('JSON telemetry preserves saved mean landmarks and flags unavailable time series and angles', () => {
  const telemetry = buildTelemetryJson(analysis);

  assert.deepEqual(telemetry.measurements?.poseKeypoints, [
    { name: 'left_hip', x: 0.25, y: 0.4, confidence: 0.9 },
  ]);
  assert.equal(telemetry.computedAngles.hipExtension.status, 'not_computed');
  assert.equal(telemetry.computedAngles.stifleFlexion.value, null);
  assert.equal(telemetry.timeSeriesMetadata.rawPerFrameSeriesAvailable, false);
  assert.equal(telemetry.timeSeriesMetadata.frameCount, 50);
  assert.equal(telemetry.confidence.perLandmark?.[0].confidence, 0.9);
});

test('CSV telemetry uses the requested columns and labels uncomputed angles honestly', () => {
  const csv = buildTelemetryCsv(analysis);

  assert.ok(csv.startsWith('"Timestamp/Frame","Metric","Value","Unit","Status"'));
  assert.ok(csv.includes('"Hip extension angle","Not measured","degrees","not_computed"'));
  assert.ok(csv.includes('"Stifle flexion angle","Not measured","degrees","not_computed"'));
  assert.ok(csv.includes('"Mean across 50 frames","Landmark left_hip x","0.25","normalized coordinate","measured"'));
});
