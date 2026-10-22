/**
 * One in-memory copy of pets and analyses for the whole app, loaded from
 * AsyncStorage on start and written back after every change.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import {
  clearAllData,
  loadAnalyses,
  loadPets,
  makeId,
  saveAnalyses,
  savePets,
} from '../lib/storage';
import type { Analysis, Pet, PetInput } from '../lib/types';
import { isDemoWalk, realWalks } from '../lib/walks';

type LocalData = {
  loading: boolean;
  pets: Pet[];
  analyses: Analysis[];
  addPet: (input: PetInput) => Pet;
  updatePet: (id: string, input: PetInput) => void;
  deletePet: (id: string) => void;
  addAnalysis: (analysis: Analysis) => void;
  deleteAnalysis: (id: string) => void;
  resetAll: () => Promise<void>;
};

const LocalDataContext = createContext<LocalData | null>(null);

export function LocalDataProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [pets, setPets] = useState<Pet[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadPets(), loadAnalyses()]).then(([storedPets, storedAnalyses]) => {
      if (cancelled) return;
      setPets(storedPets);
      // Newest first. Sample rows are never part of real history.
      const real = realWalks(storedAnalyses).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      setAnalyses(real);
      if (real.length !== storedAnalyses.length) void saveAnalyses(real);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const commitPets = useCallback((next: Pet[]) => {
    setPets(next);
    void savePets(next);
  }, []);

  const commitAnalyses = useCallback((next: Analysis[]) => {
    setAnalyses(next);
    void saveAnalyses(next);
  }, []);

  const addPet = useCallback(
    (input: PetInput) => {
      const pet: Pet = { ...input, id: makeId('pet'), createdAt: new Date().toISOString() };
      commitPets([...pets, pet]);
      return pet;
    },
    [pets, commitPets],
  );

  const updatePet = useCallback(
    (id: string, input: PetInput) => {
      commitPets(pets.map((pet) => (pet.id === id ? { ...pet, ...input } : pet)));
    },
    [pets, commitPets],
  );

  const deletePet = useCallback(
    (id: string) => {
      commitPets(pets.filter((pet) => pet.id !== id));
      // A pet's walks go with it; they cannot be shown without their owner.
      commitAnalyses(analyses.filter((analysis) => analysis.petId !== id));
    },
    [pets, analyses, commitPets, commitAnalyses],
  );

  const addAnalysis = useCallback(
    (analysis: Analysis) => {
      if (isDemoWalk(analysis)) return;
      commitAnalyses([analysis, ...analyses]);
    },
    [analyses, commitAnalyses],
  );

  const deleteAnalysis = useCallback(
    (id: string) => {
      commitAnalyses(analyses.filter((analysis) => analysis.id !== id));
    },
    [analyses, commitAnalyses],
  );

  const resetAll = useCallback(async () => {
    await clearAllData();
    setPets([]);
    setAnalyses([]);
  }, []);

  const value = useMemo<LocalData>(
    () => ({ loading, pets, analyses, addPet, updatePet, deletePet, addAnalysis, deleteAnalysis, resetAll }),
    [loading, pets, analyses, addPet, updatePet, deletePet, addAnalysis, deleteAnalysis, resetAll],
  );

  return <LocalDataContext.Provider value={value}>{children}</LocalDataContext.Provider>;
}

export function useLocalData() {
  const context = useContext(LocalDataContext);
  if (!context) throw new Error('useLocalData must be used inside LocalDataProvider');
  return context;
}
