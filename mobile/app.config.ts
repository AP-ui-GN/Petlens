import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * Placeholder ids. Replace com.silverpaws.app before a store release.
 * The previous checked-in ids were org.silverpaws.mobile.
 */
const PLACEHOLDER_APP_ID = 'com.silverpaws.app';

export default ({ config }: ConfigContext): ExpoConfig => {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL?.trim() || null;
  const infoPlist = { ...(config.ios?.infoPlist ?? {}) };
  delete infoPlist.NSMicrophoneUsageDescription;

  return {
    ...config,
    name: config.name ?? 'PetLens AI',
    slug: config.slug ?? 'silverpaws-ai',
    runtimeVersion: { policy: 'fingerprint' },
    ios: {
      ...config.ios,
      bundleIdentifier: PLACEHOLDER_APP_ID,
      infoPlist,
    },
    android: {
      ...config.android,
      package: PLACEHOLDER_APP_ID,
    },
    plugins: [...(config.plugins ?? []), 'expo-sharing'],
    extra: {
      ...(config.extra ?? {}),
      apiUrl,
    },
  };
};
