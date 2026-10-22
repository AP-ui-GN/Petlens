/**
 * Which server address to use. No network and no secrets.
 *
 * A tester's saved Advanced address wins. Otherwise a release build uses
 * EXPO_PUBLIC_API_URL. The laptop guess exists only in development.
 */

export function chooseApiUrl(input: {
  saved: string | null;
  configured: string | null;
  devGuess: string | null;
  dev: boolean;
  devFallback: string;
}): string | null {
  if (input.saved) return input.saved;
  if (input.configured) return input.configured;
  if (input.dev) return input.devGuess ?? input.devFallback;
  return null;
}
