/**
 * Full registry, including development. Wording comes only from the copied registry.
 */

import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Card, Muted, Title } from '../src/components/ui';
import { aiUseEntries, aiUseSummary } from '../src/lib/ai-use';
import { spacing } from '../src/theme';
import { useColors } from '../src/theme-context';

export default function AiUseScreen() {
  const colors = useColors();
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Card>
        <Title>How AI is used</Title>
        <Muted>{aiUseSummary()}</Muted>
      </Card>
      {aiUseEntries().map((entry) => {
        const open = openId === entry.id;
        return (
          <Card key={entry.id}>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              onPress={() => setOpenId(open ? null : entry.id)}
              style={styles.row}
            >
              <Text style={[styles.heading, { color: colors.text }]}>{entry.whatItIs}</Text>
              <Text style={{ color: colors.muted }}>{open ? 'Hide' : 'Show'}</Text>
            </Pressable>
            {open && (
              <View style={{ gap: spacing.sm }}>
                <Muted>What it does. {entry.whatItDoes}</Muted>
                <Muted>What it doesn't do. {entry.whatItDoesnt}</Muted>
                <Muted>Code: {entry.codePath}</Muted>
              </View>
            )}
          </Card>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.md },
  row: { minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  heading: { flex: 1, fontSize: 15, fontWeight: '700' },
});
