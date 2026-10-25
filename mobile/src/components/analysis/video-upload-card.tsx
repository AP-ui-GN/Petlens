import { StyleSheet, Text, View } from 'react-native';

import { Button, Card, Chip, Muted, Note } from '../ui';
import type { Pet } from '../../lib/types';
import { MAX_CLIP_SECONDS } from '../../lib/api';
import { fontFamily, spacing } from '../../theme';
import { useColors } from '../../theme-context';

type Props = {
  pets: Pet[];
  selectedPetId: string | null;
  onSelectPet: (petId: string) => void;
  onRecord: () => void;
  onChooseVideo: () => void;
  onTrySample: () => void;
  disabled: boolean;
};

export function VideoUploadCard({
  pets,
  selectedPetId,
  onSelectPet,
  onRecord,
  onChooseVideo,
  onTrySample,
  disabled,
}: Props) {
  const colors = useColors();

  return (
    <Card>
      <View style={styles.petPicker}>
        <Text style={[styles.fieldLabel, { color: colors.text }]}>Who is in this video?</Text>
        <View style={styles.petChips}>
          {pets.map((pet) => (
            <Chip
              key={pet.id}
              label={`${pet.name} · ${pet.species}`}
              selected={pet.id === selectedPetId}
              onPress={() => onSelectPet(pet.id)}
            />
          ))}
        </View>
      </View>

      <View style={[styles.dropzone, { backgroundColor: 'rgba(10,66,103,0.18)' }]}>
        <Text style={[styles.uploadTitle, { color: colors.text }]}>
          Please upload a side video of your dog walking.
        </Text>
        <Muted style={styles.centeredText}>
          Side view, steady camera. A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to {MAX_CLIP_SECONDS} seconds.
        </Muted>
        <View style={styles.actions}>
          <Button label="Record" icon="videocam-outline" onPress={onRecord} disabled={disabled} />
          <Button label="Choose video" variant="secondary" onPress={onChooseVideo} disabled={disabled} />
        </View>
        <Button label="Try Sample Dog Walk" variant="secondary" onPress={onTrySample} disabled={disabled} />
        <Muted style={styles.sampleNote}>Click 'Try Sample Dog Walk' below to run a sample movement tracking test.</Muted>
        <Muted style={styles.sampleNote}>
          Sample data is not measured from a video and is never saved to history.
        </Muted>
      </View>

      <Note tone="info" title="Sent only for analysis">
        Your video is sent to the PetLens analysis service. Saved measurements and notes stay on this device.
      </Note>
    </Card>
  );
}

const styles = StyleSheet.create({
  petPicker: { gap: spacing.sm },
  fieldLabel: { fontFamily: fontFamily.sans, fontSize: 12, fontWeight: '700' },
  petChips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  dropzone: {
    minHeight: 245,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: 'rgba(55,148,164,0.65)',
    borderRadius: 18,
    padding: 20,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
  },
  uploadIcon: {
    width: 66,
    height: 66,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    transform: [{ rotate: '-7deg' }],
  },
  uploadTitle: { fontFamily: fontFamily.sans, fontSize: 17, lineHeight: 24, fontWeight: '700', textAlign: 'center' },
  centeredText: { textAlign: 'center' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: spacing.sm },
  sampleNote: { textAlign: 'center', fontSize: 11 },
});
