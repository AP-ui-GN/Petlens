import type { Analysis, Pet } from '@/lib/storage';

type TelemetryRow = {
  timestampOrFrame: string;
  metric: string;
  value: string;
  unit: string;
  status: 'measured' | 'not_measured' | 'not_computed';
};

function angleMetric(value: null) {
  return { value, unit: 'degrees', status: 'not_computed' as const };
}

export function buildTelemetryJson(analysis: Analysis, pet?: Pet) {
  return {
    schemaVersion: 1,
    exportGeneratedAt: new Date().toISOString(),
    observation: {
      analysisId: analysis.id,
      petId: analysis.petId,
      petName: pet?.name ?? null,
      fileName: analysis.fileName,
      recordedAt: analysis.createdAt,
      status: analysis.status,
      durationSeconds: analysis.durationSeconds,
    },
    pipeline: {
      name: analysis.pipeline ?? null,
      model: analysis.modelInfo ?? null,
    },
    scores: {
      overallScore: analysis.overallScore ?? null,
      strideSymmetryScore: analysis.strideSymmetryScore ?? null,
      asymmetryPercent: analysis.asymmetryPercent ?? null,
      confidencePercent: analysis.confidence ?? null,
      modelConfidence: analysis.modelConfidence ?? null,
      factors: analysis.factors ?? null,
      weightsUsed: analysis.weightsUsed ?? null,
    },
    computedAngles: {
      hipExtension: angleMetric(null),
      stifleFlexion: angleMetric(null),
    },
    measurements: analysis.measurements ?? null,
    confidence: {
      overallPercent: analysis.confidence ?? null,
      modelMean: analysis.modelConfidence ?? null,
      meanKeypoint: analysis.measurements?.meanKeypointConfidence ?? null,
      perLandmark: analysis.measurements?.poseKeypoints?.map(({ name, confidence }) => ({
        name,
        confidence,
      })) ?? null,
    },
    timeSeriesMetadata: {
      frameCount: analysis.measurements?.frameCount ?? null,
      durationSeconds: analysis.measurements?.durationSeconds ?? analysis.durationSeconds,
      framesUsed: analysis.framesUsed ?? null,
      framesTotal: analysis.framesTotal ?? null,
      rawPerFrameSeriesAvailable: false,
      landmarkPositionsAreFrameMeans: true,
    },
    interpretation: {
      plainLanguageNote: analysis.observation ?? null,
      limitations: analysis.limitations ?? null,
      signalQuality: analysis.signalQuality ?? null,
      signalNote: analysis.signalNote ?? null,
      lowConfidence: analysis.lowConfidence ?? null,
      qualityNotes: analysis.qualityNotes ?? [],
    },
  };
}

