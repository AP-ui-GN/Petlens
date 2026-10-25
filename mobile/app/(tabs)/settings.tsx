/**
 * Where the analysis API lives, plus data reset and the safety text in full.
 *
 * In Expo Go the API address is guessed from the dev server, so most testers
 * never touch this screen. It exists for the cases where the guess is wrong.
 */

import Constants from 'expo-constants';
import * as Updates from 'expo-updates';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, Platform, ScrollView, Share, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { Button, Card, Eyebrow, Muted, Note } from '../../src/components/ui';
import { useLocalData } from '../../src/hooks/use-local-data';
import { usePreferences } from '../../src/hooks/use-preferences';
import { checkHealth, getSavedApiUrl, guessApiUrl, normalizeApiUrl, resolveApiUrl, saveApiUrl } from '../../src/lib/api';
import { EMERGENCY_NOTE, SAFETY_DISCLAIMER } from '../../src/lib/disclaimers';
import type { ThemeChoice } from '../../src/lib/preferences';
import { disableWalkReminder, enableWalkReminder } from '../../src/lib/reminder';
import { radius, spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

type Status = { kind: 'idle' } | { kind: 'checking' } | { kind: 'ok'; url: string } | { kind: 'fail'; message: string };

export default function SettingsScreen() {
  const colors = useColors();
  const router = useRouter();
  const { pets, analyses, resetAll } = useLocalData();
  const { preferences, update } = usePreferences();
  const [draft, setDraft] = useState('');
  const [usingSaved, setUsingSaved] = useState(false);
  const [status, setStatus] = useState<Status>({ kind: 'idle' });

  useEffect(() => {
    void (async () => {
      const saved = await getSavedApiUrl();
      setUsingSaved(Boolean(saved));
      setDraft(saved ?? (await resolveApiUrl()) ?? '');
    })();
  }, []);

  async function test(urlToTest?: string) {
    const normalized = normalizeApiUrl(urlToTest ?? draft);
    if (!normalized) {
      setStatus({ kind: 'fail', message: 'Enter an address like 192.168.1.20:8080.' });
      return;
    }
    setStatus({ kind: 'checking' });
    const outcome = await checkHealth(normalized);
    setStatus(outcome.ok ? { kind: 'ok', url: normalized } : { kind: 'fail', message: outcome.message });
  }

  async function save() {
    const normalized = normalizeApiUrl(draft);
    if (!normalized) {
      setStatus({ kind: 'fail', message: 'Enter an address like 192.168.1.20:8080.' });
      return;
    }
    await saveApiUrl(normalized);
    setDraft(normalized);
    setUsingSaved(true);
    await test(normalized);
  }

  async function useDetected() {
    await saveApiUrl(null);
    setUsingSaved(false);
    const detected = await resolveApiUrl();
    setDraft(detected ?? '');
    if (detected) await test(detected);
    else setStatus({ kind: 'fail', message: 'This build has no server address yet. Enter one above.' });
  }

  async function onReminder(enabled: boolean) {
    if (!enabled) {
      await disableWalkReminder();
      update({ reminderEnabled: false });
      return;
    }
    Alert.alert(
      'Weekly walk check',
      'PetLens can remind you on Sunday at 10:00 to film a short walk. This is not a medical alert. The phone will ask for notification permission next.',
      [
        { text: 'Not now', style: 'cancel' },
        {
          text: 'Continue',
          onPress: () => {
            void (async () => {
              const outcome = await enableWalkReminder();
              if (!outcome.ok) {
                Alert.alert('Reminder not set', outcome.message);
                update({ reminderEnabled: false });
                return;
              }
              update({ reminderEnabled: true });
            })();
          },
        },
      ],
    );
  }

  async function exportData() {
    const payload = {
      exportedAt: new Date().toISOString(),
      pets,
      analyses,
      preferences: {
        weightUnit: preferences.weightUnit,
        theme: preferences.theme,
        demoMode: preferences.demoMode,
        reminderEnabled: preferences.reminderEnabled,
        consentAccepted: preferences.consentAccepted,
      },
    };
    await Share.share({ message: JSON.stringify(payload, null, 2) });
  }

  function sendFeedback() {
    const version = Constants.expoConfig?.version ?? 'unknown';
    void Share.share({
      message: `PetLens AI feedback\nApp version: ${version}\nDevice: ${Platform.OS} ${String(Platform.Version)}\n\n`,
    });
  }

  function confirmReset() {
    Alert.alert('Delete all local data?', `${pets.length} pets and ${analyses.length} walks will be removed from this phone.`, [
      { text: 'Keep', style: 'cancel' },
      { text: 'Delete everything', style: 'destructive', onPress: () => void resetAll() },
    ]);
  }

  const guess = typeof __DEV__ !== 'undefined' && __DEV__ ? guessApiUrl() : null;

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <Card>
        <Eyebrow>Demo</Eyebrow>
        <SettingRow
          label="Demo mode"
          detail="Shows a sample result labeled as sample data. It is never saved to history."
          value={preferences.demoMode}
          onChange={(value) => update({ demoMode: value })}
        />
        {preferences.demoMode && <Button label="View sample result" variant="secondary" onPress={() => router.push('/demo')} />}
      </Card>

      <Card>
        <Eyebrow>Pet weight</Eyebrow>
        <Muted>Weights are saved and displayed in pounds (lb).</Muted>
      </Card>

      <Card>
        <Eyebrow>Appearance</Eyebrow>
        <Muted>The default appearance matches the dark PetLens web app. Choose light to override it.</Muted>
        <View style={styles.row}>
          {(['system', 'light', 'dark'] as ThemeChoice[]).map((choice) => (
            <Button
              key={choice}
              label={
                preferences.theme === choice
                  ? `${choice === 'system' ? 'Default dark' : choice} selected`
                  : choice === 'system' ? 'Default dark' : choice
              }
              variant={preferences.theme === choice ? 'primary' : 'secondary'}
              onPress={() => update({ theme: choice })}
              style={{ flex: 1 }}
            />
          ))}
        </View>
      </Card>

      <Card>
        <Eyebrow>Reminder</Eyebrow>
        <SettingRow
          label="Weekly walk check"
          detail="Sunday at 10:00, on this phone only. Not a medical reminder."
          value={preferences.reminderEnabled}
          onChange={(value) => void onReminder(value)}
        />
      </Card>

      <Card>
        <Eyebrow>Analysis server</Eyebrow>
        <SettingRow
          label="Advanced API address"
          detail="For testers. Leave this off unless the detected address is wrong."
          value={preferences.advancedApi}
          onChange={(value) => update({ advancedApi: value })}
        />
        {preferences.advancedApi && (
          <>
        <Muted>
          Clips are analyzed by the PetLens API. Only change this address if you were given a different server to test.{' '}
          {guess ? `Detected from the Expo dev server: ${guess}.` : 'No dev server address detected; enter the address by hand.'}
        </Muted>
        <TextInput
          accessibilityLabel="API server address"
          value={draft}
          onChangeText={setDraft}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="192.168.1.20:8080"
          placeholderTextColor={colors.muted}
          style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
        />
        <View style={styles.row}>
          <Button label="Test connection" icon="pulse-outline" variant="secondary" onPress={() => void test()} busy={status.kind === 'checking'} style={{ flex: 1 }} />
          <Button label="Save" icon="checkmark" onPress={() => void save()} style={{ flex: 1 }} />
        </View>
        {usingSaved && (
          <Button
            label={typeof __DEV__ !== 'undefined' && __DEV__ ? 'Use detected address instead' : 'Use the address from this build'}
            variant="secondary"
            onPress={() => void useDetected()}
          />
        )}

        {status.kind === 'ok' && <Note tone="info" title="Connected">The API at {status.url} answered the health check.</Note>}
        {status.kind === 'fail' && <Note tone="error" title="Not reachable">{status.message}</Note>}
          </>
        )}
      </Card>

      <Card>
        <Eyebrow>Local data</Eyebrow>
        <Muted>
          {pets.length} {pets.length === 1 ? 'pet' : 'pets'} · {analyses.length} saved {analyses.length === 1 ? 'walk' : 'walks'}. Everything is stored on this
          phone only; no account exists.
        </Muted>
        <Button label="Export all data" icon="download-outline" variant="secondary" onPress={() => void exportData()} />
        <Button label="Delete all local data" icon="trash-outline" variant="danger" onPress={confirmReset} disabled={pets.length === 0 && analyses.length === 0} />
      </Card>

      <Card>
        <Eyebrow>App updates</Eyebrow>
        <Muted>
          {Updates.isEnabled
            ? `Automatic update checks run on launch${Updates.channel ? ` on the ${Updates.channel} channel` : ''}. A downloaded update takes effect after you reopen the app.`
            : 'Over-the-air updates are not enabled in this app build.'}
        </Muted>
        <InfoRow label="App version" value={Constants.expoConfig?.version ?? 'Unavailable'} />
        <InfoRow label="Native runtime" value={Updates.runtimeVersion ?? 'Unavailable in this client'} />
        <InfoRow
          label="Running bundle"
          value={
            !Updates.isEnabled
              ? 'Unavailable in this client'
              : Updates.isEmbeddedLaunch
                ? 'Embedded fallback'
                : Updates.updateId ?? 'Update ID unavailable'
          }
        />
      </Card>

      <Card>
        <Eyebrow>App</Eyebrow>
        <Button label="Send feedback" variant="secondary" onPress={sendFeedback} />
        <Muted>Version {Constants.expoConfig?.version ?? '0.1.0'}. Feedback does not attach a video.</Muted>
      </Card>

      <Card>
        <Eyebrow>About</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>{SAFETY_DISCLAIMER}</Text>
        <Text style={[styles.body, { color: colors.text }]}>{EMERGENCY_NOTE}</Text>
        <Muted>
          PetLens AI mobile beta {Constants.expoConfig?.version ?? ''} · built for the Congressional App Challenge by Abhi, Sudarshan, and Kavin.
        </Muted>
      </Card>
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  const palette = useColors();
  return (
    <View style={styles.infoRow}>
      <Text style={{ color: palette.muted }}>{label}</Text>
      <Text selectable style={[styles.infoValue, { color: palette.text }]}>{value}</Text>
    </View>
  );
}

function SettingRow({
  label,
  detail,
  value,
  onChange,
}: {
  label: string;
  detail: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  const palette = useColors();
  return (
    <View style={styles.settingRow}>
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={{ color: palette.text, fontWeight: '600' }}>{label}</Text>
        <Muted>{detail}</Muted>
      </View>
      <Switch
        accessibilityLabel={label}
        accessibilityState={{ checked: value }}
        value={value}
        onValueChange={onChange}
        trackColor={{ false: palette.track, true: palette.accent }}
        thumbColor="#fff"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  settingRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 44 },
  infoRow: { gap: spacing.xs, paddingVertical: spacing.xs },
  infoValue: { fontSize: 14, lineHeight: 20 },
  page: { padding: spacing.lg, gap: spacing.lg },
  input: {
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: 16,
  },
  row: { flexDirection: 'row', gap: spacing.sm },
  body: { fontSize: 14, lineHeight: 21 },
});
