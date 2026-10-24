import { Linking, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, Eyebrow, Muted } from '../src/components/ui';
import { spacing } from '../src/theme';
import { useColors } from '../src/theme-context';

const REFERENCES = [
  {
    title: 'Kinetic gait analysis in healthy dogs and dogs with osteoarthritis',
    citation: 'Brønniche Møller Nielsen et al., PLoS ONE 15(12), 2020.',
    url: 'https://doi.org/10.1371/journal.pone.0243819',
  },
  {
    title: 'Comparison of force plate gait analysis and owner assessment of pain using the Canine Brief Pain Inventory in dogs with osteoarthritis',
    citation: 'Brown et al., Journal of Veterinary Internal Medicine, 2013.',
    url: 'https://pubmed.ncbi.nlm.nih.gov/23311715/',
  },
  {
    title: 'Quantitative Phenotyping of Duchenne Muscular Dystrophy Dogs by Comprehensive Gait Analysis and Overnight Activity Monitoring',
    citation: 'Shin et al., PLoS ONE 8(3), 2013. This is the source paper for the supplied video; it concerns DMD, not osteoarthritis.',
    url: 'https://doi.org/10.1371/journal.pone.0059875',
  },
  {
    title: 'AP-10K animal-pose dataset and official splits',
    citation: 'Dataset repository and annotations used for the experimental dog-only pose training path. Still images are not walking clips.',
    url: 'https://github.com/AlexTheBad/AP-10K',
  },
];

export default function MethodologyScreen() {
  const colors = useColors();
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Card>
        <Eyebrow>Measurement methods</Eyebrow>
        <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>What PetLens measures today</Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The default application measures whole-picture frame motion. It does not currently produce validated canine keypoints, stride length, stance or swing duration, or an osteoarthritis score. Missing measurements stay unavailable; they are not inferred from whole-picture motion.
        </Text>
      </Card>

      <Card>
        <Eyebrow>Paired symmetry formula</Eyebrow>
        <Text style={[styles.formula, { color: colors.text }]}>SI = 200 × (L − R) ÷ (L + R)</Text>
        <Text style={[styles.formula, { color: colors.text }]}>ASI = |SI|</Text>
        <Muted>
          Positive SI means the left measurement is larger; negative means the right is larger. The absolute index ranges from 0 to 200 for non-negative paired inputs. Both measurements must be finite, use the same units, and have a positive sum. Otherwise the result is not measured.
        </Muted>
        <Muted>
          If used for lengths, SI is dimensionless: the input units cancel. For time, this same formula must compare the same timing event on both sides. Stride-cycle duration, stance duration, swing duration, and step duration are different measurements; PetLens does not currently calculate them.
        </Muted>
        <Muted>
          The experimental AP-10K gait code currently compares paired paw excursions normalized by body length, not calibrated stride lengths in metres. Its left/right interpretation and thresholds have not been validated on clinical walking videos.
        </Muted>
      </Card>

      <Card>
        <Eyebrow>Angles and camera limits</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>
          The utility implementation calculates the included angle between two 2-D vectors at a vertex and returns degrees. It returns no value for missing, non-finite, or coincident landmarks. No joint-angle graph is enabled: current app keypoints are not validated canine anatomy. A single camera view also cannot recover 3-D joint angles without calibrated multi-view or depth information.
        </Text>
      </Card>

      <Card>
        <Eyebrow>Data and model provenance</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>
          The only recorded custom training experiment used the official AP-10K split 1, filtered to 794 dog training instances and 110 validation instances. Its 225-instance, 200-image test split was inspected during development, so the reported PCK values are retrospective and not independent. AP-10K consists of still images; it has no walking-video gait labels or clinical OA outcomes.
        </Text>
        <Text style={[styles.body, { color: colors.text }]}>
          The current optional detector and COCO-17 pose weights were not trained on PetLens data. COCO-17 landmarks are human joint labels, not an anatomical canine gait model. The supplied research video comes from a DMD dog study, not an OA dataset; PetLens did not use it for training or labeled evaluation.
        </Text>
      </Card>

      <Card>
        <Eyebrow>Osteoarthritis evidence and limits</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>
          Peer-reviewed canine studies use instrumented walkways, force plates, clinical examination, and owner-reported outcomes to study mobility and OA. Those findings do not validate a phone-video motion signal or establish that asymmetry alone diagnoses OA. This repository contains no independently labeled healthy-versus-OA dog video set, clinical grades, or outcomes; no group comparison or disease association is computed.
        </Text>
        <Text style={[styles.body, { color: colors.text }]}>
          Camera angle, speed, body conformation, surface, handler motion, occlusion, and repeated clips from the same dog can confound visual measurements. Ask a veterinarian about pain, lameness, or sudden changes.
        </Text>
      </Card>

      <Card>
        <Eyebrow>Sources</Eyebrow>
        {REFERENCES.map((reference) => (
          <View key={reference.url} style={styles.reference}>
            <Text style={[styles.referenceTitle, { color: colors.text }]}>{reference.title}</Text>
            <Muted>{reference.citation}</Muted>
            <Text
              accessibilityRole="link"
              onPress={() => {
                void Linking.openURL(reference.url).catch((error: unknown) => {
                  console.error('Could not open scientific reference URL.', error);
                });
              }}
              style={{ color: colors.accent, textDecorationLine: 'underline' }}
            >
              {reference.url}
            </Text>
          </View>
        ))}
      </Card>
      <Muted>Observational educational software only. Not a diagnosis and not a substitute for veterinary care.</Muted>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  title: { fontSize: 20, fontWeight: '700' },
  body: { fontSize: 14, lineHeight: 22 },
  formula: { fontSize: 18, fontWeight: '700', marginBottom: 8 },
  reference: { gap: 4, marginTop: 12 },
  referenceTitle: { fontWeight: '700' },
});
