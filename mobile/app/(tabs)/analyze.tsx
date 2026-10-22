/**
 * Record or choose a walking clip, send it to the analysis API, save the result.
 *
 * The screen owns the upload state machine only. Clip checks live in lib/api.ts
 * and every measurement comes back from the server; nothing is computed here.
 */

import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { DisclaimerFooter } from '../../src/components/disclaimer-footer';
import { ScoreBadge } from '../../src/components/score';
import { Button, Card, Chip, EmptyState, Eyebrow, Muted, Note, Tag } from '../../src/components/ui';
import { useConnection } from '../../src/hooks/use-connection';
import { useLocalData } from '../../src/hooks/use-local-data';
import { usePreferences } from '../../src/hooks/use-preferences';
import {
  checkClip,
  describeAnalysisError,
  MAX_CLIP_SECONDS,
  MAX_UPLOAD_MB,
  MISSING_API_URL_MESSAGE,
  requestAnalysis,
  resolveApiUrl,
  type ClipAsset,
} from '../../src/lib/api';
import { aiUseResultLines } from '../../src/lib/ai-use';
import { PRIVACY_LINE } from '../../src/lib/disclaimers';
import { formatBytes, formatDuration, SIGNAL_LABELS } from '../../src/lib/format';
import { findBaseline, toAnalysisRecord } from '../../src/lib/storage';
import type { Analysis } from '../../src/lib/types';
import { radius, spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

type Phase = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

const FILMING_GUIDE = [
  'Side angle, so the legs are visible',
  'Flat ground',
  'A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to 120 seconds.',
  'Whole body in frame',
  'Good light',
];

/** Map what the picker returns onto the fields the API client needs. */
function toClipAsset(asset: ImagePicker.ImagePickerAsset): ClipAsset {
  const name = asset.fileName?.trim() || `walk-${Date.now()}.mp4`;
  return {
    uri: asset.uri,
    name,
    mimeType: asset.mimeType || (name.toLowerCase().endsWith('.mov') ? 'video/quicktime' : 'video/mp4'),
    sizeBytes: typeof asset.fileSize === 'number' ? asset.fileSize : null,
    durationSeconds: typeof asset.duration === 'number' && asset.duration > 0 ? asset.duration / 1000 : null,
  };
}

export default function AnalyzeScreen() {
  const colors = useColors();
  const { loading, pets, analyses, addAnalysis } = useLocalData();
  const { preferences } = usePreferences();
  const { state: connection, retry: retryConnection } = useConnection(true);
  const router = useRouter();
  const params = useLocalSearchParams<{ petId?: string }>();

  const [petId, setPetId] = useState<string | null>(params.petId ?? pets[0]?.id ?? null);
  const [clip, setClip] = useState<ClipAsset | null>(null);
  const [clipProblem, setClipProblem] = useState<string | null>(null);
  const [framingReady, setFramingReady] = useState(false);
  const [phase, setPhase] = useState<Phase>('idle');
  const [uploadFraction, setUploadFraction] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saved, setSaved] = useState<Analysis | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Follow the pet the user came from (Home → "Record a walk").
  useEffect(() => {
    if (params.petId) setPetId(params.petId);
  }, [params.petId]);

  // If the chosen pet was deleted, fall back to the first one.
  useEffect(() => {
    if (petId && !pets.some((pet) => pet.id === petId)) setPetId(pets[0]?.id ?? null);
  }, [pets, petId]);

  // Simple elapsed-seconds counter while work is in flight.
  const busy = phase === 'uploading' || phase === 'analyzing';
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  // Leaving the screen cancels an in-flight request.
  useEffect(() => () => abortRef.current?.abort(), []);

  const pet = useMemo(() => pets.find((item) => item.id === petId), [pets, petId]);

  async function pickClip(source: 'library' | 'camera') {
    setErrorMessage(null);
    setSaved(null);
    setPhase('idle');

    try {
      if (source === 'camera') {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          setClipProblem('Camera access is needed to record a walk. You can still choose a saved video.');
          return;
        }
      }

      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ['videos'],
        allowsEditing: false,
        videoMaxDuration: 60,
        quality: 0.7,
      };
      const result =
        source === 'camera'
          ? await ImagePicker.launchCameraAsync(options)
          : await ImagePicker.launchImageLibraryAsync(options);

      if (result.canceled || !result.assets[0]) return;

      const chosen = toClipAsset(result.assets[0]);
      const problem = checkClip(chosen);
      setClipProblem(problem?.message ?? null);
      setClip(problem ? null : chosen);
    } catch {
      setClipProblem('The video could not be opened. Please try a different clip.');
    }
  }

  async function run() {
    if (!preferences.consentAccepted) {
      router.push('/onboarding');
      return;
    }
    if (!clip || !pet) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('uploading');
    setUploadFraction(0);
    setElapsed(0);
    setErrorMessage(null);
    setSaved(null);

    try {
      const baseUrl = await resolveApiUrl();
      if (!baseUrl) {
        setErrorMessage(MISSING_API_URL_MESSAGE);
        setPhase('error');
        return;
      }
      const baseline = findBaseline(analyses, pet.id);

      const result = await requestAnalysis({
        baseUrl,
        clip,
        petName: pet.name,
        previousOverall: baseline?.overallScore,
        previousPipeline: baseline?.pipeline,
        signal: controller.signal,
        onUploadProgress: (fraction) => {
          setUploadFraction(fraction);
          if (fraction >= 1) setPhase('analyzing');
        },
      });

      const record = toAnalysisRecord(result, {
        petId: pet.id,
        fileName: clip.name,
        durationSeconds: clip.durationSeconds ?? 0,
      });
      addAnalysis(record);
      setSaved(record);
      setPhase('done');
      setClip(null);
    } catch (error) {
      setErrorMessage(describeAnalysisError(error));
      setPhase('error');
    } finally {
      abortRef.current = null;
    }
  }

  function cancel() {
    abortRef.current?.abort();
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <Muted>Loading pets…</Muted>
      </View>
    );
  }

  if (pets.length === 0) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <ConnectionChip state={connection} onRetry={retryConnection} />
        <Card>
          <EmptyState icon="paw-outline" title="Add a pet first" body="Walks are saved against a pet profile so they can be compared over time." />
          <Button label="Create a pet profile" icon="add" onPress={() => router.push('/pet/new')} />
        </Card>
        <Muted>{PRIVACY_LINE}</Muted>
        <DisclaimerFooter />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <ConnectionChip state={connection} onRetry={retryConnection} />
      {!preferences.consentAccepted && (
        <Note tone="info" title="Before the first analysis">
          Read the three short notes and acknowledge that this is a wellness note, not a diagnosis.
        </Note>
      )}
      <Card>
        <Eyebrow>How to film</Eyebrow>
        {FILMING_GUIDE.map((item) => (
          <Muted key={item}>• {item}</Muted>
        ))}
      </Card>
      <Card>
        <Eyebrow>1 · Which pet?</Eyebrow>
        <View style={styles.chips}>
          {pets.map((item) => (
            <Chip key={item.id} label={item.name} selected={item.id === petId} onPress={() => setPetId(item.id)} />
          ))}
        </View>
      </Card>

      <Card>
        <Eyebrow>2 · The walk</Eyebrow>
        <View style={[styles.alignmentGuide, { backgroundColor: colors.track, borderColor: colors.border }]}>
          <View style={styles.alignmentHeader}>
            <View style={styles.alignmentTitleGroup}>
              <Ionicons name="scan-outline" size={17} color={colors.accent} />
              <Text style={[styles.alignmentTitle, { color: colors.text }]}>Pre-Filming Alignment Guide</Text>
            </View>
            <Text style={[styles.alignmentStep, { color: colors.muted }]}>01 / 03</Text>
          </View>

          <View style={styles.viewfinder}>
            <View style={styles.targetFrame}>
              <View style={styles.frameLabel}>
                <View style={styles.liveDot} />
                <Text style={styles.frameLabelText}>SIDE VIEW</Text>
              </View>
              <Ionicons name="paw" size={46} color="#f5e8d7" />
              <View style={styles.groundLine} />
              <View style={styles.targetCornerTopLeft} />
              <View style={styles.targetCornerTopRight} />
              <View style={styles.targetCornerBottomLeft} />
              <View style={styles.targetCornerBottomRight} />
            </View>
          </View>

          <View style={styles.guidelineList}>
            <View style={styles.guidelineRow}>
              <Ionicons name="compass-outline" size={16} color={colors.accent} />
              <Text style={[styles.guidelineText, { color: colors.text }]}>Film directly from the side (90° angle)</Text>
            </View>
            <View style={styles.guidelineRow}>
              <Ionicons name="sunny-outline" size={16} color={colors.accent} />
              <Text style={[styles.guidelineText, { color: colors.text }]}>Ensure flat ground and good lighting</Text>
            </View>
            <View style={styles.guidelineRow}>
              <Ionicons name="scan-outline" size={16} color={colors.accent} />
              <Text style={[styles.guidelineText, { color: colors.text }]}>Keep pet's full body inside the viewport</Text>
            </View>
          </View>

          <Pressable
            accessibilityRole="switch"
            accessibilityState={{ checked: framingReady }}
            onPress={() => setFramingReady((ready) => !ready)}
            style={styles.readyToggle}
          >
            <View style={styles.readyTextGroup}>
              <Ionicons name={framingReady ? 'checkmark-circle' : 'ellipse-outline'} size={18} color={framingReady ? colors.good : colors.muted} />
              <Text style={[styles.readyText, { color: colors.text }]}>Framing Ready</Text>
            </View>
            <View style={[styles.toggleTrack, { backgroundColor: framingReady ? colors.good : colors.border }]}>
              <View style={[styles.toggleThumb, framingReady && styles.toggleThumbOn]} />
            </View>
          </Pressable>
        </View>
        <Muted>
          Film from the side while your pet walks in a straight line, in good light. A useful walk is about 5 to 15
          seconds. The server accepts a longer clip, up to {MAX_CLIP_SECONDS} seconds and {MAX_UPLOAD_MB} MB.
        </Muted>
        <View style={styles.row}>
          <Button label="Record" icon="videocam-outline" onPress={() => pickClip('camera')} disabled={busy} style={{ flex: 1 }} />
          <Button label="Choose video" icon="images-outline" variant="secondary" onPress={() => pickClip('library')} disabled={busy} style={{ flex: 1 }} />
        </View>

        {clipProblem && <Note tone="error">{clipProblem}</Note>}

        {clip && (
          <View style={styles.clipMeta}>
            <Text style={[styles.clipName, { color: colors.text }]} numberOfLines={1}>
              {clip.name}
            </Text>
            <Muted>
              {clip.durationSeconds ? formatDuration(clip.durationSeconds) : 'Length unknown'} · {formatBytes(clip.sizeBytes)}
            </Muted>
          </View>
        )}
      </Card>

      <Card>
        <Eyebrow>3 · Analyze</Eyebrow>
        {!busy && !preferences.consentAccepted && (
          <Button label="Read the notes first" onPress={() => router.push('/onboarding')} />
        )}
        {!busy && preferences.consentAccepted && (
          <Button
            label={pet ? `Analyze ${pet.name}'s walk` : 'Analyze walk'}
            icon="analytics-outline"
            onPress={run}
            disabled={!clip || !pet}
          />
        )}

        {busy && (
          <View style={{ gap: spacing.sm }}>
            <Text style={[styles.stage, { color: colors.text }]}>
              {phase === 'uploading' ? `Uploading clip · ${Math.round(uploadFraction * 100)}%` : 'Measuring movement…'}
            </Text>
            <View style={[styles.track, { backgroundColor: colors.track }]} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(uploadFraction * 100) }}>
              <View style={[styles.fill, { width: `${Math.max(3, uploadFraction * 100)}%`, backgroundColor: colors.accent }, phase === 'analyzing' && styles.fillIndeterminate]} />
            </View>
            <Muted>
              {phase === 'analyzing'
                ? `Reading frames and comparing left and right movement. ${elapsed}s so far; short clips usually finish within 10 seconds.`
                : 'Large clips take longer on Wi-Fi. Keep the app open.'}
            </Muted>
            <Button label="Cancel" variant="secondary" onPress={cancel} />
          </View>
        )}

        {phase === 'error' && errorMessage && (
          <Note tone="error" title="Analysis did not finish">
            {errorMessage} {clip ? 'The clip is still selected, so you can try again without choosing it again.' : ''}
          </Note>
        )}
        {phase === 'error' && clip && <Button label="Try again" icon="refresh" onPress={() => void run()} />}

        {phase === 'done' && saved && (
          <View style={{ gap: spacing.md }}>
            <View style={styles.resultRow}>
              <ScoreBadge score={saved.overallScore} />
              <View style={{ flex: 1, gap: 6 }}>
                <Text style={[styles.resultTitle, { color: colors.text }]}>Saved to history</Text>
                <View style={styles.chips}>
                  <Tag>{SIGNAL_LABELS[saved.signalQuality] ?? saved.signalQuality}</Tag>
                  {saved.concerningChange && <Tag tone="warn">Worth asking a vet</Tag>}
                </View>
              </View>
            </View>
            {saved.lowConfidence && (
              <Note tone="warn" title="Low confidence — try a clearer clip">
                Film from the side with the whole body in frame. Limb values that were not measured are not zeros.
              </Note>
            )}
            <Text style={[styles.observation, { color: colors.text }]}>{saved.observation}</Text>
            {aiUseResultLines(saved.aiUse).map((line) => (
              <Muted key={line}>{line}</Muted>
            ))}
            <Button label="See the full breakdown" icon="arrow-forward" onPress={() => router.push({ pathname: '/history/[id]', params: { id: saved.id } })} />
          </View>
        )}
      </Card>

      {preferences.demoMode && (
        <Card>
          <Eyebrow>Demo</Eyebrow>
          <Muted>Sample data stays on this screen. It is not saved to history and does not appear in trends.</Muted>
          <Button label="View sample result" variant="secondary" onPress={() => router.push('/demo')} />
        </Card>
      )}

      <Muted>{PRIVACY_LINE}</Muted>
      <DisclaimerFooter />
    </ScrollView>
  );
}

