import assert from 'node:assert/strict';
import test from 'node:test';

import { createSampleAnalysis, createSampleWalks, SAMPLE_DATA_LABEL } from '../src/lib/sample-analysis.ts';

test('demo result has labeled mock factors and pose keypoints', () => {
  const sample = createSampleAnalysis();

  assert.equal(sample.demo, true);
  assert.equal(SAMPLE_DATA_LABEL, 'Sample data — not your pet');
  assert.equal(sample.pipeline, 'movenet');
  assert.equal(sample.factors && Object.keys(sample.factors).length, 5);
  assert.ok(Object.values(sample.factors ?? {}).every((score) => typeof score === 'number' && score >= 0 && score <= 100));
  assert.equal(sample.measurements?.poseKeypoints?.length, 12);
  assert.equal(sample.measurements?.motionCoverage, 0.8);
  assert.match(sample.observation ?? '', /sample/i);
});

test('generated sample walks are pet-linked, removable sample records with distinct history points', () => {
  const samples = createSampleWalks(3, 'pet-123', 'coco-pose');

  assert.equal(samples.length, 3);
  assert.ok(samples.every((sample) =>
    sample.petId === 'pet-123' &&
    sample.pipeline === 'coco-pose' &&
    sample.sampleData === true &&
    sample.demo === false,
  ));
  assert.equal(new Set(samples.map((sample) => sample.id)).size, 3);
  assert.equal(new Set(samples.map((sample) => sample.createdAt)).size, 3);
  assert.ok(samples[0]!.createdAt > samples[2]!.createdAt);
  assert.equal(samples[0]!.fileName, 'Sample walk 3.mp4');
  assert.ok(samples.every((sample) => sample.fileName.startsWith('Sample walk')));
  assert.ok(samples.every((sample) => sample.observation?.includes('not measured from your pet')));
});
