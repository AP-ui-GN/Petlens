/**
 * One saved walk in full: overall score, factors, raw measurements, and the
 * plain-language observation. Measurements and interpretation are shown in
 * separate sections on purpose.
 */

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';

import { ScientificCharts } from '../../src/components/scientific-charts';
import { FactorRow, ScoreBadge } from '../../src/components/score';
import { Button, Card, EmptyState, Eyebrow, Muted, Note, Tag } from '../../src/components/ui';
import { useLocalData } from '../../src/hooks/use-local-data';
import { aiUseResultLines } from '../../src/lib/ai-use';
import { EMERGENCY_NOTE, SAFETY_DISCLAIMER } from '../../src/lib/disclaimers';
import { sharePdf } from '../../src/lib/print-report';
import { vetSummaryHtml, walkReportHtml } from '../../src/lib/report-html';
import { buildTelemetryCsv, buildTelemetryJson } from '../../src/lib/telemetry-export';
import { recentWalks, walksForPet } from '../../src/lib/walks';
import {
  FACTOR_LABELS,
  formatDateTime,
  formatDuration,
  formatMeasure,
  formatPoseFrames,
  PIPELINE_LABELS,
  SIGNAL_LABELS,
} from '../../src/lib/format';
import type { Analysis, Pet } from '../../src/lib/types';
import { spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

function formatStrideCounts(left: number | null | undefined, right: number | null | undefined) {
  const values = [left, right].filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!values.length) return 'Not measured';
  return [...values].sort((a, b) => a - b).join(' and ');
}

