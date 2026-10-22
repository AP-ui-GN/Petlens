/**
 * On-device settings. Loaded once at startup and written after each change.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { DEFAULT_PREFERENCES, loadPreferences, savePreferences, type Preferences } from '../lib/preferences';

type PreferencesApi = {
  ready: boolean;
  preferences: Preferences;
  update: (patch: Partial<Preferences>) => void;
};

const PreferencesContext = createContext<PreferencesApi | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [preferences, setPreferences] = useState<Preferences>(DEFAULT_PREFERENCES);

  useEffect(() => {
    let cancelled = false;
    void loadPreferences().then((stored) => {
      if (cancelled) return;
      setPreferences(stored);
      setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const update = useCallback((patch: Partial<Preferences>) => {
    setPreferences((current) => {
      const next = { ...current, ...patch };
      void savePreferences(next);
      return next;
    });
  }, []);

  const value = useMemo<PreferencesApi>(() => ({ ready, preferences, update }), [ready, preferences, update]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error('usePreferences must be used inside PreferencesProvider');
  return context;
}
