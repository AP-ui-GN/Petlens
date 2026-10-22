/**
 * A layout example for testers who cannot reach the analysis server.
 * These figures were not measured from a clip. Nothing here is written to history.
 */

import type { Analysis } from './types.ts';
import { SAMPLE_WALK_ID } from './walks.ts';

export const SAMPLE_BANNER = 'Sample data — not your pet';

export const sampleWalk: Analysis = {
  id: SAMPLE_WALK_ID,
  petId: 'sample-pet',
  fileName: 'sample-walk.mp4',
  durationSeconds: 8,
  createdAt: '2026-01-15T15:00:00.000Z',
  pipeline: 'opencv-motion',
  signalQuality: 'limited',
  signalNote: 'This is an example layout. No clip was measured.',
  overallScore: 82,
  factors: {
    movementConsistency: 78,
    symmetry: null,
    mobility: null,
    activity: 90,
    historicalChange: null,
  },
  measurements: {
    frameCount: 80,
    durationSeconds: 8,
    meanKeypointConfidence: null,
    leftAnkleMotion: null,
    rightAnkleMotion: null,
    strideSymmetry: null,
    asymmetryPercent: null,
    motionMean: 0.02,
    motionStd: 0.004,
    motionCoverage: 0.9,
    hipStability: null,
    symmetryReliable: false,
  },
  strideSymmetryScore: null,
  asymmetryPercent: null,
  confidence: null,
  observation:
    'This is sample data, not a measurement of your pet. The figures on this screen show how a saved note is laid out. They did not come from a video.',
  limitations:
    'PetLens AI does not diagnose medical conditions, replace a veterinarian, or handle emergencies. Sample data is not a wellness note about a real animal.',
  concerningChange: false,
  usedLlm: false,
  modelInfo: {
    pipeline: 'opencv-motion',
    modelName: 'Example layout',
    modelVersion: 'sample',
    runsOn: 'server',
  },
  modelConfidence: null,
  framesUsed: null,
  framesTotal: null,
  lowConfidence: false,
  qualityNotes: [],
  demo: true,
};
