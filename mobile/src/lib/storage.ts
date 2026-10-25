/**
 * Local-first storage for pets and saved observations.
 *
 * Records live on this phone in AsyncStorage. Every read is guarded so a missing
 * or corrupted key falls back to an empty list instead of crashing the app.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import type { Analysis, AnalyzeResult, Pet } from './types';

const PETS_KEY = 'silverpaws:pets';
const ANALYSES_KEY = 'silverpaws:analyses';

async function read<T>(key: string, fallback: T): Promise<T> {
  try {
    const value = await AsyncStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}

async function write<T>(key: string, value: T): Promise<boolean> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function loadPets() {
  return read<Pet[]>(PETS_KEY, []);
}

export function loadAnalyses() {
  return read<Analysis[]>(ANALYSES_KEY, []);
}

export function savePets(pets: Pet[]) {
  return write(PETS_KEY, pets);
}

export function saveAnalyses(analyses: Analysis[]) {
  return write(ANALYSES_KEY, analyses);
}

export async function clearAllData() {
  await AsyncStorage.multiRemove([PETS_KEY, ANALYSES_KEY]);
}

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export type ClipDetails = {
  petId: string;
  fileName: string;
  durationSeconds: number;
  source?: string;
  license?: string;
  sourceUrl?: string;
};

/** Turn an API result into a saved record. */
export function toAnalysisRecord(result: AnalyzeResult, details: ClipDetails): Analysis {
  return {
    id: makeId('walk'),
    createdAt: new Date().toISOString(),
    petId: details.petId,
    fileName: details.fileName,
    source: details.source?.trim() || undefined,
    license: details.license?.trim() || undefined,
    sourceUrl: details.sourceUrl?.trim() || undefined,
    // The pipeline measures duration from decoded frames; the picker value is the
    // fallback for containers where the frame rate could not be read.
    durationSeconds: Math.round(result.measurements.durationSeconds || details.durationSeconds),
    pipeline: result.pipeline,
    signalQuality: result.signalQuality,
    signalNote: result.signalNote,
    overallScore: result.overallScore ?? null,
    factors: result.factors,
    measurements: result.measurements,
    weightsUsed: result.weightsUsed,
    strideSymmetryScore: result.strideSymmetryScore ?? null,
    asymmetryPercent: result.asymmetryPercent ?? null,
    confidence: result.confidence ?? null,
    observation: result.observation,
    limitations: result.limitations,
    concerningChange: result.concerningChange,
    usedLlm: result.usedLlm,
    modelInfo: result.modelInfo,
    modelConfidence: result.modelConfidence,
    framesUsed: result.framesUsed,
    framesTotal: result.framesTotal,
    lowConfidence: result.lowConfidence,
    qualityNotes: result.qualityNotes,
    aiUse: result.aiUse,
  };
}

/**
 * Most recent scored walk for one pet, used as the trend baseline. Only clips
 * measured the same way can be compared, so the pipeline travels with the score.
 */
export function findBaseline(analyses: Analysis[], petId: string) {
  const previous = analyses.find(
    (analysis) => analysis.petId === petId && typeof analysis.overallScore === 'number',
  );
  if (!previous || typeof previous.overallScore !== 'number') return undefined;
  return { overallScore: previous.overallScore, pipeline: previous.pipeline };
}