function csvCell(value: string) {
  const safeValue = /^[\s]*[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safeValue.replace(/"/g, '""')}"`;
}

function getTelemetryRows(analysis: Analysis): TelemetryRow[] {
  const rows: TelemetryRow[] = [];
  const timestamp = analysis.createdAt;
  const frameCount = analysis.measurements?.frameCount;
  const meanFrame = `Mean across ${typeof frameCount === 'number' ? frameCount : 'available'} frames`;

  const addRow = (
    timestampOrFrame: string,
    metric: string,
    value: number | string | boolean | null | undefined,
    unit: string,
    missingStatus: 'not_measured' | 'not_computed' = 'not_measured',
  ) => {
    const hasValue = value !== null && value !== undefined &&
      (typeof value !== 'number' || Number.isFinite(value));
    rows.push({
      timestampOrFrame,
      metric,
      value: hasValue ? String(value) : 'Not measured',
      unit,
      status: hasValue ? 'measured' : missingStatus,
    });
  };

  addRow(timestamp, 'Overall wellness score', analysis.overallScore, 'score / 100');
  addRow(timestamp, 'Gait symmetry score', analysis.strideSymmetryScore, 'score / 100');
  addRow(timestamp, 'Symmetry factor score', analysis.factors?.symmetry, 'score / 100');
  addRow(timestamp, 'Asymmetry', analysis.asymmetryPercent, '%');
  addRow(timestamp, 'Analysis confidence', analysis.confidence, '%');
  addRow(timestamp, 'Model confidence', analysis.modelConfidence, 'fraction');
  addRow(timestamp, 'Hip extension angle', null, 'degrees', 'not_computed');
  addRow(timestamp, 'Stifle flexion angle', null, 'degrees', 'not_computed');

  const measurements = analysis.measurements;
  addRow(timestamp, 'Frame count', measurements?.frameCount, 'frames');
  addRow(timestamp, 'Duration', measurements?.durationSeconds ?? analysis.durationSeconds, 'seconds');
  addRow(timestamp, 'Mean keypoint confidence', measurements?.meanKeypointConfidence, 'fraction');
  addRow(timestamp, 'Cadence', measurements?.cadenceStridesPerMinute, 'strides per minute');
  addRow(timestamp, 'Stride interval variation', measurements?.strideTimeCv, 'coefficient');
  addRow(timestamp, 'Front symmetry', measurements?.limbSymmetry?.front, 'ratio');
  addRow(timestamp, 'Rear symmetry', measurements?.limbSymmetry?.rear, 'ratio');
  addRow(timestamp, 'Head vertical asymmetry', measurements?.headBobAsymmetry, 'index');
  addRow(timestamp, 'Pelvis vertical asymmetry', measurements?.pelvisAsymmetry, 'index');
  addRow(timestamp, 'Dog frames share', measurements?.subject?.dogFramesShare, 'fraction');
  if (typeof measurements?.leftAnkleMotion === 'number') {
    addRow(timestamp, 'Left ankle motion', measurements.leftAnkleMotion, 'normalized motion');
  }
  if (typeof measurements?.rightAnkleMotion === 'number') {
    addRow(timestamp, 'Right ankle motion', measurements.rightAnkleMotion, 'normalized motion');
  }
  addRow(timestamp, 'Raw stride symmetry', measurements?.strideSymmetry, 'ratio');
  addRow(timestamp, 'Raw asymmetry', measurements?.asymmetryPercent, '%');
  addRow(timestamp, 'Mean frame motion', measurements?.motionMean, 'normalized motion');
  addRow(timestamp, 'Motion variation', measurements?.motionStd, 'normalized motion');
  addRow(timestamp, 'Motion coverage', measurements?.motionCoverage, 'fraction');
  if (typeof measurements?.hipStability === 'number') {
    addRow(timestamp, 'Hip stability', measurements.hipStability, 'normalized value');
  }
  addRow(timestamp, 'Symmetry reliable', measurements?.symmetryReliable, 'boolean');
  addRow(timestamp, 'Confident frames', analysis.framesUsed, 'frames');
  addRow(timestamp, 'Frames processed by model', analysis.framesTotal, 'frames');

  for (const [name, value] of Object.entries(analysis.factors ?? {})) {
    addRow(timestamp, `Factor: ${name}`, value, 'score / 100');
  }
  for (const [name, value] of Object.entries(analysis.weightsUsed ?? {})) {
    addRow(timestamp, `Weight: ${name}`, value, 'fraction');
  }
  for (const point of measurements?.poseKeypoints ?? []) {
    addRow(meanFrame, `Landmark ${point.name} x`, point.x, 'normalized coordinate');
    addRow(meanFrame, `Landmark ${point.name} y`, point.y, 'normalized coordinate');
    addRow(meanFrame, `Landmark ${point.name} confidence`, point.confidence, 'fraction');
  }

  return rows;
}

export function buildTelemetryCsv(analysis: Analysis) {
  const header = ['Timestamp/Frame', 'Metric', 'Value', 'Unit', 'Status'];
  const lines = getTelemetryRows(analysis).map((row) => [
    row.timestampOrFrame,
    row.metric,
    row.value,
    row.unit,
    row.status,
  ]);
  return [header, ...lines].map((line) => line.map(csvCell).join(',')).join('\r\n');
}

function safeAnalysisId(id: string) {
  return id.replace(/[^a-zA-Z0-9_-]/g, '-') || 'observation';
}

function downloadFile(content: BlobPart, mimeType: string, fileName: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadTelemetryJson(analysis: Analysis, pet?: Pet) {
  const json = JSON.stringify(buildTelemetryJson(analysis, pet), null, 2);
  downloadFile(json, 'application/json;charset=utf-8', `petlens-telemetry-${safeAnalysisId(analysis.id)}.json`);
}

export function downloadTelemetryCsv(analysis: Analysis) {
  downloadFile(buildTelemetryCsv(analysis), 'text/csv;charset=utf-8', `petlens-telemetry-${safeAnalysisId(analysis.id)}.csv`);
}
