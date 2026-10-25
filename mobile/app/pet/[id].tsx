/** Create (`/pet/new`) or edit (`/pet/<id>`) a pet profile. Plain form, local save. */

import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button, Card, Chip, Eyebrow, Muted } from '../../src/components/ui';
import { useLocalData } from '../../src/hooks/use-local-data';
import { petFormIsValid, validatePetForm, type PetFormErrors } from '../../src/lib/pet-form';
import type { PetInput } from '../../src/lib/types';
import { fontFamily, radius, spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

const SPECIES = ['Dog', 'Cat', 'Other'];

const EMPTY: PetInput = { name: '', species: 'Dog', breed: '', age: '', weight: '', notes: '' };

function Field({
  label,
  value,
  onChange,
  placeholder,
  keyboardType,
  multiline,
  error,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  keyboardType?: 'default' | 'decimal-pad';
  multiline?: boolean;
  error?: string;
}) {
  const colors = useColors();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        keyboardType={keyboardType}
        multiline={multiline}
        aria-invalid={error ? true : undefined}
        style={[
          styles.input,
          { color: colors.text, borderColor: error ? colors.error : colors.border, backgroundColor: colors.background },
          multiline && styles.inputMultiline,
        ]}
      />
      {error ? (
        <Text accessibilityRole="alert" style={[styles.error, { color: colors.error }]}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}

export default function PetScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { pets, addPet, updatePet, deletePet } = useLocalData();
  const router = useRouter();

  const existing = id === 'new' ? undefined : pets.find((pet) => pet.id === id);
  const [form, setForm] = useState<PetInput>(
    existing
      ? { name: existing.name, species: existing.species, breed: existing.breed, age: existing.age, weight: existing.weight, notes: existing.notes }
      : EMPTY,
  );

  const [attempted, setAttempted] = useState(false);
  const colors = useColors();

  const set = (key: keyof PetInput) => (value: string) => setForm((current) => ({ ...current, [key]: value }));
  const validated = validatePetForm(form);
  const errors: PetFormErrors = {
    ...(attempted ? validated : {}),
    ...(validated.age ? { age: validated.age } : {}),
    ...(validated.weight ? { weight: validated.weight } : {}),
  };

  function save() {
    const next = validatePetForm(form);
    setAttempted(true);
    if (!petFormIsValid(next)) return;

    const payload = { ...form, weightUnit: 'lb' as const };
    if (existing) {
      updatePet(existing.id, payload);
      router.back();
    } else {
      addPet(payload);
      router.replace('/pet');
    }
  }

  function confirmDelete() {
    if (!existing) return;
    Alert.alert(`Remove ${existing.name}?`, 'Their saved walks will be removed from this phone as well.', [
      { text: 'Keep', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => {
          deletePet(existing.id);
          router.replace('/');
        },
      },
    ]);
  }

  return (
    <>
      <Stack.Screen options={{ title: existing ? 'Edit Profile' : 'New Profile' }} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
        <Card>
          <Eyebrow>{existing ? 'Edit profile' : 'New Profile'}</Eyebrow>
          <Muted>Only a name is required. Nothing here leaves the phone.</Muted>

          <Field label="Name" value={form.name} onChange={set('name')} error={errors.name} />

          <View style={{ gap: 6 }}>
            <Text style={[styles.label, { color: colors.text }]}>Species</Text>
            <View style={styles.chips}>
              {SPECIES.map((species) => (
                <Chip key={species} label={species} selected={form.species === species} onPress={() => set('species')(species)} />
              ))}
            </View>
          </View>

          <Field label="Breed" value={form.breed} onChange={set('breed')} />
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Field label="Age (years)" value={form.age} onChange={set('age')} keyboardType="decimal-pad" error={errors.age} />
            </View>
            <View style={{ flex: 1 }}>
              <Field label="Weight (lb)" value={form.weight} onChange={set('weight')} keyboardType="decimal-pad" error={errors.weight} />
            </View>
          </View>
          <Field label="Baseline notes" value={form.notes} onChange={set('notes')} multiline />

          <Button label={existing ? 'Save changes' : 'Save and record a walk'} icon="checkmark" onPress={save} />
          {existing && <Button label="Remove pet" icon="trash-outline" variant="danger" onPress={confirmDelete} />}
        </Card>
      </ScrollView>
      </KeyboardAvoidingView>
    </>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  label: { fontFamily: fontFamily.sans, fontSize: 13, fontWeight: '600' },
  input: {
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: 16,
  },
  inputMultiline: { minHeight: 90, textAlignVertical: 'top' },
  error: { fontSize: 13, lineHeight: 18 },
  chips: { flexDirection: 'row', gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.md },
});
