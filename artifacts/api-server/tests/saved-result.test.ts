/**
 * A pose deadline may keep the motion JSON the CLI already wrote.
 * That file has to be a finished analysis. A failure object is not one.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { AnalyzeMovementClipResponse } from "../../../lib/api-zod/src/generated/api.ts";
import {
  DEFAULT_ANALYSIS_TIMEOUT_MS,
  MAX_ANALYSIS_TIMEOUT_MS,
  MIN_ANALYSIS_TIMEOUT_MS,
  isFinishedAnalysis,
  resolveAnalysisTimeout,
} from "../src/lib/saved-result.ts";

const motionResult = {
  ok: true,
  pipeline: "opencv-motion",
  signalQuality: "limited",
  signalNote:
    "Pose analysis exceeded its time limit. Picture motion was measured. " +
    "Stride length and symmetry were not measured.",
  measurements: {
    poseKeypoints: null,
    frameCount: 8,
    durationSeconds: 0.8,
    meanKeypointConfidence: null,
    leftAnkleMotion: null,
    rightAnkleMotion: null,
    strideSymmetry: null,
    asymmetryPercent: null,
    motionMean: 0.2,
    motionStd: 0.1,
    motionCoverage: 0.5,
    hipStability: null,
    symmetryReliable: false,
  },
  factors: {
    movementConsistency: 40,
    symmetry: null,
    mobility: null,
    activity: 50,
    historicalChange: null,
  },
  overallScore: 44,
  strideSymmetryScore: null,
  asymmetryPercent: null,
  confidence: null,
  observation: "Picture motion was measured.",
  limitations: "Stride length was not measured.",
  concerningChange: false,
  usedLlm: false,
  modelInfo: {
    pipeline: "opencv-motion",
    modelName: "OpenCV frame difference",
    modelVersion: "4.10.0",
    runsOn: "server",
  },
  modelConfidence: null,
  framesUsed: null,
  framesTotal: null,
  lowConfidence: false,
  qualityNotes: [],
  aiUse: ["motion-fallback", "scoring", "observation-rules"],
};

test("the default analysis ceiling is ten minutes", () => {
  assert.equal(DEFAULT_ANALYSIS_TIMEOUT_MS, 600_000);
});

test("a saved motion result matches the contract and leaves stride unmeasured", () => {
  assert.equal(isFinishedAnalysis(motionResult), true);
  const parsed = AnalyzeMovementClipResponse.safeParse(motionResult);
  assert.equal(parsed.success, true);
  if (!parsed.success) return;
  assert.equal(parsed.data.pipeline, "opencv-motion");
  assert.match(parsed.data.signalNote, /Pose analysis exceeded its time limit/);
  assert.equal(parsed.data.measurements.strideSymmetry ?? null, null);
  assert.equal(parsed.data.strideSymmetryScore ?? null, null);
  assert.notEqual(parsed.data.measurements.strideSymmetry, 0);
});

test("a pipeline failure is not treated as a saved result", () => {
  const failure = { ok: false, error: "The clip could not be analyzed." };
  assert.equal(isFinishedAnalysis(failure), false);
  assert.equal(AnalyzeMovementClipResponse.safeParse(failure).success, false);
  assert.equal(isFinishedAnalysis(null), false);
  assert.equal(isFinishedAnalysis({ ok: true }), false);
});


test("analysis timeout defaults safely and accepts only bounded integer milliseconds", () => {
  assert.equal(resolveAnalysisTimeout(undefined), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout(""), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout("not-a-number"), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout("NaN"), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout("Infinity"), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout("1500.5"), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout(String(MIN_ANALYSIS_TIMEOUT_MS - 1)), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout(String(MAX_ANALYSIS_TIMEOUT_MS + 1)), DEFAULT_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout(String(MIN_ANALYSIS_TIMEOUT_MS)), MIN_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout(String(MAX_ANALYSIS_TIMEOUT_MS)), MAX_ANALYSIS_TIMEOUT_MS);
  assert.equal(resolveAnalysisTimeout("120000"), 120_000);
});
