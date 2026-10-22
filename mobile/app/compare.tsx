/**
 * Two saved walks, side by side, only when they share a pipeline.
 */

import { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { DisclaimerFooter } from '../src/components/disclaimer-footer';
import { Button, Card, EmptyState, Muted, Note } from '../src/components/ui';
import { useLocalData } from '../src/hooks/use-local-data';
import { formatDate, formatMeasure, PIPELINE_LABELS } from '../src/lib/format';
import type { Analysis } from '../src/lib/types';
import { compareBlockReason, realWalks } from '../src/lib/walks';
import { spacing } from '../src/theme';
import { useColors } from '../src/theme-context';

function Cell({ label, value }: { label: string; value: string }) {
  const colors = useColors();
  return (
    <View style={{ flex: 1, gap: 2 }}>
      <Text style={{ color: colors.muted, fontSize: 12 }}>{label}</Text>
      <Text style={{ color: colors.text, fontSize: 16, fontWeight: '700' }}>{value}</Text>
    </View>
  );
}

export default function CompareScreen() {
  const colors = useColors();
  const { loading, pets, analyses } = useLocalData();
  const walks = useMemo(() => realWalks(analyses), [analyses]);
  const [leftId, setLeftId] = useState<string | null>(null);
  const [rightId, setRightId] = useState<string | null>(null);

  useEffect(() => {
    if (!leftId && walks[0]) setLeftId(walks[0].id);
    if (!rightId && walks[1]) setRightId(walks[1].id);
  }, [walks, leftId, rightId]);

  if (loading) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Muted>Loading saved walks…</Muted>
      </ScrollView>
    );
  }

  if (walks.length < 2) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Card>
          <EmptyState icon="git-compare-outline" title="Two walks are needed" body="Save two walks that were measured the same way, then come back to compare them." />
        </Card>
      </ScrollView>
    );
  }

  const left = walks.find((walk) => walk.id === leftId) ?? null;
  const right = walks.find((walk) => walk.id === rightId) ?? null;
  const reason = left && right ? compareBlockReason(left, right) : 'Choose two walks.';

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Muted>Pick two saved walks. A pair from different measurement methods is refused.</Muted>
      <WalkPicker label="First walk" walks={walks} pets={pets} selectedId={leftId} onSelect={setLeftId} />
      <WalkPicker label="Second walk" walks={walks} pets={pets} selectedId={rightId} onSelect={setRightId} />
      {reason ? (
        <Note tone="warn" title="Not compared">
          {reason}
        </Note>
      ) : (
        left &&
        right && (
          <Card>
            <Text style={{ color: colors.text, fontWeight: '700' }}>{PIPELINE_LABELS[left.pipeline] ?? left.pipeline}</Text>
            <View style={styles.columns}>
              <Column walk={left} petName={pets.find((pet) => pet.id === left.petId)?.name ?? 'Pet'} />
              <Column walk={right} petName={pets.find((pet) => pet.id === right.petId)?.name ?? 'Pet'} />
            </View>
          </Card>
        )
      )}
      <DisclaimerFooter />
    </ScrollView>
  );
}

function WalkPicker({
  label,
  walks,
  pets,
  selectedId,
  onSelect,
}: {
  label: string;
  walks: Analysis[];
  pets: { id: string; name: string }[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <Card>
      <Muted>{label}</Muted>
      {walks.map((walk) => {
        const pet = pets.find((item) => item.id === walk.petId)?.name ?? 'Pet';
        const selected = walk.id === selectedId;
        return (
          <Button
            key={walk.id}
            label={`${pet} · ${formatDate(walk.createdAt)} · ${PIPELINE_LABELS[walk.pipeline] ?? walk.pipeline}${selected ? ' · selected' : ''}`}
            variant={selected ? 'primary' : 'secondary'}
            onPress={() => onSelect(walk.id)}
          />
        );
      })}
    </Card>
  );
}

function Column({ walk, petName }: { walk: Analysis; petName: string }) {
  return (
    <View style={{ flex: 1, gap: spacing.sm }}>
      <Cell label={petName} value={formatDate(walk.createdAt)} />
      <Cell label="Overall" value={formatMeasure(walk.overallScore, '/100', 0)} />
      <Cell label="Consistency" value={formatMeasure(walk.factors.movementConsistency, '/100', 0)} />
      <Cell label="Symmetry" value={formatMeasure(walk.factors.symmetry, '/100', 0)} />
      <Cell label="Mobility" value={formatMeasure(walk.factors.mobility, '/100', 0)} />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  columns: { flexDirection: 'row', gap: spacing.md },
});
