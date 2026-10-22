/** Score display pieces: the big overall number and one factor row with a bar. */

import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '../theme';
import { useColors } from '../theme-context';

export function ScoreBadge({ score, size = 'large' }: { score: number | null | undefined; size?: 'large' | 'small' }) {
  const colors = useColors();
  const measured = typeof score === 'number';
  const dimension = size === 'large' ? 88 : 48;
  return (
    <View
      accessibilityLabel={measured ? `Overall wellness indicator ${Math.round(score)} out of 100` : 'Overall score not available'}
      style={[styles.badge, { width: dimension, height: dimension, borderRadius: dimension / 2, backgroundColor: colors.accentSoft }]}
    >
      <Text style={[styles.badgeNumber, { color: colors.accent }, size === 'small' && { fontSize: 17 }]}>{measured ? Math.round(score) : '—'}</Text>
      {size === 'large' && <Text style={[styles.badgeUnit, { color: colors.accent }]}>/100</Text>}
    </View>
  );
}

export function FactorRow({ label, help, score }: { label: string; help: string; score: number | null | undefined }) {
  const colors = useColors();
  const measured = typeof score === 'number';
  return (
    <View style={styles.factor} accessibilityLabel={`${label}: ${measured ? `${Math.round(score)} out of 100` : 'not scored'}`}>
      <View style={styles.factorHeader}>
        <Text style={[styles.factorLabel, { color: colors.text }]}>{label}</Text>
        <Text style={[styles.factorValue, { color: measured ? colors.text : colors.muted }]}>
          {measured ? `${Math.round(score)}` : 'Not scored'}
        </Text>
      </View>
      <View style={[styles.track, { backgroundColor: colors.track }]}>
        {measured && <View style={[styles.fill, { width: `${Math.max(2, Math.min(100, score))}%`, backgroundColor: colors.accent }]} />}
      </View>
      <Text style={[styles.help, { color: colors.muted }]}>{help}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeNumber: { fontSize: 30, fontWeight: '800', color: colors.accent },
  badgeUnit: { fontSize: 11, color: colors.accent, fontWeight: '600', marginTop: -4 },
  factor: { gap: 6, paddingVertical: spacing.sm },
  factorHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  factorLabel: { fontSize: 15, fontWeight: '600', color: colors.text },
  factorValue: { fontSize: 15, fontWeight: '700', color: colors.text },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: colors.track, overflow: 'hidden' },
  fill: { height: '100%', backgroundColor: colors.accent, borderRadius: radius.pill },
  help: { fontSize: 12, color: colors.muted },
});
