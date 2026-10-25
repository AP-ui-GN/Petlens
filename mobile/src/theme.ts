/** Shared PetLens ocean palette. */

export type ThemeColors = {
  background: string;
  card: string;
  border: string;
  text: string;
  muted: string;
  primary: string;
  accent: string;
  accentSoft: string;
  good: string;
  warn: string;
  warnSoft: string;
  error: string;
  errorSoft: string;
  track: string;
};

// These colors sample the web panel without needing a gradient layer on native.
export const colors: ThemeColors = {
  background: '#061826',
  card: '#0a2b3e',
  border: '#204254',
  text: '#f3fafc',
  muted: '#a5bec9',
  primary: '#1669aa',
  accent: '#3eb49c',
  accentSoft: '#103541',
  good: '#3eb49c',
  warn: '#f1b65f',
  warnSoft: '#3a311c',
  error: '#ff8b84',
  errorSoft: '#3a2420',
  track: '#173746',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const fontFamily = {
  sans: 'Montserrat',
  display: 'Horizon',
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 18,
  pill: 999,
};
