/**
 * Sample layout for testers. This screen never writes to saved history.
 */

import { ScrollView, StyleSheet, Text } from 'react-native';

import { DisclaimerFooter } from '../src/components/disclaimer-footer';
import { ScoreBadge } from '../src/components/score';
import { Card, Eyebrow, Muted, Note } from '../src/components/ui';
import { formatMeasure } from '../src/lib/format';
import { SAMPLE_BANNER, sampleWalk } from '../src/lib/sample-walk';
import { spacing } from '../src/theme';
import { useColors } from '../src/theme-context';

export default function DemoScreen() {
  const colors = useColors();
  const walk = sampleWalk;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Note tone="warn" title={SAMPLE_BANNER}>
        These figures are an example of the layout. They were not measured from a clip, and they are not saved with your pets.
      </Note>
      <Card>
        <Eyebrow>Example only</Eyebrow>
        <ScoreBadge score={walk.overallScore} />
        <Text style={{ color: colors.text, fontSize: 16, lineHeight: 22 }}>{walk.observation}</Text>
        <Muted>Overall example: {formatMeasure(walk.overallScore, '/100', 0)}. Symmetry: {formatMeasure(walk.factors.symmetry, '/100', 0)}.</Muted>
      </Card>
      <DisclaimerFooter />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
});
