import { StyleSheet, Text, View } from 'react-native';

import { useColors } from '../../theme-context';

const STEPS = ['Choose video', 'Review clip', 'Analysis'];

export function AnalysisStepper({ activeStep }: { activeStep: number }) {
  const colors = useColors();

  return (
    <View accessibilityLabel={`Step ${activeStep + 1} of ${STEPS.length}: ${STEPS[activeStep]}`}>
      <View style={styles.steps}>
        {STEPS.map((label, index) => {
          const complete = index < activeStep;
          const active = index === activeStep;
          return (
            <View key={label} style={styles.stepItem}>
              <View
                style={[
                  styles.stepCircle,
                  {
                    backgroundColor: active ? colors.border : colors.track,
                    borderColor: active ? '#5e17eb' : colors.border,
                  },
                ]}
              >
                <Text style={{ color: colors.text, fontSize: 12, fontWeight: '700' }}>
                  {complete ? '✓' : index + 1}
                </Text>
              </View>
              <Text style={[styles.stepLabel, { color: active ? colors.text : colors.muted }]}>
                {label}
              </Text>
              {index < STEPS.length - 1 && (
                <View style={[styles.stepLine, { backgroundColor: colors.border }]} />
              )}
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  steps: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  stepItem: { flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1 },
  stepCircle: { width: 32, height: 32, borderRadius: 16, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  stepLabel: { fontSize: 11, fontWeight: '600', flexShrink: 1 },
  stepLine: { width: 18, height: 1 },
});
