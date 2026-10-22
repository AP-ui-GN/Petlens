/**
 * Last-resort screen when a view throws. The rest of the app stays installed.
 */

import { Component, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { spacing } from '../theme';
import { useColors } from '../theme-context';

function ErrorFallback({ onReset }: { onReset: () => void }) {
  const colors = useColors();
  return (
    <View style={[styles.page, { backgroundColor: colors.background }]}>
      <Text style={[styles.title, { color: colors.text }]} accessibilityRole="header">
        Something went wrong
      </Text>
      <Text style={[styles.body, { color: colors.text }]}>
        This screen hit an unexpected error. Your saved pets and walks are still on this phone. This is not a medical alert.
      </Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Try again" onPress={onReset} style={[styles.button, { backgroundColor: colors.accent }]}>
        <Text style={styles.buttonText}>Try again</Text>
      </Pressable>
    </View>
  );
}

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return <ErrorFallback onReset={this.reset} />;
  }
}

const styles = StyleSheet.create({
  page: { flex: 1, justifyContent: 'center', padding: spacing.xl, gap: spacing.md },
  title: { fontSize: 22, fontWeight: '700' },
  body: { fontSize: 15, lineHeight: 22 },
  button: { minHeight: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
