import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, EmptyState, Eyebrow, Muted } from '../../../src/components/ui';
import { useLocalData } from '../../../src/hooks/use-local-data';
import { spacing } from '../../../src/theme';
import { useColors } from '../../../src/theme-context';

export default function PetProfilesScreen() {
  const colors = useColors();
  const { loading, pets, analyses } = useLocalData();
  const router = useRouter();

  if (loading) {
    return (
      <View style={styles.center}>
        <Text style={{ color: colors.muted }}>Loading pet profiles…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={{ gap: spacing.sm }}>
        <Eyebrow>The companion file</Eyebrow>
        <Text style={[styles.title, { color: colors.text }]}>Make it personal.</Text>
        <Muted>A little context helps every saved observation stay connected to the right pet.</Muted>
      </View>
      <Button label="Settings" icon="settings-outline" variant="secondary" onPress={() => router.push('/settings')} />
      <Card style={styles.info}>
        <Ionicons name="shield-checkmark-outline" size={17} color={colors.accent} />
        <Text style={[styles.infoText, { color: colors.text }]}>Saved only on this device</Text>
      </Card>

      {pets.length === 0 ? (
        <Card>
          <EmptyState
            icon="paw-outline"
            title="No pet profiles yet"
            body="A profile helps keep each walking observation connected to the right companion."
          />
          <Button label="Create pet profile" icon="add" onPress={() => router.push('/pet/new')} />
        </Card>
      ) : (
        <>
          <View style={styles.heading}>
            <View style={{ flex: 1 }}>
              <Eyebrow>Profiles on this device</Eyebrow>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Choose a companion to edit</Text>
            </View>
            <Button label="Add pet" icon="add" variant="secondary" onPress={() => router.push('/pet/new')} />
          </View>
          {pets.map((pet) => {
            const count = analyses.filter((walk) => walk.petId === pet.id).length;
            return (
              <Pressable
                key={pet.id}
                accessibilityRole="button"
                accessibilityLabel={`Edit ${pet.name}'s profile`}
                onPress={() => router.push({ pathname: '/pet/[id]', params: { id: pet.id } })}
                style={({ pressed }) => [
                  styles.petCard,
                  { backgroundColor: colors.card, borderColor: colors.border },
                  pressed && { opacity: 0.82 },
                ]}
              >
                <View style={[styles.avatar, { backgroundColor: colors.accentSoft }]}>
                  <Text style={[styles.avatarText, { color: colors.accent }]}>
                    {pet.name.trim().slice(0, 2).toUpperCase() || '🐾'}
                  </Text>
                </View>
                <View style={{ flex: 1, gap: 3 }}>
                  <Text style={[styles.petName, { color: colors.text }]}>{pet.name}</Text>
                  <Muted>{[pet.breed || pet.species, pet.age ? `${pet.age} years` : ''].filter(Boolean).join(' · ')}</Muted>
                  <Muted>{count} saved observation{count === 1 ? '' : 's'}</Muted>
                </View>
                <Ionicons name="chevron-forward" size={19} color={colors.muted} />
              </Pressable>
            );
          })}
        </>
      )}
      <Card style={styles.note}>
        <Text style={[styles.noteText, { color: colors.text }]}>Built for noticing, not diagnosing.</Text>
        <Muted>Notes are optional and can hold details you want to remember when reviewing a walk.</Muted>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 34, lineHeight: 40, fontWeight: '800', letterSpacing: -1 },
  info: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.md },
  infoText: { fontSize: 12, fontWeight: '600' },
  heading: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  sectionTitle: { fontSize: 17, fontWeight: '700', marginTop: 4 },
  petCard: { minHeight: 84, borderWidth: 1, borderRadius: 18, padding: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: { width: 48, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 15, fontWeight: '800' },
  petName: { fontSize: 16, fontWeight: '700' },
  note: { gap: spacing.sm },
  noteText: { fontSize: 14, fontWeight: '700' },
});
