import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { DisclaimerFooter } from '../../src/components/disclaimer-footer';
import { ScoreBadge } from '../../src/components/score';
import { TrendPanel } from '../../src/components/trend-panel';
import { Button, Card, EmptyState, Eyebrow, Muted } from '../../src/components/ui';
import { useLocalData } from '../../src/hooks/use-local-data';
import { formatDateTime, formatDuration } from '../../src/lib/format';
import { spacing } from '../../src/theme';
import { useColors } from '../../src/theme-context';

function relativeDate(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return 'Date unavailable';
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return days < 7 ? `${days} day${days === 1 ? '' : 's'} ago` : formatDateTime(value);
}

export default function HomeScreen() {
  const colors = useColors();
  const { loading, pets, analyses } = useLocalData();
  const router = useRouter();
  const pet = pets[0];
  const petAnalyses = pet ? analyses.filter((item) => item.petId === pet.id) : [];
  const latest = petAnalyses[0];
  const recent = petAnalyses.slice(0, 3);

  if (loading) {
    return (
      <View style={styles.center}>
        <Text style={{ color: colors.muted }}>Loading your local notebook…</Text>
      </View>
    );
  }

  if (!pet) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Card style={styles.emptyCard}>
          <View style={[styles.paw, { backgroundColor: colors.accentSoft }]}>
            <Ionicons name="paw-outline" size={28} color={colors.accent} />
          </View>
          <Eyebrow>First, a little context</Eyebrow>
          <Text style={[styles.emptyTitle, { color: colors.text }]}>Tell us who you’re watching over.</Text>
          <Muted style={styles.centerText}>
            A pet profile helps keep each walking observation connected to the right companion.
          </Muted>
          <Button
            label="Create pet profile"
            icon="arrow-forward"
            onPress={() => router.push('/pet/new')}
            style={styles.createButton}
          />
        </Card>
        <DisclaimerFooter />
      </ScrollView>
    );
  }

  const initials = pet.name.trim().slice(0, 2).toUpperCase() || '🐾';

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={styles.hero}>
        <View style={{ flex: 1, gap: spacing.sm }}>
          <Eyebrow>A quiet read on movement</Eyebrow>
          <Text style={[styles.heroTitle, { color: colors.text }]}>
            Good morning,{'\n'}
            <Text style={{ color: colors.accent }}>{pet.name}.</Text>
          </Text>
          <Muted>One short walk can become a useful note to bring into a bigger conversation.</Muted>
        </View>
        <Button
          label="Start an analysis"
          icon="sparkles"
          onPress={() => router.push({ pathname: '/analyze', params: { petId: pet.id } })}
          style={styles.heroButton}
        />
      </View>

      <View style={styles.cards}>
        <Card style={styles.summaryCard}>
          <View style={styles.petRow}>
            <View style={[styles.petOrb, { backgroundColor: colors.accentSoft, borderColor: colors.border }]}>
              <Text style={[styles.petInitials, { color: colors.accent }]}>{initials}</Text>
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <Eyebrow>Selected companion</Eyebrow>
              <Text style={[styles.petName, { color: colors.text }]}>{pet.name}</Text>
              <Muted>{pet.species}{pet.age ? ` · ${pet.age} years` : ''}</Muted>
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Edit ${pet.name}'s profile`}
              onPress={() => router.push({ pathname: '/pet/[id]', params: { id: pet.id } })}
              hitSlop={8}
            >
              <Ionicons name="create-outline" size={21} color={colors.muted} />
            </Pressable>
          </View>
          <View style={[styles.stats, { borderTopColor: colors.border }]}>
            <View style={{ flex: 1 }}>
              <Eyebrow>Last read</Eyebrow>
              <Text style={[styles.statValue, { color: colors.text }]}>{latest ? relativeDate(latest.createdAt) : 'Not yet'}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Eyebrow>On device</Eyebrow>
              <Text style={[styles.statValue, { color: colors.text }]}>
                {analyses.length} observation{analyses.length === 1 ? '' : 's'}
              </Text>
            </View>
          </View>
        </Card>

        <Card style={styles.latestCard}>
          <View style={styles.noteHeading}>
            <View style={{ flex: 1 }}>
              <Eyebrow>Latest mobility note</Eyebrow>
              <Text style={[styles.cardTitle, { color: colors.text }]}>
                {latest ? 'A steady picture' : 'Nothing to compare yet'}
              </Text>
            </View>
            {latest && <ScoreBadge score={latest.overallScore} size="small" />}
            {!latest && <Ionicons name="heart-outline" size={24} color={colors.accent} />}
          </View>
          {latest ? (
            <>
              <Muted>{latest.observation}</Muted>
              <View style={styles.noteMeta}>
                <Muted>{formatDateTime(latest.createdAt)} · {formatDuration(latest.durationSeconds)}</Muted>
                <Button
                  label="Open observation"
                  icon="arrow-forward"
                  variant="secondary"
                  onPress={() => router.push({ pathname: '/history/[id]', params: { id: latest.id } })}
                />
              </View>
            </>
          ) : (
            <>
              <Muted>Upload a walking video to create your first educational observation.</Muted>
              <Button
                label="Upload a walk"
                icon="arrow-forward"
                onPress={() => router.push({ pathname: '/analyze', params: { petId: pet.id } })}
              />
            </>
          )}
        </Card>
      </View>

      <TrendPanel analyses={petAnalyses} />

      <Card>
        <View style={styles.sectionHeading}>
          <View style={{ flex: 1 }}>
            <Eyebrow>Recent analyses</Eyebrow>
            <Text style={[styles.cardTitle, { color: colors.text }]}>Your observation trail</Text>
          </View>
          <Pressable
            accessibilityRole="link"
            onPress={() => router.navigate('/history')}
            style={styles.linkRow}
          >
            <Text style={[styles.linkText, { color: colors.accent }]}>See all</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </Pressable>
        </View>
        {recent.length ? (
          recent.map((analysis) => (
            <Pressable
              key={analysis.id}
              accessibilityRole="link"
              onPress={() => router.push({ pathname: '/history/[id]', params: { id: analysis.id } })}
              style={[styles.analysisRow, { borderTopColor: colors.border }]}
            >
              <View style={[styles.videoIcon, { backgroundColor: colors.accentSoft }]}>
                <Ionicons name="videocam-outline" size={17} color={colors.accent} />
              </View>
              <View style={{ flex: 1, gap: 3 }}>
                <Text style={[styles.analysisTitle, { color: colors.text }]} numberOfLines={1}>{analysis.fileName}</Text>
                <Muted style={styles.smallText}>{relativeDate(analysis.createdAt)} · Observation ready</Muted>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 2 }}>
                <Text style={[styles.analysisScore, { color: colors.text }]}>
                  {analysis.overallScore === null ? 'Not scored' : `${Math.round(analysis.overallScore)}/100`}
                </Text>
                <Muted style={styles.smallText}>overall</Muted>
              </View>
            </Pressable>
          ))
        ) : (
          <EmptyState
            icon="videocam-outline"
            title="No observations yet"
            body="Your completed observations will collect here."
          />
        )}
      </Card>

      <Card style={styles.guideCard}>
        <Ionicons name="help-circle-outline" size={21} color={colors.accent} />
        <Text style={[styles.cardTitle, { color: colors.text }]}>How to get a useful clip</Text>
        <View style={{ gap: spacing.sm }}>
          {['Keep the camera low and level.', 'Capture a few steps from the side.', 'Let your pet move naturally.'].map((item) => (
            <View key={item} style={styles.guideRow}>
              <Ionicons name="ellipse" size={6} color={colors.accent} />
              <Muted style={{ flex: 1 }}>{item}</Muted>
            </View>
          ))}
        </View>
        <View style={styles.repeatRow}>
          <Ionicons name="calendar-outline" size={15} color={colors.accent} />
          <Text style={[styles.repeatText, { color: colors.text }]}>Repeat over time, not just once.</Text>
        </View>
      </Card>
      <DisclaimerFooter />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyCard: { alignItems: 'center', paddingVertical: spacing.xxl },
  paw: { width: 58, height: 58, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  emptyTitle: { fontSize: 28, lineHeight: 34, fontWeight: '800', textAlign: 'center', letterSpacing: -0.7 },
  centerText: { textAlign: 'center', maxWidth: 300 },
  createButton: { alignSelf: 'center', marginTop: spacing.sm },
  hero: { gap: spacing.md, paddingVertical: spacing.sm },
  heroTitle: { fontSize: 36, lineHeight: 40, fontWeight: '800', letterSpacing: -1.1 },
  heroButton: { alignSelf: 'flex-start' },
  cards: { gap: spacing.md },
  summaryCard: { gap: spacing.lg },
  petRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  petOrb: { width: 54, height: 54, borderRadius: 18, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  petInitials: { fontWeight: '800', fontSize: 17 },
  petName: { fontWeight: '700', fontSize: 18 },
  stats: { flexDirection: 'row', borderTopWidth: StyleSheet.hairlineWidth, paddingTop: spacing.md, gap: spacing.md },
  statValue: { fontSize: 14, fontWeight: '600', marginTop: 5 },
  latestCard: { gap: spacing.md },
  noteHeading: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  cardTitle: { fontSize: 19, lineHeight: 25, fontWeight: '700', marginTop: spacing.xs },
  noteMeta: { gap: spacing.md, alignItems: 'flex-start' },
  sectionHeading: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  linkRow: { flexDirection: 'row', alignItems: 'center', minHeight: 44 },
  linkText: { fontWeight: '700', fontSize: 13 },
  analysisRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingTop: spacing.md, marginTop: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth },
  videoIcon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  analysisTitle: { fontWeight: '600', fontSize: 14 },
  analysisScore: { fontWeight: '700', fontSize: 13 },
  smallText: { fontSize: 11 },
  guideCard: { gap: spacing.md },
  guideRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center' },
  repeatRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center', marginTop: spacing.xs },
  repeatText: { fontSize: 12, fontWeight: '600' },
});
