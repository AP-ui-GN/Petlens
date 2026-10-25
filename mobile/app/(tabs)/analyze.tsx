/** Handles clip selection, analysis requests, and the saved-result state. */

import * as ImagePicker from 'expo-image-picker';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { ConnectionStatus } from '../../src/components/analysis/connection-status';
import { AnalysisStepper } from '../../src/components/analysis/analysis-stepper';
import { VideoUploadCard } from '../../src/components/analysis/video-upload-card';
import { ScoreBadge } from '../../src/components/score';
import { Button, Card, EmptyState, Eyebrow, Muted, Note, Tag } from '../../src/components/ui';
import { useConnection } from '../../src/hooks/use-connection';
import { useLocalData } from '../../src/hooks/use-local-data';
import { usePreferences } from '../../src/hooks/use-preferences';
import {
  checkClip,
  describeAnalysisError,
  isClipReadable,
  MISSING_API_URL_MESSAGE,
  requestAnalysis,
  resolveApiUrl,
  type ClipAsset,
} from '../../src/lib/api';
import { aiUseResultLines } from '../../src/lib/ai-use';
import { attemptAnalysis, createSubmissionGate } from '../../src/lib/analysis-attempt';
import { PRIVACY_LINE } from '../../src/lib/disclaimers';
import { formatBytes, formatDuration, SIGNAL_LABELS } from '../../src/lib/format';
import { stashSelection, takeSelection } from '../../src/lib/pending-selection';
import { findBaseline, toAnalysisRecord } from '../../src/lib/storage';
import type { Analysis } from '../../src/lib/types';
import { fontFamily, radius, spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

type Phase = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

// The picker doesn't always include every detail, so fill in upload-safe defaults here.
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
  const [phase, setPhase] = useState<Phase>('idle');
  const [uploadFraction, setUploadFraction] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [source, setSource] = useState('');
  const [license, setLicense] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [specialistLocation, setSpecialistLocation] = useState('');
  const [specialistError, setSpecialistError] = useState('');
  const [saved, setSaved] = useState<Analysis | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const gate = useRef(createSubmissionGate());

  // Bring back a clip that was set aside while the consent notes were open.
  useFocusEffect(
    useCallback(() => {
      const restored = takeSelection();
      if (!restored) return;
      setClip(restored.clip);
      if (restored.petId) setPetId(restored.petId);
      setSource(restored.source);
      setLicense(restored.license);
      setSourceUrl(restored.sourceUrl);
    }, []),
  );

  // Keep the pet selected on Home when opening this screen from a pet card.
  useEffect(() => {
    if (params.petId) setPetId(params.petId);
  }, [params.petId]);

  // If that pet was removed, select the next available profile.
  useEffect(() => {
    if (petId && !pets.some((pet) => pet.id === petId)) setPetId(pets[0]?.id ?? null);
  }, [pets, petId]);

  const busy = phase === 'uploading' || phase === 'analyzing';
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  // Don't keep uploading if the user leaves this screen.
  useEffect(() => () => abortRef.current?.abort(), []);

  const pet = pets.find((item) => item.id === petId);
  const activeStep = busy || phase === 'done' ? 2 : clip ? 1 : 0;

  function searchSpecialists(query: string) {
    const place = query.trim();
    if (!place) {
      setSpecialistError('Enter a ZIP code or city to search nearby.');
      return;
    }
    setSpecialistError('');
    const url = new URL('https://www.google.com/maps/search/');
    url.searchParams.set('api', '1');
    url.searchParams.set('query', `Veterinary Physical Therapy near ${place}`);
    void Linking.openURL(url.toString()).catch((error: unknown) => {
      console.error('Could not open Google Maps search for veterinary physical therapy.', error);
      setSpecialistError('Could not open Maps. Try searching for veterinary physical therapy in your maps app.');
    });
  }

  async function pickClip(source: 'library' | 'camera') {
    setErrorMessage(null);
    setSaved(null);
    setPhase('idle');
    setSource('');
    setLicense('');
    setSourceUrl('');

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
      if (clip) stashSelection({ clip, petId, source, license, sourceUrl });
      router.push('/onboarding');
      return;
    }
    if (!clip || !pet) return;
    if (!gate.current.tryEnter()) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('uploading');
    setUploadFraction(0);
    setElapsed(0);
    setErrorMessage(null);
    setSaved(null);

    try {
      const baseline = findBaseline(analyses, pet.id);
      const outcome = await attemptAnalysis(
        clip,
        {
          isReadable: isClipReadable,
          resolveUrl: resolveApiUrl,
          request: (baseUrl, chosen, onUploadProgress) =>
            requestAnalysis({
              baseUrl,
              clip: chosen,
              petName: pet.name,
              previousOverall: baseline?.overallScore,
              previousPipeline: baseline?.pipeline,
              signal: controller.signal,
              onUploadProgress,
            }),
          describeError: describeAnalysisError,
        },
        (fraction) => {
          setUploadFraction(fraction);
          if (fraction >= 1) setPhase('analyzing');
        },
      );

      if (outcome.kind === 'unreadable') {
        setClip(null);
        setClipProblem('That video can no longer be opened. Please choose it again.');
        setPhase('idle');
      } else if (outcome.kind === 'no-server') {
        setErrorMessage(MISSING_API_URL_MESSAGE);
        setPhase('error');
      } else if (outcome.kind === 'failed') {
        setErrorMessage(outcome.message);
        setPhase('error');
      } else {
        const record = toAnalysisRecord(outcome.result, {
          petId: pet.id,
          fileName: clip.name,
          durationSeconds: clip.durationSeconds ?? 0,
          source,
          license,
          sourceUrl,
        });
        addAnalysis(record);
        setSaved(record);
        setPhase('done');
        setClip(null);
      }
    } finally {
      abortRef.current = null;
      gate.current.leave();
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
        <ConnectionStatus state={connection} onRetry={retryConnection} />
        <Card>
          <EmptyState icon="paw-outline" title="Add a pet first" body="Walks are saved against a pet profile so they can be compared over time." />
          <Button label="Create a pet profile" icon="add" onPress={() => router.push('/pet/new')} />
        </Card>
        <Card>
          <Eyebrow>Sample</Eyebrow>
          <Muted>Explore an example result. It is sample data, not a real clip analysis, and is not saved to history.</Muted>
          <Button label="Try Sample Dog Walk" variant="secondary" onPress={() => router.push('/demo')} />
        </Card>
        <Muted>{PRIVACY_LINE}</Muted>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <ConnectionStatus state={connection} onRetry={retryConnection} />
      {!preferences.consentAccepted && (
        <Note tone="info" title="Before the first analysis">
          Read the three short notes and acknowledge that this is a wellness note, not a diagnosis.
        </Note>
      )}
      <View style={styles.pageHeading}>
        <Text accessibilityRole="header" style={[styles.pageTitle, { color: colors.text }]}>Analyze how your dog walks</Text>
        <Muted>
          Choose a video of your dog. We’ll look for patterns in your pet’s movement and give you an easy-to-understand observation.
        </Muted>
        <Button label="Replay Guided Tour" icon="help-circle-outline" variant="secondary" onPress={() => router.push('/guided-tour')} style={styles.tourButton} />
      </View>

      <AnalysisStepper activeStep={activeStep} />

      <VideoUploadCard
        pets={pets}
        selectedPetId={petId}
        onSelectPet={setPetId}
        onRecord={() => void pickClip('camera')}
        onChooseVideo={() => void pickClip('library')}
        onTrySample={() => router.push('/demo')}
        disabled={busy}
      />

      {clipProblem && <Note tone="error">{clipProblem}</Note>}

      {clip && (
        <Card>
          <View style={styles.clipMeta}>
            <Text style={[styles.clipName, { color: colors.text }]} numberOfLines={1}>
              {clip.name}
            </Text>
            <Muted>
              {clip.durationSeconds ? formatDuration(clip.durationSeconds) : 'Length unknown'} · {formatBytes(clip.sizeBytes)}
            </Muted>
            <Button
              label="Choose another video"
              icon="refresh"
              variant="secondary"
              onPress={() => void pickClip('library')}
              disabled={busy}
            />
            <View style={[styles.sourceContext, { borderColor: colors.border, backgroundColor: colors.accentSoft }]}>
              <Eyebrow>Optional sharing context</Eyebrow>
              <Muted>
                Add attribution if the clip came from a shared library. Leave these blank for a private local video.
              </Muted>
              <TextInput
                accessibilityLabel="Video source"
                value={source}
                onChangeText={setSource}
                placeholder="Source (for example, personal video)"
                placeholderTextColor={colors.muted}
                style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
              />
              <TextInput
                accessibilityLabel="Video license"
                value={license}
                onChangeText={setLicense}
                placeholder="License or permission"
                placeholderTextColor={colors.muted}
                style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
              />
              <TextInput
                accessibilityLabel="Video source link"
                value={sourceUrl}
                onChangeText={setSourceUrl}
                placeholder="https://…"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
              />
            </View>
          </View>
        </Card>
      )}

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
                ? `Reading video frames. ${elapsed}s elapsed; the measurements depend on the signal available in this clip.`
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
                <View style={styles.resultTags}>
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

      <Card>
        <Eyebrow>Find Care Nearby</Eyebrow>
        <Muted>Search Google Maps for veterinary physical therapy specialists near you.</Muted>
        <TextInput
          accessibilityLabel="ZIP code or city"
          value={specialistLocation}
          onChangeText={setSpecialistLocation}
          onSubmitEditing={() => searchSpecialists(specialistLocation)}
          placeholder="ZIP code or city"
          placeholderTextColor={colors.muted}
          autoComplete="postal-code"
          returnKeyType="search"
          style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
        />
        <Button label="Search" icon="search-outline" onPress={() => searchSpecialists(specialistLocation)} />
        <Button
          label="Search near me in Maps"
          icon="map-outline"
          variant="secondary"
          onPress={() => searchSpecialists('me')}
        />
        {specialistError ? <Note tone="error">{specialistError}</Note> : null}
      </Card>

      <Muted>{PRIVACY_LINE}</Muted>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 20, gap: 20, paddingBottom: 120 },
  pageHeading: { gap: spacing.sm },
  pageTitle: { fontFamily: fontFamily.display, fontSize: 32, lineHeight: 37, fontWeight: '800', letterSpacing: -0.8 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  tourButton: { alignSelf: 'flex-start' },
  resultTags: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  clipMeta: { marginTop: spacing.xs, gap: 2 },
  sourceContext: { gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderRadius: radius.md, marginTop: spacing.sm },
  input: { borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 11, fontSize: 14 },
  clipName: { fontWeight: '600', fontSize: 14 },
  stage: { fontWeight: '700', fontSize: 15 },
  track: { height: 8, borderRadius: radius.pill, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
  fillIndeterminate: { opacity: 0.6 },
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  resultTitle: { fontSize: 18, fontWeight: '700' },
  observation: { fontSize: 15, lineHeight: 22 },
});
