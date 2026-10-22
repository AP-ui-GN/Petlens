/**
 * Team-defined weights, not a clinical scale.
 * The planning note used a divisor of 17.5. The weights below sum to 14.5,
 * and the score uses that sum.
 */

export const COGNITIVE_SYMPTOMS = [
  { id: 'disorientation', label: 'Disorientation/lost', weight: 2.5 },
  { id: 'night-pacing', label: 'Night pacing', weight: 2.0 },
  { id: 'stuck', label: 'Stuck in corners', weight: 2.0 },
  { id: 'soiling', label: 'House soiling', weight: 1.5 },
  { id: 'food', label: 'Food indifference', weight: 1.5 },
  { id: 'anxiety', label: 'Anxiety/restless', weight: 1.5 },
  { id: 'staring', label: 'Staring at walls', weight: 1.0 },
  { id: 'withdrawn', label: 'Withdrawn', weight: 1.0 },
  { id: 'day-sleeping', label: 'Day sleeping', weight: 1.0 },
  { id: 'clingy', label: 'Clingy', weight: 0.5 },
] as const;

export const COGNITIVE_MAX = COGNITIVE_SYMPTOMS.reduce((sum, item) => sum + item.weight, 0);

export type CognitiveLog = {
  id: string;
  petId: string;
  createdAt: string;
  hourOfDay: number;
  symptomIds: string[];
  score: number;
};

export type HappinessEntry = {
  id: string;
  petId: string;
  day: string;
  score: number;
};

const WEIGHTS = new Map(COGNITIVE_SYMPTOMS.map((item) => [item.id, item.weight]));

export function cognitiveScore(symptomIds: readonly string[]): number {
  const weighted = symptomIds.reduce((sum, id) => sum + (WEIGHTS.get(id as typeof COGNITIVE_SYMPTOMS[number]['id']) ?? 0), 0);
  const score = 100 * (1 - weighted / COGNITIVE_MAX);
  return Math.round(Math.max(0, Math.min(100, score)) * 10) / 10;
}

export function eveningSymptomNote(logs: readonly Pick<CognitiveLog, 'hourOfDay' | 'symptomIds'>[]): {
  show: boolean;
  byHour: (number | null)[];
} {
  const byHour = Array.from({ length: 24 }, (_, hour) => {
    const rows = logs.filter((log) => log.hourOfDay === hour);
    if (!rows.length) return null;
    return rows.reduce((sum, log) => sum + log.symptomIds.length, 0) / rows.length;
  });
  if (logs.length < 30) return { show: false, byHour };
  const evening = logs.filter((log) => log.hourOfDay >= 17 && log.hourOfDay <= 21);
  const other = logs.filter((log) => log.hourOfDay < 17 || log.hourOfDay > 21);
  if (!evening.length || !other.length) return { show: false, byHour };
  const mean = (rows: readonly Pick<CognitiveLog, 'symptomIds'>[]) =>
    rows.reduce((sum, log) => sum + log.symptomIds.length, 0) / rows.length;
  return { show: mean(evening) >= mean(other) * 1.4, byHour };
}

export function dailyQualityOfLife(
  mobility: number | null | undefined,
  cognitive: number | null | undefined,
  happiness: number | null | undefined,
): number | null {
  if (![mobility, cognitive, happiness].every((value) => typeof value === 'number' && Number.isFinite(value))) {
    return null;
  }
  return Math.round((Number(mobility) * 0.4 + Number(cognitive) * 0.35 + Number(happiness) * 0.25) * 10) / 10;
}

export type DailyScore = { day: string; score: number | null };

function shiftDay(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function meanOf(days: string[], scores: Map<string, number>): number | null {
  const values = days.map((day) => scores.get(day)).filter((value): value is number => typeof value === 'number');
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function qualityTrend(entries: readonly DailyScore[], today: string): {
  label: 'improving' | 'declining' | 'stable' | null;
  lowerThanAWeekAgo: boolean;
} {
  const scores = new Map(entries.filter((entry) => typeof entry.score === 'number').map((entry) => [entry.day, entry.score as number]));
  const recentDays = [0, -1, -2].map((offset) => shiftDay(today, offset));
  const earlierDays = [-3, -4, -5, -6].map((offset) => shiftDay(today, offset));
  const recent = meanOf(recentDays, scores);
  const earlier = meanOf(earlierDays, scores);
  let label: 'improving' | 'declining' | 'stable' | null = null;
  if (recent !== null && earlier !== null) {
    const delta = recent - earlier;
    label = delta > 5 ? 'improving' : delta < -5 ? 'declining' : 'stable';
  }
  const weekAgo = scores.get(shiftDay(today, -7));
  const todayScore = scores.get(today);
  const lowerThanAWeekAgo = typeof todayScore === 'number' && typeof weekAgo === 'number' && weekAgo - todayScore >= 10;
  return { label, lowerThanAWeekAgo };
}
