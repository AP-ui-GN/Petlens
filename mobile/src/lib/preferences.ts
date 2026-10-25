/**
 * Settings that stay on this phone. No account, no analytics.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'silverpaws:preferences';

export type WeightUnit = 'kg' | 'lb';
export type ThemeChoice = 'system' | 'light' | 'dark';

export type Preferences = {
  consentAccepted: boolean;
  consentAcceptedAt: string | null;
  demoMode: boolean;
  /** Default unit for a new pet. Existing pets keep the unit they were saved with. */
  weightUnit: WeightUnit;
  theme: ThemeChoice;
  reminderEnabled: boolean;
  advancedApi: boolean;
};

export const CONSENT_PHRASE = 'this is a wellness note, not a diagnosis';

export const DEFAULT_PREFERENCES: Preferences = {
  consentAccepted: false,
  consentAcceptedAt: null,
  demoMode: false,
  weightUnit: 'lb',
  theme: 'system',
  reminderEnabled: false,
  advancedApi: false,
};

export async function loadPreferences(): Promise<Preferences> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_PREFERENCES };
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    return { ...DEFAULT_PREFERENCES, ...parsed, weightUnit: 'lb' };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export async function savePreferences(preferences: Preferences): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(preferences));
  } catch {
    // The in-memory copy still applies until the next launch.
  }
}