function ConnectionChip({
  state,
  onRetry,
}: {
  state: { kind: 'checking' } | { kind: 'online'; url: string } | { kind: 'offline'; message: string };
  onRetry: () => void;
}) {
  if (state.kind === 'checking') {
    return (
      <Note tone="info" title="Checking the server">
        Looking for the analysis server.
      </Note>
    );
  }
  if (state.kind === 'online') {
    return (
      <Note tone="info" title="Connected">
        The analysis server answered.
      </Note>
    );
  }
  return (
    <Note tone="error" title="Offline">
      {state.message} You can keep the clip you already chose and try again.
      <Text onPress={onRetry} accessibilityRole="button" style={{ fontWeight: '700' }}>
        {' '}
        Retry
      </Text>
    </Note>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  alignmentGuide: { borderWidth: 1, borderRadius: radius.md, padding: spacing.md, gap: spacing.md },
  alignmentHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  alignmentTitleGroup: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flex: 1 },
  alignmentTitle: { fontSize: 14, fontWeight: '700', flexShrink: 1 },
  alignmentStep: { fontSize: 10, fontWeight: '700', letterSpacing: 0.8 },
  viewfinder: { height: 150, borderRadius: radius.sm, backgroundColor: '#263b35', padding: spacing.md },
  targetFrame: { flex: 1, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderStyle: 'dashed', borderColor: 'rgba(245, 232, 215, 0.72)', borderRadius: radius.sm, overflow: 'hidden' },
  frameLabel: { position: 'absolute', top: spacing.sm, left: spacing.sm, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(20, 31, 28, 0.72)', borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 5 },
  liveDot: { width: 6, height: 6, borderRadius: radius.pill, backgroundColor: '#e8a47b' },
  frameLabelText: { color: '#f5e8d7', fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  groundLine: { position: 'absolute', left: spacing.md, right: spacing.md, bottom: 27, borderBottomWidth: 1, borderColor: 'rgba(245, 232, 215, 0.48)' },
  targetCornerTopLeft: { position: 'absolute', top: -1, left: -1, width: 13, height: 13, borderTopWidth: 2, borderLeftWidth: 2, borderColor: '#f5e8d7' },
  targetCornerTopRight: { position: 'absolute', top: -1, right: -1, width: 13, height: 13, borderTopWidth: 2, borderRightWidth: 2, borderColor: '#f5e8d7' },
  targetCornerBottomLeft: { position: 'absolute', bottom: -1, left: -1, width: 13, height: 13, borderBottomWidth: 2, borderLeftWidth: 2, borderColor: '#f5e8d7' },
  targetCornerBottomRight: { position: 'absolute', bottom: -1, right: -1, width: 13, height: 13, borderBottomWidth: 2, borderRightWidth: 2, borderColor: '#f5e8d7' },
  guidelineList: { gap: spacing.sm },
  guidelineRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  guidelineText: { flex: 1, fontSize: 12, lineHeight: 18 },
  readyToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderTopWidth: 1, borderColor: 'rgba(122, 111, 102, 0.18)', paddingTop: spacing.md, minHeight: 40 },
  readyTextGroup: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  readyText: { fontSize: 13, fontWeight: '700' },
  toggleTrack: { width: 40, height: 23, borderRadius: radius.pill, justifyContent: 'center', paddingHorizontal: 3 },
  toggleThumb: { width: 17, height: 17, borderRadius: radius.pill, backgroundColor: '#fff' },
  toggleThumbOn: { alignSelf: 'flex-end' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  clipMeta: { marginTop: spacing.xs, gap: 2 },
  clipName: { fontWeight: '600', fontSize: 14 },
  stage: { fontWeight: '700', fontSize: 15 },
  track: { height: 8, borderRadius: radius.pill, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
  fillIndeterminate: { opacity: 0.6 },
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  resultTitle: { fontSize: 18, fontWeight: '700' },
  observation: { fontSize: 15, lineHeight: 22 },
});