function Measure({ label, value }: { label: string; value: string }) {
  const colors = useColors();
  return (
    <View style={[styles.measure, { backgroundColor: colors.background }]}>
      <Text style={[styles.measureLabel, { color: colors.muted }]}>{label}</Text>
      <Text style={[styles.measureValue, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

const COCO_EDGES = [
  ['left_ankle', 'left_knee'],
  ['left_knee', 'left_hip'],
  ['right_ankle', 'right_knee'],
  ['right_knee', 'right_hip'],
  ['left_hip', 'right_hip'],
  ['left_shoulder', 'left_hip'],
  ['right_shoulder', 'right_hip'],
  ['left_shoulder', 'right_shoulder'],
  ['left_shoulder', 'left_elbow'],
  ['right_shoulder', 'right_elbow'],
  ['left_elbow', 'left_wrist'],
  ['right_elbow', 'right_wrist'],
  ['left_eye', 'right_eye'],
  ['nose', 'left_eye'],
  ['nose', 'right_eye'],
  ['left_eye', 'left_ear'],
  ['right_eye', 'right_ear'],
  ['left_ear', 'left_shoulder'],
  ['right_ear', 'right_shoulder'],
] as const;

const POSE_CONNECTIONS = [
  ['left_shoulder', 'right_shoulder'],
  ['left_shoulder', 'left_elbow'],
  ['left_elbow', 'left_wrist'],
  ['right_shoulder', 'right_elbow'],
  ['right_elbow', 'right_wrist'],
  ['left_shoulder', 'left_hip'],
  ['right_shoulder', 'right_hip'],
  ['left_hip', 'right_hip'],
  ['left_hip', 'left_knee'],
  ['left_knee', 'left_ankle'],
  ['right_hip', 'right_knee'],
  ['right_knee', 'right_ankle'],
] as const;

const WEIGHT_LABELS: Record<string, string> = {
  movementConsistency: 'Movement Consistency',
  symmetry: 'Stride Symmetry',
  mobility: 'Mobility',
  activity: 'Activity',
  historicalChange: 'Baseline Change',
};

type PosePoint = NonNullable<NonNullable<Analysis['measurements']>['poseKeypoints']>[number];

function isPosePoint(point: unknown): point is PosePoint {
  if (!point || typeof point !== 'object') return false;
  const candidate = point as Record<string, unknown>;
  return (
    typeof candidate.name === 'string' &&
    typeof candidate.x === 'number' && Number.isFinite(candidate.x) && candidate.x >= 0 && candidate.x <= 1 &&
    typeof candidate.y === 'number' && Number.isFinite(candidate.y) && candidate.y >= 0 && candidate.y <= 1 &&
    typeof candidate.confidence === 'number' && Number.isFinite(candidate.confidence) &&
    candidate.confidence >= 0 && candidate.confidence <= 1
  );
}

function PipelineVisual({ analysis }: { analysis: Analysis }) {
  const colors = useColors();
  const measurements = analysis.measurements;
  const [selectedPoint, setSelectedPoint] = useState<PosePoint | null>(null);
  const rawPoints = measurements?.poseKeypoints;
  const points = Array.isArray(rawPoints) ? rawPoints.filter(isPosePoint) : [];
  const lowConfidence =
    analysis.lowConfidence === true ||
    (typeof analysis.modelConfidence === 'number' && analysis.modelConfidence < 0.3) ||
    (typeof measurements?.meanKeypointConfidence === 'number' && measurements.meanKeypointConfidence < 0.3);

  if (points.length === 0 || lowConfidence) {
    const coverage = measurements?.motionCoverage;
    const percent = typeof coverage === 'number' && Number.isFinite(coverage)
      ? Math.max(0, Math.min(100, coverage * 100))
      : null;
    const reason = lowConfidence
      ? 'Pose confidence was too low to show reliable keypoints, so frame-motion coverage is shown instead.'
      : analysis.pipeline === 'opencv-motion'
        ? 'This fallback measures picture motion and does not produce pose landmarks.'
        : 'No usable pose keypoints were returned, so frame-motion coverage is shown instead.';
    return (
      <Card>
        <Eyebrow>Computer vision activity</Eyebrow>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Frame Motion Coverage</Text>
        <Muted>Share of analyzed frame pairs with visible picture motion. {reason}</Muted>
        <View style={styles.coverageHeader}>
          <Muted>Frames with movement</Muted>
          <Text style={[styles.coverageValue, { color: colors.text }]}>{percent === null ? 'Not measured' : `${percent.toFixed(0)}%`}</Text>
        </View>
        <View
          accessibilityRole="progressbar"
          accessibilityLabel="Frame Motion Coverage"
          accessibilityValue={percent === null ? undefined : { min: 0, max: 100, now: percent }}
          style={[styles.coverageTrack, { backgroundColor: colors.track }]}
        >
          <View style={[styles.coverageFill, { width: `${percent ?? 0}%`, backgroundColor: colors.accent }]} />
        </View>
      </Card>
    );
  }

  const byName = new Map(points.map((point) => [point.name, point]));
  const cocoNamed = points.some((point) => point.name === 'right_ear' || point.name === 'left_wrist');
  const connections = cocoNamed ? COCO_EDGES : POSE_CONNECTIONS;
  const isCocoPose = analysis.pipeline === 'coco-pose' || analysis.pipeline === 'dog-pose';
  const title = isCocoPose ? 'COCO-17 output summary' : analysis.pipeline === 'movenet' ? 'MoveNet landmark summary' : 'Saved landmark summary';
  const caption = isCocoPose
    ? 'Mean positions from confident frames. These are COCO-17 human joint labels applied inside a detected dog box, not validated canine anatomical landmarks. The head has no neck or tail-base point, so stride length and left/right gait symmetry are not measured.'
    : 'Mean normalized COCO-17 landmark positions from confident frames; canine anatomical interpretation is unvalidated.';
  return (
    <Card>
      <Eyebrow>Computer vision activity</Eyebrow>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>{title}</Text>
      <Muted>{caption}</Muted>
      {points.length ? (
        <>
          <View style={styles.poseCanvas}>
            <Svg width="100%" height="100%" viewBox="0 0 100 70" preserveAspectRatio="none" accessibilityRole="image">
              {connections.map(([from, to]) => {
                const start = byName.get(from);
                const end = byName.get(to);
                return start && end ? (
                  <Line
                    key={`${from}-${to}`}
                    x1={start.x * 100}
                    y1={start.y * 70}
                    x2={end.x * 100}
                    y2={end.y * 70}
                    stroke={colors.good}
                    strokeWidth="1.2"
                  />
                ) : null;
              })}
              {points.map((point) => (
                <Circle
                  key={point.name}
                  cx={point.x * 100}
                  cy={point.y * 70}
                  r="2.2"
                  fill={colors.accent}
                  stroke="#fff4e7"
                  strokeWidth="0.6"
                  accessible
                  accessibilityLabel={`${point.name.replaceAll('_', ' ')} keypoint, ${Math.round(point.confidence * 100)}% confidence`}
                  onPress={() => setSelectedPoint(point)}
                />
              ))}
            </Svg>
          </View>
          <Muted>
            {selectedPoint
              ? `${selectedPoint.name.replaceAll('_', ' ')} · ${Math.round(selectedPoint.confidence * 100)}% confidence`
              : 'Tap a keypoint to inspect its confidence.'}
            {' · '}{points.length} landmarks averaged across {formatPoseFrames(analysis.framesUsed, analysis.framesTotal)}.
          </Muted>
        </>
      ) : (
        <Muted>No confident keypoints were available to visualize for this walk.</Muted>
      )}
    </Card>
  );
}

/** Plain-text version of the record for the share sheet. */
function buildShareText(analysis: Analysis, pet?: Pet) {
  const lines = [
    `PetLens AI observation for ${pet?.name ?? 'pet'} — ${formatDateTime(analysis.createdAt)}`,
    analysis.source ? `Video source: ${analysis.source}` : '',
    analysis.license ? `License or permission: ${analysis.license}` : '',
    analysis.sourceUrl ? `Source link: ${analysis.sourceUrl}` : '',
    `Overall wellness indicator: ${formatMeasure(analysis.overallScore, '/100', 0)}`,
    ...FACTOR_LABELS.map((factor) => `${factor.label}: ${formatMeasure(analysis.factors[factor.key], '/100', 0)}`),
    '',
    analysis.observation,
    '',
    `Measured with: ${PIPELINE_LABELS[analysis.pipeline] ?? analysis.pipeline} (${SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality})`,
    `Limitations: ${analysis.limitations}`,
    '',
    SAFETY_DISCLAIMER,
  ];
  return lines.join('\n');
}

export default function WalkDetailScreen() {
  const colors = useColors();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { pets, analyses, deleteAnalysis } = useLocalData();
  const router = useRouter();

  const analysis = analyses.find((item) => item.id === id);
  const pet = analysis ? pets.find((item) => item.id === analysis.petId) : undefined;

  if (!analysis) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Card>
          <EmptyState icon="search-outline" title="Walk not found" body="This observation may have been deleted." />
          <Button label="Back to history" variant="secondary" onPress={() => router.replace('/history')} />
        </Card>
      </ScrollView>
    );
  }

  const measurements = analysis.measurements;
  const walk = analysis;

  async function savePdf() {
    const outcome = await sharePdf(walkReportHtml(walk, pets), 'Walk report');
    if (!outcome.ok) Alert.alert('Report not shared', outcome.message);
  }

  async function saveVetSummary() {
    const rows = recentWalks(walksForPet(analyses, walk.petId));
    const outcome = await sharePdf(vetSummaryHtml(rows, pets), 'Veterinarian summary');
    if (!outcome.ok) Alert.alert('Summary not shared', outcome.message);
  }

  async function shareTelemetry(format: 'csv' | 'json') {
    try {
      const message = format === 'csv'
        ? buildTelemetryCsv(walk, pet)
        : JSON.stringify(buildTelemetryJson(walk, pet), null, 2);
      await Share.share({
        title: `PetLens raw telemetry (${format.toUpperCase()})`,
        message,
      });
    } catch {
      Alert.alert('Telemetry not shared', 'The raw values could not be opened in the share sheet.');
    }
  }

  function confirmDelete() {
    Alert.alert('Delete this walk?', 'The saved measurements and notes will be removed from this phone.', [
      { text: 'Keep', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          deleteAnalysis(analysis!.id);
          router.replace('/history');
        },
      },
    ]);
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Card>
        <View style={styles.header}>
          <ScoreBadge score={analysis.overallScore} />
          <View style={{ flex: 1, gap: 6 }}>
            <Eyebrow>Overall wellness indicator</Eyebrow>
            <Text style={[styles.petName, { color: colors.text }]}>{pet?.name ?? 'Pet'}</Text>
            <Muted>
              {formatDateTime(analysis.createdAt)} · {formatDuration(analysis.durationSeconds)}
            </Muted>
          </View>
        </View>
        <View style={styles.tags}>
          <Tag>{SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality}</Tag>
          <Tag>{PIPELINE_LABELS[analysis.pipeline] ?? analysis.pipeline}</Tag>
          {analysis.usedLlm && <Tag tone="accent">Model-written summary</Tag>}
        </View>
        {analysis.signalNote ? <Muted>{analysis.signalNote}</Muted> : null}
        {analysis.modelInfo ? (
          <Muted>
            Measured on the server with {analysis.modelInfo.modelName}, version {analysis.modelInfo.modelVersion}.
          </Muted>
        ) : null}
        {(analysis.source || analysis.license || analysis.sourceUrl) && (
          <View style={{ gap: 4 }}>
            <Eyebrow>Video attribution</Eyebrow>
            {analysis.source ? <Muted>Source: {analysis.source}</Muted> : null}
            {analysis.license ? <Muted>License or permission: {analysis.license}</Muted> : null}
            {analysis.sourceUrl ? <Muted>Source link: {analysis.sourceUrl}</Muted> : null}
          </View>
        )}
        {aiUseResultLines(analysis.aiUse).map((line) => (
          <Muted key={line}>{line}</Muted>
        ))}
      </Card>

      {analysis.lowConfidence && (
        <Note tone="warn" title="Low confidence — try a clearer clip">
          The pose model could not see the body clearly enough to measure the legs. Film from the side with the whole
          body in frame. Values that were not measured are shown as “Not measured”, not as zero.
        </Note>
      )}

      {analysis.qualityNotes && analysis.qualityNotes.length > 0 && (
        <Note tone="info" title="Before the next clip">
          {analysis.qualityNotes.join(' ')}
        </Note>
      )}

      {analysis.concerningChange && (
        <Note tone="warn" title="Worth asking a veterinarian">
          The measured change from the previous walk was large enough to mention to a vet. This is a prompt to ask a
          professional, not a diagnosis. {EMERGENCY_NOTE}
        </Note>
      )}

      <Card>
        <Eyebrow>What we noticed</Eyebrow>
        <Text style={[styles.observation, { color: colors.text }]}>{analysis.observation}</Text>
      </Card>

      <PipelineVisual analysis={analysis} />
      <ScientificCharts measurements={analysis.measurements} />

      <Card>
        <Eyebrow>Factors</Eyebrow>
        <Muted>Each factor is scored 0-100 from the measurements below. "Not scored" means there was not enough signal.</Muted>
        {FACTOR_LABELS.map((factor) => (
          <FactorRow key={factor.key} label={factor.label} help={factor.help} score={analysis.factors[factor.key]} />
        ))}
        {analysis.weightsUsed && Object.keys(analysis.weightsUsed).length > 0 && (
          <Muted>
            Weights used:{' '}
            {Object.entries(analysis.weightsUsed)
              .map(([name, weight]) => `${WEIGHT_LABELS[name] ?? name} (${Math.round((weight ?? 0) * 100)}%)`)
              .join(' • ')}
          </Muted>
        )}
      </Card>

      {measurements && (
        <Card>
          <Eyebrow>Raw measurements</Eyebrow>
          <Muted>Exactly what the pipeline measured, with no interpretation.</Muted>
          <View style={styles.measureGrid}>
            <Measure label="Frames read" value={formatMeasure(measurements.frameCount, '', 0)} />
            <Measure label="Clip length" value={formatMeasure(measurements.durationSeconds, ' s', 1)} />
            <Measure label="Mean frame motion" value={formatMeasure(measurements.motionMean)} />
            <Measure label="Motion variation" value={formatMeasure(measurements.motionStd)} />
            <Measure
              label="Frame Motion Coverage"
              value={formatMeasure(
                typeof measurements.motionCoverage === 'number' ? measurements.motionCoverage * 100 : undefined,
                '%',
                0,
              )}
            />
            <Measure label="Front strides" value={formatStrideCounts(measurements.strides?.frontLeft?.strideCount, measurements.strides?.frontRight?.strideCount)} />
            <Measure label="Rear strides" value={formatStrideCounts(measurements.strides?.rearLeft?.strideCount, measurements.strides?.rearRight?.strideCount)} />
            <Measure label="Front symmetry" value={formatMeasure(measurements.limbSymmetry?.front)} />
            <Measure label="Rear symmetry" value={formatMeasure(measurements.limbSymmetry?.rear)} />
            <Measure label="Front stride length" value={formatMeasure(measurements.strideLengthBodyLengths?.front, ' body lengths')} />
            <Measure label="Rear stride length" value={formatMeasure(measurements.strideLengthBodyLengths?.rear, ' body lengths')} />
            <Measure label="Cadence" value={formatMeasure(measurements.cadenceStridesPerMinute, ' / min', 1)} />
            <Measure label="Stride regularity" value={formatMeasure(measurements.strideTimeCv)} />
            <Measure label="Head vertical asymmetry" value={formatMeasure(measurements.headBobAsymmetry)} />
            <Measure label="Pelvis vertical asymmetry" value={formatMeasure(measurements.pelvisAsymmetry)} />
            <Measure label="Dog in frame" value={formatMeasure(typeof measurements.subject?.dogFramesShare === 'number' ? measurements.subject.dogFramesShare * 100 : undefined, '%', 0)} />
            <Measure label="Stride symmetry" value={formatMeasure(measurements.strideSymmetry)} />
            <Measure label="Asymmetry" value={formatMeasure(measurements.asymmetryPercent, '%', 1)} />
            <Measure label="Hip stability" value={formatMeasure(measurements.hipStability)} />
            <Measure label="Left ankle motion" value={formatMeasure(measurements.leftAnkleMotion)} />
            <Measure label="Right ankle motion" value={formatMeasure(measurements.rightAnkleMotion)} />
            <Measure label="Keypoint confidence" value={formatMeasure(measurements.meanKeypointConfidence)} />
            <Measure label="Confident frames" value={formatPoseFrames(analysis.framesUsed, analysis.framesTotal)} />
            <Measure label="Symmetry reliable" value={typeof measurements.symmetryReliable === 'boolean' ? (measurements.symmetryReliable ? 'Yes' : 'No') : 'Not measured'} />
          </View>
          {(measurements.notMeasuredReasons ?? []).map((reason) => (
            <Muted key={reason}>Not measured: {reason}</Muted>
          ))}
        </Card>
      )}

      <Card>
        <Eyebrow>Limitations</Eyebrow>
        <Text style={[styles.body, { color: colors.text }]}>{analysis.limitations}</Text>
      </Card>

      <Card>
        <Eyebrow>Export options</Eyebrow>
        <Muted>Share the saved observation or raw measured values from this phone.</Muted>
        <Button label="Export raw telemetry (CSV)" icon="download-outline" variant="secondary" onPress={() => void shareTelemetry('csv')} />
        <Button label="Export raw telemetry (JSON)" icon="download-outline" variant="secondary" onPress={() => void shareTelemetry('json')} />
      </Card>

      <View style={styles.actions}>
        <Button
          label="Share summary"
          icon="share-outline"
          variant="secondary"
          onPress={() => void Share.share({ message: buildShareText(analysis, pet) })}
          style={{ flex: 1 }}
        />
        <Button label="PDF report" icon="document-outline" variant="secondary" onPress={() => void savePdf()} style={{ flex: 1 }} />
        <Button label="Delete" icon="trash-outline" variant="danger" onPress={confirmDelete} />
      </View>
      <Button label="Movement report for recent walks" variant="secondary" onPress={() => void saveVetSummary()} />
      <Button label="Formulas and scientific evidence" variant="secondary" onPress={() => router.push('/methodology')} />

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  petName: { fontSize: 22, fontWeight: '700' },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.xs },
  observation: { fontSize: 16, lineHeight: 24 },
  sectionTitle: { fontSize: 18, fontWeight: '700' },
  coverageHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.md },
  coverageValue: { fontSize: 14, fontWeight: '700' },
  coverageTrack: { height: 10, borderRadius: 5, overflow: 'hidden', marginTop: spacing.xs },
  coverageFill: { height: '100%', borderRadius: 5 },
  poseCanvas: { width: '100%', aspectRatio: 10 / 7, borderRadius: 12, overflow: 'hidden', backgroundColor: '#263b35', marginVertical: spacing.md },
  body: { fontSize: 14, lineHeight: 21 },
  measureGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.xs },
  measure: {
    width: '48%',
    borderRadius: 10,
    padding: spacing.md,
    gap: 2,
  },
  measureLabel: { fontSize: 11, fontWeight: '600' },
  measureValue: { fontSize: 15, fontWeight: '700' },
  actions: { flexDirection: 'row', gap: spacing.sm },
});
