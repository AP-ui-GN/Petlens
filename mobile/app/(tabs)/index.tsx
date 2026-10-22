import { Ionicons } from '@expo/vector-icons';
import { Link, useRouter } from 'expo-router';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { DisclaimerFooter } from '../../src/components/disclaimer-footer';
import { ScoreBadge } from '../../src/components/score';
import { Button, Card, EmptyState, Eyebrow, Muted, Note, Title } from '../../src/components/ui';
import { useLocalData } from '../../src/hooks/use-local-data';
import { usePreferences } from '../../src/hooks/use-preferences';
import { formatDate } from '../../src/lib/format';
import type { Analysis, Pet } from '../../src/lib/types';
import { weightUnitForPet } from '../../src/lib/walks';
import { spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

function describePet(pet: Pet) {
  const parts = [pet.species, pet.breed].filter((part) => part.trim());
  const age = pet.age.trim();
  if (age) parts.push(/^\d+(\.\d+)?$/.test(age) ? `${age} yrs` : age);
  if (pet.weight.trim()) {
    parts.push(`${pet.weight.trim()} ${weightUnitForPet(pet.weightUnit, 'kg', false)}`);
  }
  return parts.join(' · ') || 'No details yet';
}

function PetCard({ pet, latest }: { pet: Pet; latest?: Analysis }) {
  const colors = useColors();
  const router = useRouter();
  return (
    <Card>
      <View style={styles.petRow}>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={[styles.petName, { color: colors.text }]}>{pet.name}</Text>
          <Muted>{describePet(pet)}</Muted>
          <Muted>{latest ? `Last walk ${formatDate(latest.createdAt)}` : 'No walks recorded yet'}</Muted>
        </View>
        <ScoreBadge score={latest?.overallScore} size="small" />
      </View>
      <View style={styles.petActions}>
        <Button
          label="Record a walk"
          icon="videocam-outline"
          onPress={() => router.push({ pathname: '/analyze', params: { petId: pet.id } })}
          style={{ flex: 1 }}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Edit ${pet.name}`}
          onPress={() => router.push({ pathname: '/pet/[id]', params: { id: pet.id } })}
          style={[styles.iconButton, { borderColor: colors.border, backgroundColor: colors.card }]}
        >
          <Ionicons name="create-outline" size={20} color={colors.text} />
        </Pressable>
      </View>
    </Card>
  );
}

export default function HomeScreen() {
  const colors = useColors();
  const { loading, pets, analyses } = useLocalData();
  const { ready, preferences } = usePreferences();
  const router = useRouter();

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      {ready && !preferences.consentAccepted && (
        <Note tone="info" title="Before the first analysis">
          Three short notes explain what PetLens does and does not do. Analysis stays locked until you acknowledge that this is a wellness note, not a diagnosis.
        </Note>
      )}
      {ready && !preferences.consentAccepted && <Button label="Read the notes" onPress={() => router.push('/onboarding')} />}

      <View style={{ gap: 4 }}>
        <Eyebrow>Observational wellness notes</Eyebrow>
        <Title>{pets.length ? 'Your pets' : 'Welcome'}</Title>
        <Muted>
          Record a short walk, and PetLens measures how steady and even the movement looked. It never diagnoses.
        </Muted>
      </View>

      {pets.length === 0 ? (
        <Card>
          <EmptyState
            icon="paw-outline"
            title="Add your first pet"
            body="A profile only needs a name. Breed, age, and notes help you remember what a normal walk looks like."
          />
          <Button label="Create a pet profile" icon="add" onPress={() => router.push('/pet/new')} />
        </Card>
      ) : (
        <>
          {pets.map((pet) => (
            <PetCard key={pet.id} pet={pet} latest={analyses.find((item) => item.petId === pet.id)} />
          ))}
          <Button label="Add another pet" icon="add" variant="secondary" onPress={() => router.push('/pet/new')} />
        </>
      )}

      {analyses.length > 0 && (
        <Link href="/history" asChild>
          <Pressable accessibilityRole="link" style={styles.historyLink}>
            <Ionicons name="time-outline" size={18} color={colors.accent} />
            <Text style={[styles.historyText, { color: colors.accent }]}>
              {analyses.length} saved {analyses.length === 1 ? 'walk' : 'walks'} · open history
            </Text>
          </Pressable>
        </Link>
      )}

      <DisclaimerFooter />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  petRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  petName: { fontSize: 20, fontWeight: '700' },
  petActions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  iconButton: {
    width: 48,
    height: 48,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  historyLink: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
  historyText: { fontWeight: '600', fontSize: 14 },
});
