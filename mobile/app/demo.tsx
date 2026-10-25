/**
 * Full sample result layout for testers. No sample value comes from a clip or
 * enters saved history.
 */

import { useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';

import { FactorRow, ScoreBadge } from '../src/components/score';
import { Button, Card, Eyebrow, Muted, Note } from '../src/components/ui';
import { FACTOR_LABELS, formatMeasure } from '../src/lib/format';
import { sharePdf } from '../src/lib/print-report';
import { walkReportHtml } from '../src/lib/report-html';
import { SAMPLE_BANNER, sampleWalk } from '../src/lib/sample-walk';
import { useLocalData } from '../src/hooks/use-local-data';
import { spacing } from '../src/theme';
import { useColors } from '../src/theme-context';

export default function DemoScreen() {
  const colors = useColors();
  const { pets } = useLocalData();
  const walk = sampleWalk;
  const [sharing, setSharing] = useState(false);

  async function shareSampleReport() {
    setSharing(true);
    try {
      const outcome = await sharePdf(walkReportHtml(walk, pets), 'PetLens sample movement report');
      if (!outcome.ok) Alert.alert('Sample report not shared', outcome.message);
    } catch {
      Alert.alert('Sample report not shared', 'The report could not be opened in the share sheet.');
    } finally {
      setSharing(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Note tone="warn" title={SAMPLE_BANNER}>
        These figures are an example layout only. No video was analyzed, and this result is not saved to your pet history.
      </Note>

      <Card>
        <Text style={[styles.title, { color: colors.text }]}>A breakdown of the sample pet's walk</Text>
        <View style={styles.scoreRow}>
          <ScoreBadge score={walk.overallScore} />
          <View style={{ flex: 1 }}>
            <Eyebrow>Overall wellness indicator · example only</Eyebrow>
            <Text style={[styles.scoreText, { color: colors.text }]}>
              {formatMeasure(walk.overallScore, '/100', 0)}
            </Text>
          </View>
        </View>
        <View style={styles.tags}>
          <Text style={[styles.tag, { color: colors.text, backgroundColor: colors.accentSoft }]}>Sample values</Text>
          <Text style={[styles.tag, { color: colors.text, backgroundColor: colors.track }]}>Picture motion example</Text>
        </View>
      </Card>

      <Card>
        <Eyebrow>What we noticed</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>{walk.observation}</Text>
        <Muted>{walk.signalNote}</Muted>
      </Card>

      <Card>
        <Eyebrow>Factor breakdown · examples only</Eyebrow>
        <Muted>Missing factors are not measured. These sample figures are not evidence about an animal.</Muted>
        {FACTOR_LABELS.map((factor) => (
          <FactorRow
            key={factor.key}
            label={factor.label}
            help={factor.help}
            score={walk.factors[factor.key]}
          />
        ))}
      </Card>

      <Card>
        <Eyebrow>Raw measurements · example values</Eyebrow>
        <Muted>What a saved result can display. These values were not measured from a video.</Muted>
        <View style={styles.grid}>
          <Metric label="Frames read" value={formatMeasure(walk.measurements.frameCount, '', 0)} />
          <Metric label="Clip length" value={formatMeasure(walk.measurements.durationSeconds, ' s', 1)} />
          <Metric label="Mean frame motion" value={formatMeasure(walk.measurements.motionMean)} />
          <Metric label="Motion variation" value={formatMeasure(walk.measurements.motionStd)} />
          <Metric label="Frame motion coverage" value={formatMeasure(walk.measurements.motionCoverage * 100, '%', 0)} />
          <Metric label="Stride symmetry" value={formatMeasure(walk.measurements.strideSymmetry)} />
          <Metric label="Cadence" value={formatMeasure(walk.measurements.cadenceStridesPerMinute, ' / min', 1)} />
          <Metric label="Hip stability" value={formatMeasure(walk.measurements.hipStability)} />
        </View>
      </Card>

      <Card>
        <Eyebrow>Limitations</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>{walk.limitations}</Text>
      </Card>

      <Button label="Share sample report" icon="share-outline" variant="secondary" onPress={() => void shareSampleReport()} busy={sharing} />
    </ScrollView>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  const colors = useColors();
  return (
    <View style={[styles.metric, { backgroundColor: colors.background }]}>
      <Text style={[styles.metricLabel, { color: colors.muted }]}>{label}</Text>
      <Text style={[styles.metricValue, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  title: { fontSize: 25, lineHeight: 31, fontWeight: '800' },
  scoreRow: { flexDirection: 'row', gap: spacing.md, alignItems: 'center', marginTop: spacing.sm },
  scoreText: { fontSize: 28, fontWeight: '800', marginTop: 4 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  tag: { fontSize: 11, fontWeight: '700', overflow: 'hidden', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  body: { fontSize: 15, lineHeight: 23 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  metric: { width: '48%', borderRadius: 10, padding: spacing.md, gap: 3 },
  metricLabel: { fontSize: 11, fontWeight: '600' },
  metricValue: { fontSize: 15, fontWeight: '700' },
});
