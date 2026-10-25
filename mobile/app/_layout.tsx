import { Stack } from 'expo-router';
import { useFonts } from 'expo-font';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ErrorBoundary } from '../src/components/error-boundary';
import { PreferencesProvider } from '../src/hooks/use-preferences';
import { LocalDataProvider } from '../src/hooks/use-local-data';
import { ThemeProvider, useColorMode, useColors } from '../src/theme-context';

function Navigation() {
  const [fontsLoaded, fontError] = useFonts({
    Montserrat: require('../assets/fonts/Montserrat-Variable.ttf'),
    Horizon: require('../assets/fonts/Horizon-Bold.otf'),
  });
  const colors = useColors();
  const mode = useColorMode();
  if (fontError) throw fontError;
  if (!fontsLoaded) return null;
  return (
    <>
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="history/[id]" options={{ title: 'Walk details' }} />
        <Stack.Screen name="pet/[id]" options={{ title: 'Pet profile' }} />
        <Stack.Screen name="onboarding" options={{ title: 'Before you start', headerBackVisible: false }} />
        <Stack.Screen name="guided-tour" options={{ title: 'PetLens walkthrough' }} />
        <Stack.Screen name="demo" options={{ title: 'Sample data' }} />
        <Stack.Screen name="compare" options={{ title: 'Compare walks' }} />
        <Stack.Screen name="methodology" options={{ title: 'Methodology' }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <PreferencesProvider>
        <ThemeProvider>
          <ErrorBoundary>
            <LocalDataProvider>
              <Navigation />
            </LocalDataProvider>
          </ErrorBoundary>
        </ThemeProvider>
      </PreferencesProvider>
    </SafeAreaProvider>
  );
}
