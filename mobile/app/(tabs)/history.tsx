import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ScoreBadge } from '../../src/components/score';
import { TrendPanel } from '../../src/components/trend-panel';
import { Button, Card, Chip, EmptyState, Eyebrow, Muted } from '../../src/components/ui';
import { useLocalData } from '../../src/hooks/use-local-data';
import { formatDateTime, formatDuration, SIGNAL_LABELS } from '../../src/lib/format';
import { sharePdf } from '../../src/lib/print-report';
import { vetSummaryHtml } from '../../src/lib/report-html';
import { recentWalks } from '../../src/lib/walks';
import { spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

export default function HistoryScreen() {
  const colors = useColors();
  const { loading, pets, analyses } = useLocalData();
  const router = useRouter();
  const [petFilter, setPetFilter] = useState<string | null>(null);

  useEffect(() => {
    if (petFilter && !pets.some((pet) => pet.id === petFilter)) setPetFilter(null);
  }, [pets, petFilter]);

  const visible = useMemo(
    () => (petFilter ? analyses.filter((item) => item.petId === petFilter) : analyses),
    [analyses, petFilter],
  );

  async function shareVetSummary() {
    const rows = recentWalks(petFilter ? visible : analyses);
    const outcome = await sharePdf(vetSummaryHtml(rows, pets), 'Veterinarian summary');
    if (!outcome.ok) Alert.alert('Summary not shared', outcome.message);
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} accessibilityLabel="Loading saved walks" />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={{ gap: spacing.sm }}>
        <Eyebrow>Your local notebook</Eyebrow>
        <Text style={[styles.pageTitle, { color: colors.text }]}>
          History, not{'\n'}<Text style={{ color: colors.accent }}>a verdict.</Text>
        </Text>
        <Muted>A dated trail of observations to help you notice patterns and ask better questions.</Muted>
      </View>
      <View style={styles.countRow}>
        <Muted>{analyses.length} saved observation{analyses.length === 1 ? '' : 's'} on this device</Muted>
        <Button label="New analysis" icon="videocam-outline" onPress={() => router.push('/analyze')} />
      </View>

      {analyses.length === 0 ? (
        <Card>
          <EmptyState icon="footsteps-outline" title="No walks saved yet" body="Your first observation will appear here after you run an analysis." />
          <Button label="Record a walk" icon="videocam-outline" onPress={() => router.push('/analyze')} />
        </Card>
      ) : (
        <>
      {pets.length > 1 && (
        <View style={styles.chips}>
          <Chip label="All pets" selected={petFilter === null} onPress={() => setPetFilter(null)} />
          {pets.map((pet) => (
            <Chip key={pet.id} label={pet.name} selected={petFilter === pet.id} onPress={() => setPetFilter(pet.id)} />
          ))}
        </View>
      )}

      <View style={styles.actions}>
        <Button label="Compare two walks" variant="secondary" onPress={() => router.push('/compare')} disabled={analyses.length < 2} style={{ flex: 1 }} />
        <Button label="Vet summary" variant="secondary" onPress={() => void shareVetSummary()} disabled={visible.length === 0} style={{ flex: 1 }} />
      </View>

      <TrendPanel analyses={visible} />

      <View style={{ gap: spacing.sm }}>
        {visible.map((analysis) => {
          const pet = pets.find((item) => item.id === analysis.petId);
          return (
            <Pressable
              key={analysis.id}
              accessibilityRole="button"
              onPress={() => router.push({ pathname: '/history/[id]', params: { id: analysis.id } })}
              style={({ pressed }) => [
                styles.item,
                { backgroundColor: colors.card, borderColor: colors.border },
                pressed && { opacity: 0.8 },
              ]}
            >
              <ScoreBadge score={analysis.overallScore} size="small" />
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={[styles.itemTitle, { color: colors.text }]}>{pet?.name ?? 'Pet'}</Text>
                <Text numberOfLines={1} style={[styles.itemFile, { color: colors.muted }]}>{analysis.fileName}</Text>
                <Muted>
                  {formatDateTime(analysis.createdAt)} · {formatDuration(analysis.durationSeconds)}
                </Muted>
                <Muted>
                  {SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality}
                  {analysis.concerningChange ? ' · worth asking a vet' : ''}
                </Muted>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} accessibilityElementsHidden />
            </Pressable>
          );
        })}
      </View>
        </>
      )}

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  pageTitle: { fontSize: 34, lineHeight: 39, fontWeight: '800', letterSpacing: -0.8 },
  countRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  actions: { flexDirection: 'row', gap: spacing.sm },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderWidth: 1,
    borderRadius: 14,
    minHeight: 44,
    padding: spacing.md,
  },
  itemTitle: { fontSize: 16, fontWeight: '700' },
  itemFile: { fontSize: 12 },
});
