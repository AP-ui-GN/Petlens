import { useState } from 'react';
import { useRouter } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';

import { Button, Card, Eyebrow, Muted, Title } from '../src/components/ui';
import { spacing } from '../src/theme';

const STEPS = [
  {
    title: 'Try a sample walk',
    body: 'Click \'Try Sample Dog Walk\' below to run a sample movement tracking test. The example is mock data, not an analysis of a real clip.',
  },
  {
    title: 'Pose keypoints',
    body: 'When pose output is available, the result identifies the model’s joint labels. The current COCO-17 head has no tail-base point and is not validated canine anatomy.',
  },
  {
    title: 'Factor scores',
    body: 'The result separates measured factors. “Not scored” means there was not enough signal to measure a value; it does not mean zero.',
  },
  {
    title: 'Movement report',
    body: 'Share a movement-observation report from a saved walk or a veterinarian summary from your history. These are educational notes, not a diagnosis.',
  },
];

export default function GuidedTourScreen() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const current = STEPS[step] ?? STEPS[0]!;
  const last = step === STEPS.length - 1;

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Muted>Step {step + 1} of {STEPS.length}</Muted>
      <Card>
        <Eyebrow>PetLens walkthrough</Eyebrow>
        <Title>{current.title}</Title>
        <Muted>{current.body}</Muted>
      </Card>
      <View style={styles.row}>
        {step > 0 && (
          <Button label="Back" variant="secondary" onPress={() => setStep((value) => value - 1)} style={{ flex: 1 }} />
        )}
        <Button
          label={last ? 'Finish' : 'Next'}
          onPress={() => last ? router.back() : setStep((value) => value + 1)}
          style={{ flex: 1 }}
        />
        {!last && (
          <Button label="Skip" variant="secondary" onPress={() => router.back()} style={{ flex: 1 }} />
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  row: { flexDirection: 'row', gap: spacing.sm },
});
