/**
 * Three short notes before the first analysis. The acknowledgment stays on this phone.
 */

import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, Eyebrow, Muted, Title } from '../src/components/ui';
import { usePreferences } from '../src/hooks/use-preferences';
import { CONSENT_PHRASE } from '../src/lib/preferences';
import { spacing } from '../src/theme';
import { useColors } from '../src/theme-context';

const STEPS = [
  {
    eyebrow: 'What PetLens does',
    title: 'A note about a walk',
    body: 'You save a pet, film a short walk, and the app stores measured movement values with a plain-language note you can compare later.',
  },
  {
    eyebrow: 'What it does not do',
    title: 'Not a diagnosis',
    body: 'PetLens does not detect pain, injury, or disease, and it is not for emergencies. A concerning change points you to a veterinarian.',
  },
  {
    eyebrow: 'How to film',
    title: 'One clear clip',
    body: 'Film from the side, on flat ground, with the whole body in frame and enough light to see the legs. A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to 120 seconds.',
  },
];

export default function OnboardingScreen() {
  const colors = useColors();
  const router = useRouter();
  const { update } = usePreferences();
  const [step, setStep] = useState(0);
  const [checked, setChecked] = useState(false);
  const current = STEPS[step] ?? STEPS[0];
  const last = step === STEPS.length - 1;

  function accept() {
    if (!checked) return;
    update({ consentAccepted: true, consentAcceptedAt: new Date().toISOString() });
    // Go back to wherever the notes were opened from, such as a half-finished analysis.
    if (router.canGoBack()) router.back();
    else router.replace('/analyze');
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Muted>
        {step + 1} of {STEPS.length}
      </Muted>
      <Card>
        <Eyebrow>{current.eyebrow}</Eyebrow>
        <Title>{current.title}</Title>
        <Muted>{current.body}</Muted>
      </Card>
      {last && (
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked }}
          accessibilityLabel={CONSENT_PHRASE}
          onPress={() => setChecked((value) => !value)}
          style={styles.checkRow}
        >
          <View style={[styles.box, { borderColor: colors.border, backgroundColor: checked ? colors.accent : colors.card }]}>
            {checked ? <Text style={styles.mark}>✓</Text> : null}
          </View>
          <Text style={[styles.checkLabel, { color: colors.text }]}>I understand {CONSENT_PHRASE}.</Text>
        </Pressable>
      )}
      <View style={styles.row}>
        {step > 0 && <Button label="Back" variant="secondary" onPress={() => setStep((value) => value - 1)} style={{ flex: 1 }} />}
        {last ? (
          <Button label="Continue" onPress={accept} disabled={!checked} style={{ flex: 1 }} />
        ) : (
          <Button label="Next" onPress={() => setStep((value) => value + 1)} style={{ flex: 1 }} />
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  row: { flexDirection: 'row', gap: spacing.sm },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 44 },
  box: { width: 28, height: 28, borderRadius: 6, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  mark: { color: '#fff', fontWeight: '700' },
  checkLabel: { flex: 1, fontSize: 16, lineHeight: 22 },
});
