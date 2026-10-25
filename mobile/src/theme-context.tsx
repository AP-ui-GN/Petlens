/**
 * Light and dark palettes. Screens read colors from here so a theme change
 * is not stuck in styles created at startup.
 */

import { createContext, useContext, type ReactNode } from 'react';
import { usePreferences } from './hooks/use-preferences';
import { colors as lightColors, type ThemeColors } from './theme';

export const darkColors: ThemeColors = {
  background: '#061826',
  card: '#0a4267',
  border: '#1669aa',
  text: '#f4fbff',
  muted: '#a5bec9',
  accent: '#3eb49c',
  accentSoft: '#103d4f',
  good: '#69d8bf',
  warn: '#f1b65f',
  warnSoft: '#3a311c',
  error: '#ff8b84',
  errorSoft: '#3a2420',
  track: '#12364b',
};

const ThemeContext = createContext<ThemeColors>(lightColors);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { ready, preferences } = usePreferences();
  const mode = ready && preferences.theme === 'light' ? 'light' : 'dark';
  const palette = mode === 'dark' ? darkColors : lightColors;
  return <ThemeContext.Provider value={palette}>{children}</ThemeContext.Provider>;
}

export function useColors(): ThemeColors {
  return useContext(ThemeContext);
}

export function useColorMode(): 'light' | 'dark' {
  const palette = useColors();
  return palette.background === darkColors.background ? 'dark' : 'light';
}
