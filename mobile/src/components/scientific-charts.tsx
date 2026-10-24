import { useColors } from '../theme-context';
import type { AnalysisMeasurements, MotionTracePoint } from '../lib/types';
import { Card, Eyebrow, Muted } from './ui';
import { Text, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Text as SvgText } from 'react-native-svg';

const WIDTH = 320;
const HEIGHT = 160;
const PLOT_LEFT = 48;
const PLOT_RIGHT = 12;
const PLOT_TOP = 12;
const PLOT_BOTTOM = 30;

function validPoints(value: unknown): MotionTracePoint[] {
  if (!Array.isArray(value)) return [];
  return value.filter((point): point is MotionTracePoint => {
    if (!point || typeof point !== 'object') return false;
    const candidate = point as Record<string, unknown>;
    return (
      typeof candidate.timeSeconds === 'number' &&
      Number.isFinite(candidate.timeSeconds) &&
      candidate.timeSeconds >= 0 &&
      typeof candidate.movement === 'number' &&
      Number.isFinite(candidate.movement) &&
      candidate.movement >= 0 &&
      candidate.movement <= 1
    );
  });
}

function MotionTraceChart({ measurements }: { measurements: AnalysisMeasurements }) {
  const colors = useColors();
  const trace = measurements.motionTrace;
  const points = validPoints(trace?.points);
  const duration = measurements.durationSeconds;

  return (
    <Card>
      <Eyebrow>Per-video graph</Eyebrow>
      <Text style={{ color: colors.text, fontSize: 18, fontWeight: '700' }}>
        Frame-to-frame visual motion
      </Text>
      <Muted>
        Whole-picture grayscale change over time. This is not a limb trajectory or stride measurement.
      </Muted>
      {points.length >= 2 && trace && duration > 0 ? (
        <>
          <View style={{ marginTop: 8 }}>
            <Svg
              width="100%"
              height={HEIGHT}
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              accessibilityRole="image"
              accessibilityLabel={`Frame-to-frame visual motion over ${duration.toFixed(1)} seconds, plotted from ${points.length} points. The vertical axis uses this clip's scale and does not show limb motion.`}
            >
              <Line x1={PLOT_LEFT} y1={PLOT_TOP} x2={PLOT_LEFT} y2={HEIGHT - PLOT_BOTTOM} stroke={colors.border} />
              <Line
                x1={PLOT_LEFT}
                y1={HEIGHT - PLOT_BOTTOM}
                x2={WIDTH - PLOT_RIGHT}
                y2={HEIGHT - PLOT_BOTTOM}
                stroke={colors.border}
              />
              <Line
                x1={PLOT_LEFT}
                y1={PLOT_TOP}
                x2={WIDTH - PLOT_RIGHT}
                y2={PLOT_TOP}
                stroke={colors.track}
                strokeDasharray="3 4"
              />
              <Line
                x1={PLOT_LEFT}
                y1={(PLOT_TOP + HEIGHT - PLOT_BOTTOM) / 2}
                x2={WIDTH - PLOT_RIGHT}
                y2={(PLOT_TOP + HEIGHT - PLOT_BOTTOM) / 2}
                stroke={colors.track}
                strokeDasharray="3 4"
              />
              <SvgText x={PLOT_LEFT - 6} y={HEIGHT - PLOT_BOTTOM + 4} fill={colors.muted} fontSize="9" textAnchor="end">
                0
              </SvgText>
              <SvgText x={PLOT_LEFT - 6} y={PLOT_TOP + 4} fill={colors.muted} fontSize="9" textAnchor="end">
                {Math.max(...points.map((point) => point.movement)).toPrecision(3)}
              </SvgText>
              <SvgText x={PLOT_LEFT} y={HEIGHT - 8} fill={colors.muted} fontSize="9" textAnchor="middle">
                0 s
              </SvgText>
              <SvgText x={WIDTH - PLOT_RIGHT} y={HEIGHT - 8} fill={colors.muted} fontSize="9" textAnchor="end">
                {duration.toFixed(1)} s
              </SvgText>
              <Path
                d={motionPath(points, duration)}
                fill="none"
                stroke={colors.accent}
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </Svg>
          </View>
          <Muted>
            {trace.sampleCount} frame comparisons · {points.length} plotted point{points.length === 1 ? '' : 's'}.
            The y-axis scales to this clip; do not compare heights across different videos.
          </Muted>
        </>
      ) : (
        <Muted>
          {trace
            ? 'A time series could not be drawn because this clip has too few timed frame comparisons.'
            : 'This saved walk does not include the motion trace, so a graph is unavailable.'}
        </Muted>
      )}
    </Card>
  );
}

