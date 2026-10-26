import type { Analysis, Pet } from './types';

type TelemetryValue = string | number | boolean | null | undefined | object;

function telemetryDocument(analysis: Analysis, pet?: Pet) {
  // Keep provenance, scores, measurements, and interpretation in named groups.
  return {
    schemaVersion: 1,
    exportGeneratedAt: new Date().toISOString(),
    observation: {
      analysisId: analysis.id,
      petId: analysis.petId,
      petName: pet?.name ?? null,
      fileName: analysis.fileName,
      source: analysis.source ?? null,
      license: analysis.license ?? null,
      sourceUrl: analysis.sourceUrl ?? null,
      recordedAt: analysis.createdAt,
      durationSeconds: analysis.durationSeconds,
    },
    pipeline: { name: analysis.pipeline, model: analysis.modelInfo ?? null },
    scores: {
      overallScore: analysis.overallScore,
      strideSymmetryScore: analysis.strideSymmetryScore,
      asymmetryPercent: analysis.asymmetryPercent,
      confidencePercent: analysis.confidence,
      modelConfidence: analysis.modelConfidence,
      factors: analysis.factors,
      weightsUsed: analysis.weightsUsed ?? null,
    },
    measurements: analysis.measurements,
    interpretation: {
      plainLanguageNote: analysis.observation,
      limitations: analysis.limitations,
      signalQuality: analysis.signalQuality,
      signalNote: analysis.signalNote,
      lowConfidence: analysis.lowConfidence ?? null,
      qualityNotes: analysis.qualityNotes ?? [],
      aiUse: analysis.aiUse ?? [],
    },
  };
}

function flatten(value: TelemetryValue, path: string, rows: string[][]) {
  // Mark unavailable values explicitly rather than exporting them as zero.
  if (value === null || value === undefined) {
    rows.push([path, 'Not measured', 'not_measured']);
    return;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) rows.push([path, '[]', 'measured']);
    value.forEach((item, index) => flatten(item, `${path}[${index}]`, rows));
    return;
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (entries.length === 0) rows.push([path, '{}', 'measured']);
    entries.forEach(([key, item]) => flatten(item, path ? `${path}.${key}` : key, rows));
    return;
  }
  rows.push([path, String(value), 'measured']);
}

function csvCell(value: string) {
  // Quote cells and prefix spreadsheet formula-like text before export.
  const safe = /^[\s]*[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safe.replace(/"/g, '""')}"`;
}

export function buildTelemetryJson(analysis: Analysis, pet?: Pet) {
  return telemetryDocument(analysis, pet);
}

export function buildTelemetryCsv(analysis: Analysis, pet?: Pet) {
  const rows: string[][] = [['Field', 'Value', 'Status']];
  flatten(telemetryDocument(analysis, pet), '', rows);
  return rows.map((row) => row.map(csvCell).join(',')).join('\r\n');
}
