import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, EmptyState, Eyebrow, Muted } from '../../../src/components/ui';
import { useLocalData } from '../../../src/hooks/use-local-data';
import { fontFamily, spacing } from '../../../src/theme';
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
        <Text style={[styles.title, { color: colors.text }]}>New Profile</Text>
      </View>

      {pets.length === 0 ? (
        <Card>
          <EmptyState
            icon="person-outline"
            title="No pet profiles yet"
            body="A profile keeps each walking observation connected to the right pet."
          />
          <Button label="Create pet profile" icon="add" onPress={() => router.push('/pet/new')} />
        </Card>
      ) : (
        <>
          <View style={styles.heading}>
            <View style={{ flex: 1 }}>
              <Eyebrow>Profiles on this device</Eyebrow>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Choose a pet to edit</Text>
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
                    {pet.name.trim().slice(0, 2).toUpperCase()}
                  </Text>
                </View>
                <View style={{ flex: 1, gap: 3 }}>
                  <Text style={[styles.petName, { color: colors.text }]}>{pet.name}</Text>
                  <Muted>{[pet.breed || pet.species, pet.age ? `${pet.age} years` : ''].filter(Boolean).join(' · ')}</Muted>
                  <Muted>{count} saved observation{count === 1 ? '' : 's'}</Muted>
                </View>
              </Pressable>
            );
          })}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: fontFamily.display, fontSize: 30, lineHeight: 35, letterSpacing: -0.7 },
  heading: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  sectionTitle: { fontFamily: fontFamily.display, fontSize: 16, marginTop: 4 },
  petCard: { minHeight: 84, borderWidth: 1, borderRadius: 18, padding: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: { width: 48, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontFamily: fontFamily.sans, fontSize: 15, fontWeight: '700' },
  petName: { fontFamily: fontFamily.sans, fontSize: 15, fontWeight: '700' },
});
