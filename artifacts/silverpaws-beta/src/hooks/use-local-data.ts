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

export function useLocalData() {
  // Start each page from this browser's saved profiles and observations.
  const [pets, setPets] = useState<Pet[]>(() => getPets());
  const [analyses, setAnalyses] = useState<Analysis[]>(() => getAnalyses());
  const [cognitiveLogs, setCognitiveLogs] = useState<CognitiveLog[]>(() => getCognitiveLogs());
  const [happinessEntries, setHappinessEntries] = useState<HappinessEntry[]>(() => getHappinessEntries());

  // Keep browser storage in sync whenever a local collection changes.
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

  const addAnalysis = useCallback((analysis: Omit<Analysis, 'id' | 'createdAt'>) => {
    const next: Analysis = { ...analysis, id: makeId('analysis'), createdAt: new Date().toISOString() };
    setAnalyses((current) => [next, ...current]);
    return next;
  }, []);

  const deleteAnalysis = useCallback((id: string) => {
    setAnalyses((current) => current.filter((analysis) => analysis.id !== id));
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
    addAnalysis,
    deleteAnalysis,
    addCognitiveLog,
    saveHappiness,
  };
}