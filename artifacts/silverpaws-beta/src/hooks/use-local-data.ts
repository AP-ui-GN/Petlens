import { useCallback, useEffect, useState } from 'react';
import type { CognitiveLog, HappinessEntry } from '@/lib/daily-wellness';
import {
  type Analysis,
  type Pet,
  getAnalyses,
  getCognitiveLogs,
  getHappinessEntries,
  getPets,
  makeId,
  saveAnalyses,
  saveCognitiveLogs,
  saveHappinessEntries,
  savePets,
} from '@/lib/storage';
import { createSampleWalks } from '@/lib/sample-analysis';

export function useLocalData() {
  const [pets, setPets] = useState<Pet[]>(() => getPets());
  const [analyses, setAnalyses] = useState<Analysis[]>(() => getAnalyses());
  const [cognitiveLogs, setCognitiveLogs] = useState<CognitiveLog[]>(() => getCognitiveLogs());
  const [happinessEntries, setHappinessEntries] = useState<HappinessEntry[]>(() => getHappinessEntries());

  useEffect(() => {
    savePets(pets);
  }, [pets]);

  useEffect(() => {
    saveAnalyses(analyses);
  }, [analyses]);

  useEffect(() => {
    saveCognitiveLogs(cognitiveLogs);
  }, [cognitiveLogs]);

  useEffect(() => {
    saveHappinessEntries(happinessEntries);
  }, [happinessEntries]);

  const addPet = useCallback((pet: Omit<Pet, 'id' | 'createdAt'>) => {
    const next: Pet = { ...pet, id: makeId('pet'), createdAt: new Date().toISOString() };
    setPets((current) => [...current, next]);
    return next;
  }, []);

  const updatePet = useCallback((id: string, updates: Omit<Pet, 'id' | 'createdAt'>) => {
    setPets((current) => current.map((pet) => pet.id === id ? { ...pet, ...updates } : pet));
  }, []);

  const deletePet = useCallback((id: string) => {
    setPets((current) => current.filter((pet) => pet.id !== id));
    setAnalyses((current) => current.filter((analysis) => analysis.petId !== id));
    setCognitiveLogs((current) => current.filter((log) => log.petId !== id));
    setHappinessEntries((current) => current.filter((entry) => entry.petId !== id));
  }, []);

  const addAnalysis = useCallback((analysis: Omit<Analysis, 'id' | 'createdAt'>) => {
    const next: Analysis = { ...analysis, id: makeId('analysis'), createdAt: new Date().toISOString() };
    setAnalyses((current) => [next, ...current]);
    return next;
  }, []);

  const deleteAnalysis = useCallback((id: string) => {
    setAnalyses((current) => current.filter((analysis) => analysis.id !== id));
  }, []);

  const addSampleWalks = useCallback((petId: string, count: number) => {
    const pipeline = analyses.find((analysis) => analysis.petId === petId && analysis.status === 'complete')?.pipeline ?? 'movenet';
    const samples = createSampleWalks(count, petId, pipeline);
    setAnalyses((current) => [...samples, ...current]);
    return samples;
  }, [analyses]);

  const clearSampleWalks = useCallback(() => {
    setAnalyses((current) => current.filter((analysis) => !analysis.sampleData));
  }, []);

  const addCognitiveLog = useCallback((log: Omit<CognitiveLog, 'id' | 'createdAt'>) => {
    const next: CognitiveLog = { ...log, id: makeId('cognitive'), createdAt: new Date().toISOString() };
    setCognitiveLogs((current) => [next, ...current]);
    return next;
  }, []);

  const saveHappiness = useCallback((entry: Omit<HappinessEntry, 'id'>) => {
    setHappinessEntries((current) => {
      const rest = current.filter((item) => !(item.petId === entry.petId && item.day === entry.day));
      return [{ ...entry, id: makeId('happiness') }, ...rest];
    });
  }, []);

  return {
    pets,
    analyses,
    cognitiveLogs,
    happinessEntries,
    addPet,
    updatePet,
    deletePet,
    addAnalysis,
    deleteAnalysis,
    addSampleWalks,
    clearSampleWalks,
    addCognitiveLog,
    saveHappiness,
  };
}