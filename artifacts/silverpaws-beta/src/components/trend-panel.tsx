import { type Analysis } from '@/lib/storage';
import { formatDate } from '@/lib/format';
import {
  formatTrendScore,
  pipelineLabel,
  sparklineLayout,
  trendSeries,
  type TrendPoint,
  type TrendSeries,
} from '@/lib/trends';

const CHART_WIDTH = 280;
const CHART_HEIGHT = 56;

function Sparkline({ points }: { points: TrendPoint[] }) {
  const scores = points.map((point) => point.overallScore);
  const layout = sparklineLayout(scores, CHART_WIDTH, CHART_HEIGHT);
  if (layout.dots.length === 0) return null;

  const summary = scores.map((score) => formatTrendScore(score)).join(', ');
  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label={`Overall scores from oldest to newest: ${summary}. A gap means that walk was not scored.`}
      className="w-full max-w-xs mt-3"
      data-testid="trend-sparkline"
    >
      {layout.segments.map((segment) => (
        <polyline key={segment} fill="none" stroke="#3eb49c" strokeWidth="2" points={segment} />
      ))}
      {layout.dots.map((dot, index) => (
        <circle key={`${dot.x}-${index}`} cx={dot.x} cy={dot.y} r="3.5" fill="#3794a4">
          <title>{formatTrendScore(dot.score)} out of 100</title>
        </circle>
      ))}
    </svg>
  );
}

function seriesNote(series: TrendSeries): string {
  const scored = series.points.filter((point) => point.overallScore !== null);
  if (series.points.length === 1) {
    return 'This is the only saved walk measured this way. A second walk from the same method will show whether the scores moved.';
  }
  if (scored.length < 2) {
    return 'Only one of these walks has an overall score, so there is no line to draw. A walk without a score is not plotted as zero.';
  }
  const oldest = scored[0];
  const newest = scored[scored.length - 1];
  if (!oldest || !newest) return '';
  return `Oldest scored walk ${formatTrendScore(oldest.overallScore)} on ${formatDate(oldest.createdAt)}. Newest ${formatTrendScore(newest.overallScore)} on ${formatDate(newest.createdAt)}.`;
}

function TrendGroup({ series }: { series: TrendSeries }) {
  return (
    <div className="mt-5" data-testid={`trend-series-${series.pipeline}`}>
      <h3 className="font-bold text-sm">{pipelineLabel(series.pipeline)}</h3>
      <p className="body-muted text-sm leading-relaxed mt-1">{seriesNote(series)}</p>
      <Sparkline points={series.points} />
      <table className="w-full text-sm mt-3">
        <caption className="sr-only">
          Saved walks measured with {pipelineLabel(series.pipeline)}, oldest first
        </caption>
        <thead>
          <tr className="body-muted text-xs text-left">
            <th className="font-semibold py-2 pr-3">Date</th>
            <th className="font-semibold py-2 pr-3">Overall</th>
            <th className="font-semibold py-2 pr-3">Movement consistency</th>
            <th className="font-semibold py-2">Symmetry</th>
          </tr>
        </thead>
        <tbody>
          {series.points.map((point) => (
            <tr key={point.id} className="border-t" data-testid={`trend-row-${point.id}`}>
              <td className="py-2 pr-3">{formatDate(point.createdAt)}</td>
              <td className="py-2 pr-3">{formatTrendScore(point.overallScore)}</td>
              <td className="py-2 pr-3">{formatTrendScore(point.movementConsistency)}</td>
              <td className="py-2">{formatTrendScore(point.symmetry)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TrendPanel({ analyses }: { analyses: Analysis[] }) {
  const series = trendSeries(analyses);

  return (
    <section className="soft-note p-5 mt-5" data-testid="trend-panel">
      
      <h2 className="font-bold text-sm mt-2">How the scores moved</h2>
      {series.length === 0 ? (
        <p className="body-muted text-sm leading-relaxed mt-2" data-testid="trend-empty">
          Charts appear here after the first walk is saved.
        </p>
      ) : (
        <>
          <p className="body-muted text-sm leading-relaxed mt-2">
            {series.length > 1
              ? 'These walks were measured in more than one way. Each way is listed on its own and is not plotted together.'
              : 'Only walks measured the same way are compared. A score that was not measured is shown as “Not scored”, not as zero.'}
          </p>
          {series.map((item) => (
            <TrendGroup key={item.pipeline} series={item} />
          ))}
        </>
      )}
    </section>
  );
}