function motionPath(points: MotionTracePoint[], duration: number): string {
  const plotWidth = WIDTH - PLOT_LEFT - PLOT_RIGHT;
  const plotHeight = HEIGHT - PLOT_TOP - PLOT_BOTTOM;
  const max = Math.max(...points.map((point) => point.movement), 0.001);
  return points
    .map((point, index) => {
      const x = PLOT_LEFT + Math.max(0, Math.min(1, point.timeSeconds / duration)) * plotWidth;
      const y = HEIGHT - PLOT_BOTTOM - (point.movement / max) * plotHeight;
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');
}

function LimbSymmetryChart({ measurements }: { measurements: AnalysisMeasurements }) {
  const colors = useColors();
  const pairs = measurements.limbSymmetryIndex;
  const rows = [
    { label: 'Forelimb pair', key: 'front' as const, left: measurements.strides?.frontLeft?.strideCount, right: measurements.strides?.frontRight?.strideCount },
    { label: 'Hindlimb pair', key: 'rear' as const, left: measurements.strides?.rearLeft?.strideCount, right: measurements.strides?.rearRight?.strideCount },
  ].filter((row) => {
    const index = pairs?.[row.key];
    return typeof index?.signed === 'number' && Number.isFinite(index.signed);
  });

  return (
    <Card>
      <Eyebrow>Gait comparison</Eyebrow>
      <Text style={{ color: colors.text, fontSize: 18, fontWeight: '700' }}>
        Paired limb symmetry index
      </Text>
      <Muted>
        Signed SI = 200 × (left − right) ÷ (left + right). Positive means the left excursion was larger. This experimental measure is not a clinical severity scale.
      </Muted>
      {rows.length > 0 ? (
        <>
          <Svg
            width="100%"
            height={104}
            viewBox="0 0 320 104"
            accessibilityRole="image"
            accessibilityLabel={rows.length
              ? rows
                  .map((row) => `${row.label} signed SI ${pairs?.[row.key]?.signed?.toFixed(1)}`)
                  .join('; ')
              : 'Paired limb symmetry index was not measured for this walk.'}
          >
            <Line x1="48" y1="20" x2="308" y2="20" stroke={colors.track} />
            <Line x1="48" y1="20" x2="48" y2="25" stroke={colors.muted} />
            <Line x1="178" y1="20" x2="178" y2="86" stroke={colors.border} />
            <Line x1="308" y1="20" x2="308" y2="25" stroke={colors.muted} />
            <SvgText x="48" y="15" fill={colors.muted} fontSize="9" textAnchor="middle">−200</SvgText>
            <SvgText x="178" y="15" fill={colors.muted} fontSize="9" textAnchor="middle">0</SvgText>
            <SvgText x="308" y="15" fill={colors.muted} fontSize="9" textAnchor="middle">+200</SvgText>
            {rows.map((row, index) => {
              const value = pairs?.[row.key]?.signed;
              if (typeof value !== 'number') return null;
              const y = 42 + index * 34;
              const x = 178 + (Math.max(-200, Math.min(200, value)) / 200) * 130;
              return (
                <G key={row.key}>
                  <SvgText x="4" y={y + 4} fill={colors.text} fontSize="10">{row.label}</SvgText>
                  <Line x1="178" y1={y} x2={x} y2={y} stroke={colors.accent} strokeWidth="5" strokeLinecap="round" />
                  <Circle cx={x} cy={y} r="5" fill={colors.accent} />
                  <SvgText x="312" y={y + 4} fill={colors.text} fontSize="9" textAnchor="end">
                    {`${value > 0 ? '+' : ''}${value.toFixed(1)}`}
                  </SvgText>
                </G>
              );
            })}
          </Svg>
          {rows.map((row) => (
            <Muted key={`${row.key}-n`}>
              {row.label}: left {row.left ?? 'n/a'} strides; right {row.right ?? 'n/a'} strides.
            </Muted>
          ))}
        </>
      ) : (
        <Muted>
          Not measured for this walk. The available pose head is COCO-17, not a validated canine skeleton, so no left/right stride symmetry is inferred.
        </Muted>
      )}
    </Card>
  );
}

export function ScientificCharts({ measurements }: { measurements: AnalysisMeasurements }) {
  return (
    <>
      <MotionTraceChart measurements={measurements} />
      <LimbSymmetryChart measurements={measurements} />
    </>
  );
}
