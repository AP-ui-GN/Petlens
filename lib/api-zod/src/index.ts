export * from "./generated/api";

// `./generated/api` exports an `AnalyzeMovementClipBody` zod schema and
// `./generated/types` exports an interface with the same name, so the types are
// re-exported explicitly instead of with `export *`. Consumers that need the
// request body type should use the zod schema from `./generated/api`.
export {
  AnalyzeResultPipeline,
  AnalyzeResultSignalQuality,
} from "./generated/types";
export type {
  AnalysisFactors,
  AnalysisMeasurements,
  AnalysisWeights,
  AnalyzeError,
  AnalyzeResult,
  AnalyzeResultDiagnostics,
  HealthStatus,
  ModelInfo,
  LimbSymmetryIndex,
  MotionTrace,
  MotionTracePoint,
  PairValues,
  PawStride,
  PoseKeypointSummary,
  SideOnView,
  StrideSet,
  SymmetryIndexPair,
  SubjectInfo,
} from "./generated/types";
