import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Polyline } from 'react-native-svg';

import { formatDate } from '../lib/format';
import type { Analysis } from '../lib/types';
import {
  formatTrendScore,
  pipelineLabel,
  sparklineLayout,
  trendSeries,
  type TrendPoint,
  type TrendSeries,
} from '../lib/trends';
import { spacing } from '../theme';
import { useColors } from '../theme-context';
import { Card, Eyebrow, Muted } from './ui';

const CHART_WIDTH = 280;
const CHART_HEIGHT = 64;

function Sparkline({ points }: { points: TrendPoint[] }) {
  const colors = useColors();
  const scores = points.map((point) => point.overallScore);
  const layout = sparklineLayout(scores, CHART_WIDTH, CHART_HEIGHT);
  if (layout.dots.length === 0) return null;

  const summary = scores.map((score) => formatTrendScore(score)).join(', ');
  return (
    <Svg
      width="100%"
      height={CHART_HEIGHT}
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      accessibilityRole="image"
      accessibilityLabel={`Overall scores from oldest to newest: ${summary}. A gap means that walk was not scored.`}
    >
      {layout.segments.map((segment) => (
        <Polyline key={segment} points={segment} fill="none" stroke={colors.good} strokeWidth={2} />
      ))}
      {layout.dots.map((dot, index) => (
        <Circle key={`${dot.x}-${index}`} cx={dot.x} cy={dot.y} r={3.5} fill={colors.accent} />
      ))}
    </Svg>
  );
}

function seriesNote(series: TrendSeries): string {
  const scored = series.points.filter((point) => point.overallScore !== null);
  if (series.points.length === 1) {
    return 'This is the only saved walk measured this way. A second walk from the same method will show whether the scores moved.';
  }
  if (scored.length < 2) {
    return 'Only one of these walks has an overall score, so there is no line to draw. A walk without a score is not plotted as zero.';
  }
  const oldest = scored[0];
  const newest = scored[scored.length - 1];
  if (!oldest || !newest) return '';
  return `Oldest scored walk ${formatTrendScore(oldest.overallScore)} on ${formatDate(oldest.createdAt)}. Newest ${formatTrendScore(newest.overallScore)} on ${formatDate(newest.createdAt)}.`;
}

function ScoreCell({ value }: { value: number | null }) {
  const colors = useColors();
  const label = formatTrendScore(value);
  return <Text style={[styles.cell, { color: value === null ? colors.muted : colors.text }]}>{label}</Text>;
}

function TrendGroup({ series }: { series: TrendSeries }) {
  const colors = useColors();
  return (
    <View style={[styles.group, { borderTopColor: colors.border }]} accessibilityLabel={pipelineLabel(series.pipeline)}>
      <Text style={[styles.groupTitle, { color: colors.text }]}>{pipelineLabel(series.pipeline)}</Text>
      <Muted>{seriesNote(series)}</Muted>
      <Sparkline points={series.points} />
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, styles.dateCell, { color: colors.muted }]}>Date</Text>
        <Text style={[styles.headerCell, { color: colors.muted }]}>Overall</Text>
        <Text style={[styles.headerCell, { color: colors.muted }]}>Consistency</Text>
        <Text style={[styles.headerCell, { color: colors.muted }]}>Symmetry</Text>
      </View>
      {series.points.map((point) => (
        <View key={point.id} style={[styles.row, { borderTopColor: colors.border }]}>
          <Text style={[styles.cell, styles.dateCell, { color: colors.text }]}>{formatDate(point.createdAt)}</Text>
          <ScoreCell value={point.overallScore} />
          <ScoreCell value={point.movementConsistency} />
          <ScoreCell value={point.symmetry} />
        </View>
      ))}
    </View>
  );
}

export function TrendPanel({ analyses }: { analyses: Analysis[] }) {
  const colors = useColors();
  const series = trendSeries(analyses);

  return (
    <Card>
      <Eyebrow>Saved walks</Eyebrow>
      <Text style={[styles.title, { color: colors.text }]}>How the scores moved</Text>
      {series.length === 0 ? (
        <Muted>Trends appear after the first scored walk is saved. Nothing is filled in before that.</Muted>
      ) : (
        <>
          <Muted>
            {series.length > 1
              ? 'These walks were measured in more than one way. Each way is listed on its own and is not plotted together.'
              : 'Only walks measured the same way are compared. A score that was not measured is shown as “Not scored”, not as zero.'}
          </Muted>
          {series.map((item) => (
            <TrendGroup key={item.pipeline} series={item} />
          ))}
        </>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 16, fontWeight: '700' },
  group: { gap: spacing.sm, marginTop: spacing.md },
  groupTitle: { fontSize: 14, fontWeight: '700' },
  headerRow: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.sm },
  row: {
    flexDirection: 'row',
    gap: spacing.xs,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  headerCell: { flex: 1, fontSize: 11, fontWeight: '700' },
  cell: { flex: 1, fontSize: 12 },
  dateCell: { flex: 1.3 },
});
