/**
 * Data shapes shared by every mobile screen.
 *
 * The analysis types mirror `lib/api-spec/openapi.yaml`, which is the source of
 * truth. If the API contract changes, update the spec first and then this file.
 */

export type Pipeline = 'dog-pose' | 'movenet' | 'opencv-motion';

export type SignalQuality = 'good' | 'limited' | 'unusable';

/** Factor scores from 0-100. `null` means "not enough signal", never zero. */
export type AnalysisFactors = {
  movementConsistency?: number | null;
  symmetry?: number | null;
  mobility?: number | null;
  activity?: number | null;
  historicalChange?: number | null;
};

export type AnalysisWeights = Partial<Record<keyof AnalysisFactors, number>>;

/** Raw measurements from the clip. These carry no interpretation. */
export type PoseKeypointSummary = {
  name: string;
  /** Normalized frame coordinate, from 0 to 1. */
  x: number;
  /** Normalized frame coordinate, from 0 to 1. */
  y: number;
  confidence: number;
};

export type AnalysisMeasurements = {
  poseKeypoints?: PoseKeypointSummary[] | null;
  frameCount: number;
  durationSeconds: number;
  meanKeypointConfidence?: number | null;
  leftAnkleMotion?: number | null;
  rightAnkleMotion?: number | null;
  strideSymmetry?: number | null;
  asymmetryPercent?: number | null;
  motionMean: number;
  motionStd: number;
  motionCoverage: number;
  hipStability?: number | null;
  symmetryReliable: boolean;
  strides?: {
    frontLeft?: { strideCount?: number | null } | null;
    frontRight?: { strideCount?: number | null } | null;
    rearLeft?: { strideCount?: number | null } | null;
    rearRight?: { strideCount?: number | null } | null;
  } | null;
  limbSymmetry?: { front?: number | null; rear?: number | null } | null;
  strideLengthBodyLengths?: { front?: number | null; rear?: number | null } | null;
  cadenceStridesPerMinute?: number | null;
  strideTimeCv?: number | null;
  headBobAsymmetry?: number | null;
  pelvisAsymmetry?: number | null;
  subject?: { dogFramesShare?: number | null } | null;
  notMeasuredReasons?: string[] | null;
};

export type ModelInfo = {
  pipeline: Pipeline;
  modelName: string;
  modelVersion: string;
  runsOn: 'server';
};

export type AnalyzeResult = {
  ok: boolean;
  pipeline: Pipeline;
  signalQuality: SignalQuality;
  signalNote: string;
  measurements: AnalysisMeasurements;
  factors: AnalysisFactors;
  overallScore?: number | null;
  strideSymmetryScore?: number | null;
  asymmetryPercent?: number | null;
  confidence?: number | null;
  observation: string;
  limitations: string;
  concerningChange: boolean;
  usedLlm: boolean;
  weightsUsed?: AnalysisWeights;
  modelInfo: ModelInfo;
  /** 0–1. Null when pose was not run. Null is not zero. */
  modelConfidence: number | null;
  framesUsed: number | null;
  framesTotal: number | null;
  lowConfidence: boolean;
  qualityNotes: string[];
  aiUse: string[];
};

export type Pet = {
  id: string;
  name: string;
  species: string;
  breed: string;
  age: string;
  weight: string;
  /** Unit the weight number was entered in. Missing means an older phone profile labeled lb. */
  weightUnit?: 'kg' | 'lb';
  notes: string;
  createdAt: string;
};

export type PetInput = Omit<Pet, 'id' | 'createdAt'>;

/** One saved walk. Measurements and interpretation live side by side, never merged. */
export type Analysis = {
  id: string;
  petId: string;
  fileName: string;
  durationSeconds: number;
  createdAt: string;
  pipeline: Pipeline;
  signalQuality: SignalQuality;
  signalNote: string;
  overallScore: number | null;
  factors: AnalysisFactors;
  measurements: AnalysisMeasurements;
  weightsUsed?: AnalysisWeights;
  strideSymmetryScore: number | null;
  asymmetryPercent: number | null;
  confidence: number | null;
  observation: string;
  limitations: string;
  concerningChange: boolean;
  usedLlm: boolean;
  modelInfo?: ModelInfo;
  modelConfidence?: number | null;
  framesUsed?: number | null;
  framesTotal?: number | null;
  lowConfidence?: boolean;
  qualityNotes?: string[];
  /** Sample layout only. Never written to real history. */
  demo?: boolean;
  aiUse?: string[];
};
