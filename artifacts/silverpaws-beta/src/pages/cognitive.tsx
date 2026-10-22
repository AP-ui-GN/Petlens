import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import {
  COGNITIVE_SYMPTOMS,
  type CognitiveLog,
  type HappinessEntry,
  cognitiveScore,
  dailyQualityOfLife,
  eveningSymptomNote,
  qualityTrend,
} from '@/lib/daily-wellness';
import type { Analysis, Pet } from '@/lib/storage';

type Props = {
  pets: Pet[];
  analyses: Analysis[];
  cognitiveLogs: CognitiveLog[];
  happinessEntries: HappinessEntry[];
  addCognitiveLog: (log: Omit<CognitiveLog, 'id' | 'createdAt'>) => CognitiveLog;
  saveHappiness: (entry: Omit<HappinessEntry, 'id'>) => void;
};

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function latestNumber(values: (number | null | undefined)[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
  }
  return null;
}

export default function CognitivePage({
  pets,
  analyses,
  cognitiveLogs,
  happinessEntries,
  addCognitiveLog,
  saveHappiness,
}: Props) {
  const [petId, setPetId] = useState(pets[0]?.id ?? '');
  const [selected, setSelected] = useState<string[]>([]);
  const [happiness, setHappiness] = useState(50);
  const [savedNote, setSavedNote] = useState('');
  const petLogs = cognitiveLogs.filter((log) => log.petId === petId);
  const pattern = useMemo(() => eveningSymptomNote(petLogs), [petLogs]);
  const latestCognitive = petLogs[0]?.score ?? null;
  const latestMobility = latestNumber(
    analyses.filter((analysis) => analysis.petId === petId).map((analysis) => analysis.factors?.mobility),
  );
  const today = todayKey();
  const todayHappiness = happinessEntries.find((entry) => entry.petId === petId && entry.day === today)?.score;
  const qol = dailyQualityOfLife(latestMobility, latestCognitive, todayHappiness ?? null);
  const dailyScores = happinessEntries
    .filter((entry) => entry.petId === petId)
    .map((entry) => ({
      day: entry.day,
      score: dailyQualityOfLife(
        latestMobility,
        petLogs.find((log) => log.createdAt.slice(0, 10) === entry.day)?.score ?? latestCognitive,
        entry.score,
      ),
    }));
  const trend = qualityTrend(dailyScores, today);

  const toggle = (id: string) => {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  const saveLog = () => {
    if (!petId) return;
    const score = cognitiveScore(selected);
    addCognitiveLog({
      petId,
      hourOfDay: new Date().getHours(),
      symptomIds: selected,
      score,
    });
    setSavedNote(`Saved. This check scored ${score} out of 100.`);
    setSelected([]);
  };

  return (
    <div className="page-frame max-w-3xl">
      <div className="eyebrow">Daily notes</div>
      <h1 className="display-title text-5xl mt-3">Quick check</h1>
      <p className="body-muted mt-4 max-w-lg leading-relaxed">
        These are team-defined weights, not a clinical scale. The score describes what you tapped. It is not a diagnosis.
      </p>
      <section className="panel panel-padded mt-7">
        <label className="field-label" htmlFor="cognitive-pet">Who is this about?</label>
        {pets.length
          ? <select id="cognitive-pet" className="field-input" value={petId} onChange={(event) => setPetId(event.target.value)} data-testid="select-cognitive-pet">{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select>
          : <p className="body-muted text-sm">Create a pet profile first. <Link href="/pet" className="font-bold underline">Add a pet</Link></p>}
        <ul className="mt-5 flex flex-col gap-2">
          {COGNITIVE_SYMPTOMS.map((item) => (
            <li key={item.id}>
              <label className="flex items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  onChange={() => toggle(item.id)}
                  data-testid={`check-${item.id}`}
                />
                <span>{item.label}</span>
              </label>
            </li>
          ))}
        </ul>
        <p className="body-muted text-sm mt-4">This check would score {cognitiveScore(selected)} out of 100. A missing check is not zero.</p>
        <button type="button" className="btn-primary mt-4" onClick={saveLog} disabled={!petId} data-testid="button-save-cognitive">Save check</button>
        {savedNote && <p className="text-sm mt-3" role="status">{savedNote}</p>}
      </section>

      <section className="panel panel-padded mt-5">
        <h2 className="display-title text-2xl">Today</h2>
        <label className="field-label mt-4" htmlFor="happiness">Happiness, 0 to 100</label>
        <input id="happiness" type="range" min={0} max={100} value={happiness} onChange={(event) => setHappiness(Number(event.target.value))} data-testid="input-happiness" />
        <div className="text-sm mt-2">{happiness}</div>
        <button
          type="button"
          className="btn-secondary mt-3"
          disabled={!petId}
          onClick={() => saveHappiness({ petId, day: today, score: happiness })}
          data-testid="button-save-happiness"
        >
          Save happiness for today
        </button>
        <dl className="mt-5 grid gap-3">
          <div><dt className="body-muted text-xs">Latest walk mobility</dt><dd className="font-bold">{latestMobility === null ? 'Not scored' : latestMobility}</dd></div>
          <div><dt className="body-muted text-xs">Latest cognitive score</dt><dd className="font-bold">{latestCognitive === null ? 'Not scored' : latestCognitive}</dd></div>
          <div><dt className="body-muted text-xs">Daily quality of life</dt><dd className="font-bold" data-testid="text-qol">{qol === null ? 'Not scored' : qol}</dd></div>
          <div><dt className="body-muted text-xs">Recent direction</dt><dd className="font-bold">{trend.label ?? 'Not scored'}</dd></div>
        </dl>
        {trend.lowerThanAWeekAgo && (
          <p className="text-sm mt-4" role="status" data-testid="text-qol-banner">
            This is lower than a week ago. Consider asking your veterinarian.
          </p>
        )}
      </section>

      {pattern.show && (
        <section className="panel panel-padded mt-5" data-testid="section-evening">
          <h2 className="display-title text-2xl">Symptoms are more frequent in the evening</h2>
          <p className="body-muted text-sm mt-2">This compares the logs you saved. It is an observation, not a diagnosis.</p>
          <ul className="mt-4 flex flex-col gap-1">
            {pattern.byHour.map((value, hour) => (
              <li key={hour} className="text-xs flex justify-between gap-3">
                <span>{String(hour).padStart(2, '0')}:00</span>
                <span>{value === null ? 'Not measured' : value.toFixed(1)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
