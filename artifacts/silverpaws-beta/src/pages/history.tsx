import { type CSSProperties, useState } from 'react';
import { ArrowRight, CalendarDays, CircleAlert, Download, FileVideo, Stethoscope, Trash2 } from 'lucide-react';
import { Link, useParams } from 'wouter';
import { displayScore, type Analysis, type Pet } from '@/lib/storage';
import { aiUseResultLines } from '@/lib/ai-use';
import { formatDate, formatDuration, formatPoseFrames, formatRelative } from '@/lib/format';
import { downloadAnalysisReport } from '@/lib/report';
import { downloadTelemetryCsv, downloadTelemetryJson } from '@/lib/telemetry-export';
import ProductTour from '@/components/ProductTour';
import VetReportModal from '@/components/VetReportModal';

type Props = {
  pets: Pet[];
  analyses: Analysis[];
  deleteAnalysis: (id: string) => void;
  demoAnalysis?: Analysis | null;
  demoTourActive?: boolean;
  onDemoTourComplete?: () => void;
};

const FACTOR_LABELS: { key: keyof NonNullable<Analysis['factors']>; label: string; help: string }[] = [
  { key: 'movementConsistency', label: 'Movement consistency', help: 'How steady the amount of movement stayed between frames.' },
  { key: 'symmetry', label: 'Stride symmetry', help: 'How similar the left and right leg movement looked.' },
  { key: 'mobility', label: 'Mobility', help: 'Stride regularity and up-and-down symmetry, when those were measured.' },
  { key: 'activity', label: 'Activity', help: 'Share of the clip that contained visible movement.' },
  { key: 'historicalChange', label: 'Change from baseline', help: 'How this walk compares with the previous walk measured the same way. A first walk is not scored.' },
];

const WEIGHT_LABELS: Record<string, string> = {
  movementConsistency: 'Movement Consistency',
  symmetry: 'Stride Symmetry',
  mobility: 'Mobility',
  activity: 'Activity',
  historicalChange: 'Baseline Change',
};

const SIGNAL_LABELS: Record<string, string> = {
  good: 'Good signal',
  limited: 'Limited signal',
  unusable: 'No usable signal',
};

const PIPELINE_LABELS: Record<string, string> = {
  'coco-pose': 'COCO-17 output (canine interpretation unvalidated)',
  'dog-pose': 'COCO-17 output (canine interpretation unvalidated)',
  movenet: 'Pose landmarks (older saved walk)',
  'opencv-motion': 'Picture motion only',
};

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
  const measurements = analysis.measurements;
  const [selectedPoint, setSelectedPoint] = useState<PosePoint | null>(null);
  const sample = measurements?.poseSample;
  const legacy = analysis.pipeline === 'movenet' || analysis.sampleData ? measurements?.poseKeypoints : undefined;
  const rawPoints = Array.isArray(sample) && sample.length > 0 ? sample : legacy;
  const points = Array.isArray(rawPoints) ? rawPoints.filter(isPosePoint) : [];
  const sampleFrame = Array.isArray(sample) && sample.length > 0;
  const currentCocoPose = analysis.pipeline === 'coco-pose' || analysis.pipeline === 'dog-pose';
  const connections = currentCocoPose ? COCO_EDGES : POSE_CONNECTIONS;
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
      <section id="movenet-card" className="panel panel-padded mt-5 telemetry-card" aria-label="Frame motion coverage fallback">
        <h2 className="display-title text-2xl">Frame Motion Coverage</h2>
        <p className="body-muted text-sm mt-2">Share of analyzed frame pairs with visible picture motion. {reason}</p>
        <div className="flex justify-between items-center text-sm mt-5">
          <span className="font-semibold">Frames with movement</span>
          <span>{percent === null ? 'Not measured' : <span className="font-mono">{percent.toFixed(0)}%</span>}</span>
        </div>
        <div className="progress-track mt-2" role="progressbar" aria-label="Frame Motion Coverage" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined}>
          <div className="progress-fill" style={{ width: `${percent ?? 0}%` }} />
        </div>
      </section>
    );
  }

  const byName = new Map(points.map((point) => [point.name, point]));

  return (
    <section id="movenet-card" className="panel panel-padded mt-5 telemetry-card" aria-label={sampleFrame ? 'Sample pose frame' : 'Saved pose landmark summary'}>
      <h2 className="display-title text-2xl">{sampleFrame ? 'COCO-17 output summary' : analysis.pipeline === 'movenet' ? 'Vite+ Landmark Summary' : 'Saved landmark summary'}</h2>
      <p className="body-muted text-sm mt-2">
        {sampleFrame
          ? 'Sample frame, not your video. Stride length and left/right symmetry are not measured.'
          : 'Average landmark positions from the clearest frames.'}
      </p>
      {points.length ? (
        <>
          <div className="grid md:grid-cols-[1.2fr_.8fr] gap-5 items-center mt-5">
            <svg
              className="w-full rounded-xl bg-petlens-navy"
              style={{ aspectRatio: '10 / 7' }}
              viewBox="0 0 100 70"
              role="img"
              aria-label={`${points.length} pose keypoint markers`}
            >
              <title>Confidence-filtered average pose landmarks</title>
              {connections.map(([from, to]) => {
                const start = byName.get(from);
                const end = byName.get(to);
                return start && end ? (
                  <line
                    key={`${from}-${to}`}
                    x1={start.x * 100}
                    y1={start.y * 70}
                    x2={end.x * 100}
                    y2={end.y * 70}
                    stroke="var(--color-petlens-teal)"
                    strokeWidth="1.2"
                  />
                ) : null;
              })}
              {points.map((point) => (
                <circle
                  key={point.name}
                  cx={point.x * 100}
                  cy={point.y * 70}
                  r="2.2"
                  fill="var(--color-petlens-emerald)"
                  stroke="var(--color-white)"
                  strokeWidth="0.6"
                  role="button"
                  tabIndex={0}
                  aria-label={`${point.name.replaceAll('_', ' ')} keypoint, ${Math.round(point.confidence * 100)}% confidence`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedPoint(point)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedPoint(point);
                    }
                  }}
                >
                  <title>{point.name.replaceAll('_', ' ')}</title>
                </circle>
              ))}
            </svg>
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="soft-note p-3">
                  <div className="font-bold text-lg">{points.length}</div>
                  <div className="body-muted text-xs mt-1">Keypoint outputs</div>
                </div>
                <div className="soft-note p-3">
                  <div className="font-bold text-lg">
                    {typeof analysis.framesUsed === 'number' && typeof analysis.framesTotal === 'number'
                      ? `${analysis.framesUsed} / ${analysis.framesTotal}`
                      : 'Not measured'}
                  </div>
                  <div className="body-muted text-xs mt-1">Valid Frames Analyzed</div>
                </div>
              </div>
              <div className="soft-note p-4">
                <div className="font-semibold text-sm">Checkpoint label groups</div>
                <ul className="body-muted text-sm mt-3 flex flex-col gap-3">
                  <li>Head labels: nose, eyes, ears</li>
                  <li>Upper-body labels: shoulders, elbows, wrists</li>
                  <li>Lower-body labels: hips, knees, ankles</li>
                </ul>
              </div>
            </div>
          </div>
          <div className="mt-5 rounded-2xl border border-petlens-emerald/60 bg-petlens-emerald/15 px-5 py-4 flex flex-wrap items-center gap-x-5 gap-y-2" data-testid="text-keypoint-confidence">
            {selectedPoint ? (
              <>
                <span className="font-mono font-bold text-3xl text-white">{Math.round(selectedPoint.confidence * 100)}%</span>
                <span className="text-sm font-semibold text-white">confidence · {selectedPoint.name.replaceAll('_', ' ')}</span>
              </>
            ) : (
              <span className="text-sm font-semibold text-white">Select a keypoint to see its confidence.</span>
            )}
            <span className="body-muted text-xs">{points.length} landmarks averaged across {formatPoseFrames(analysis.framesUsed, analysis.framesTotal)}</span>
          </div>
        </>
      ) : (
        <p className="body-muted text-sm mt-5">No confident keypoints were available to visualize for this walk.</p>
      )}
    </section>
  );
}

/** Format a measurement for display, keeping "not measured" visibly different from zero. */
function formatStrideCounts(left: number | null | undefined, right: number | null | undefined) {
  const values = [left, right].filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!values.length) return 'Not measured';
  return [...values].sort((a, b) => a - b).join(' and ');
}

function formatMeasure(value: number | null | undefined, suffix = '', digits = 3) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not measured';
  return `${Number(value.toFixed(digits))}${suffix}`;
}

function FactorRow({ label, help, score }: { label: string; help: string; score: number | null | undefined }) {
  const measured = typeof score === 'number';
  const scoreColor = measured ? getScoreColor(score) : undefined;
  return (
    <div className="factor-row" data-testid={`row-factor-${label.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="min-w-0">
        <div className="font-semibold text-sm">{label}</div>
        <div className="body-muted text-xs mt-1">{help}</div>
        {measured && <div className="progress-track mt-2 max-w-[240px]"><div className="progress-fill" style={{ width: `${score}%`, backgroundColor: scoreColor }} /></div>}
      </div>
      <div className="text-right">
        {measured
          ? <><div className="font-mono font-semibold text-lg" style={{ color: scoreColor }}>{score}</div><div className="body-muted text-[10px]">OUT OF 100</div></>
          : <span className="tag">Not scored</span>}
      </div>
    </div>
  );
}

function SimpleModeDetails({ analysis }: { analysis: Analysis }) {
  const factors = analysis.factors;
  const explanations = FACTOR_LABELS.map((factor) => ({
    ...factor,
    measured: typeof factors?.[factor.key] === 'number' && Number.isFinite(factors[factor.key]),
  }));
  const signalExplanation = analysis.signalQuality === 'unusable'
    ? 'The video did not give the movement reader a clear enough view to make a reliable movement summary.'
    : analysis.signalQuality === 'limited' || analysis.lowConfidence
      ? 'Only part of the movement could be read clearly, so some observations may be missing.'
      : 'The video provided a usable view for the movement details listed below.';

  return (
    <section className="normal-mode-only panel panel-padded mt-5" data-testid="simple-mode-analysis-explanations">
      <div className="eyebrow">Understanding this observation</div>
      <h2 className="display-title text-2xl mt-2">What the movement summary means</h2>
      <p className="body-muted text-sm leading-relaxed mt-3">{signalExplanation}</p>
      <p className="body-muted text-sm leading-relaxed mt-2">
        The overall movement indicator brings together the details that could be read from this one clip. It is not a diagnosis or a complete measure of your pet’s health. Missing details are left out rather than treated as zero.
      </p>
      <div className="soft-note mt-5 flex flex-wrap items-center justify-between gap-3 p-4" data-testid="simple-mode-overall-score">
        <span className="font-semibold text-sm">Overall movement score</span>
        <span className="font-mono font-bold text-xl">
          {typeof analysis.overallScore === 'number' && Number.isFinite(analysis.overallScore)
            ? `${analysis.overallScore}/100`
            : 'Not scored'}
        </span>
      </div>
      <div className="grid gap-3 mt-5">
        {explanations.map((item) => (
          <div className="soft-note p-4" key={String(item.key)} data-testid={`simple-explanation-${String(item.key)}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-bold text-sm">{item.label}</h3>
                <p className="body-muted text-sm leading-relaxed mt-1">{item.help}</p>
              </div>
              <span className="shrink-0 font-mono font-bold text-lg" data-testid={`simple-score-${String(item.key)}`}>
                {item.measured ? `${factors?.[item.key]}/100` : 'Not scored'}
              </span>
            </div>
            {item.measured && (
              <div
                className="progress-track mt-3"
                role="progressbar"
                aria-label={`${item.label} score`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={factors?.[item.key] ?? undefined}
              >
                <div className="progress-fill" style={{ width: `${factors?.[item.key]}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>
      {analysis.concerningChange && (
        <p className="body-muted text-sm leading-relaxed mt-4">
          This clip differed enough from an earlier comparable observation to be flagged for a closer look. Video analysis cannot explain the reason for a change; consider discussing it with your veterinarian.
        </p>
      )}
      {!analysis.concerningChange && explanations.some((item) => item.key === 'historicalChange' && item.measured) && (
        <p className="body-muted text-sm leading-relaxed mt-4">
          The comparison uses a previous walk analyzed with the same measurement method. It describes a difference between clips, not the cause of that difference.
        </p>
      )}
    </section>
  );
}

function getScoreColor(score: number) {
  if (score >= 80) return 'var(--color-status-success)';
  if (score >= 60) return 'var(--color-status-warning)';
  return 'var(--color-status-danger)';
}

function AnalysisList({ analyses, pets }: { analyses: Analysis[]; pets: Pet[] }) {
  if (!analyses.length) {
    return <div className="panel panel-padded text-center py-16"><h2 className="display-title text-3xl">No walks saved yet.</h2><p className="body-muted text-sm mt-3">Your first observation will appear here after you run an analysis.</p><Link href="/analyze" className="btn-primary mt-6" data-testid="link-history-start-analysis">Record a walk <ArrowRight size={15} /></Link></div>;
  }
  return <div className="panel panel-padded">
    {analyses.map((analysis) => {
      const pet = pets.find((item) => item.id === analysis.petId);
      const score = displayScore(analysis);
      return <Link href={`/history/${analysis.id}`} className="analysis-row no-underline" key={analysis.id} data-testid={`link-history-analysis-${analysis.id}`}>
        <div className="flex gap-3 items-center min-w-0"><div className="video-icon"><FileVideo size={16} /></div><div className="min-w-0"><div className="font-semibold truncate text-sm">{analysis.fileName}</div><div className="body-muted text-xs mt-1">{analysis.sampleData ? 'Sample data · ' : ''}{pet?.name ?? 'Unknown pet'} · {formatRelative(analysis.createdAt)} · {formatDuration(analysis.durationSeconds)}</div><p className="normal-mode-only body-muted text-sm leading-relaxed mt-2 line-clamp-2">{analysis.observation ?? 'No written movement observation was saved for this video.'}</p><p className="normal-mode-only body-muted text-xs leading-relaxed mt-1">{analysis.signalQuality === 'unusable' ? 'The clip was not clear enough for a reliable movement summary.' : analysis.signalQuality === 'limited' || analysis.lowConfidence ? 'Only some movement details could be read clearly.' : 'This is an observation of one clip; repeated walks help build a picture over time.'}</p></div></div>
        <div className="flex items-center gap-5"><div className="analytical-only text-right"><div className="font-bold text-sm">{score === null ? 'Not scored' : `${score}/100`}</div><div className="body-muted text-[10px] mt-1">{analysis.signalQuality ? SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality : 'overall'}</div></div><ArrowRight size={16} className="body-muted" /></div>
      </Link>;
    })}
  </div>;
}

function ResultDetail({
  analysis,
  pet,
  onDelete,
  demoTourActive,
  onDemoTourComplete,
}: {
  analysis: Analysis;
  pet?: Pet;
  onDelete: () => void;
  demoTourActive: boolean;
  onDemoTourComplete: () => void;
}) {
  const [showReport, setShowReport] = useState(false);
  const score = displayScore(analysis);
  const factors = analysis.factors;
  const measurements = analysis.measurements;
  const [telemetryMenuOpen, setTelemetryMenuOpen] = useState(false);

  return <div className="page-frame max-w-5xl">
    <div className="flex flex-wrap items-end justify-between gap-5 stagger">
      <div><h1 className="display-title text-5xl">A <span className="text-petlens-trim">breakdown</span> of {analysis.demo ? "the sample pet's walk" : `${pet?.name ?? 'your pet'}'s walk`}</h1></div>
       <div className="flex flex-wrap gap-2">
         <button id="vet-summary-export" type="button" className="btn-secondary" onClick={() => setShowReport(true)} data-testid={`button-vet-summary-report-${analysis.id}`}>Export Movement Report PDF</button>
         {!analysis.demo && <button className="btn-quiet" onClick={() => { if (window.confirm('Remove this saved observation from this device?')) onDelete(); }} data-testid={`button-delete-analysis-${analysis.id}`}><Trash2 size={15} /> Remove</button>}
       </div>
    </div>

    {analysis.sampleData && (
      <section className="soft-note p-4 mt-5" data-testid="text-sample-data-notice">
        <p className="text-sm leading-relaxed"><strong>Sample data;</strong> This example is included in app charts for demonstration. Clear sample walks from Home or Analyze, to efficiently upload your own walks</p>
      </section>
    )}

    {!analysis.demo && (
      <section className="analytical-only panel panel-padded mt-5" aria-label="Export Options">
        <div className="eyebrow">Export Options</div>
        <div className="flex flex-wrap items-start gap-3 mt-3">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => downloadAnalysisReport(analysis, pet)}
            data-testid={`button-download-report-${analysis.id}`}
          >
            <Download size={15} /> Download Movement Observation PDF
          </button>
          <div className="relative">
            <button
              type="button"
              className="analytical-only btn-secondary"
              aria-expanded={telemetryMenuOpen}
              aria-controls={`telemetry-export-options-${analysis.id}`}
              onClick={() => setTelemetryMenuOpen((open) => !open)}
              data-testid={`button-export-telemetry-${analysis.id}`}
            >
              <Download size={15} /> Export Raw Telemetry (CSV / JSON)
            </button>
            {telemetryMenuOpen && (
              <div
                className="panel panel-padded absolute left-0 top-full z-10 mt-2 flex min-w-full flex-col gap-2"
                id={`telemetry-export-options-${analysis.id}`}
              >
                <button
                  type="button"
                  className="btn-quiet justify-start"
                  onClick={() => {
                    downloadTelemetryCsv(analysis);
                    setTelemetryMenuOpen(false);
                  }}
                  data-testid={`button-download-telemetry-csv-${analysis.id}`}
                >
                  Download CSV
                </button>
                <button
                  type="button"
                  className="btn-quiet justify-start"
                  onClick={() => {
                    downloadTelemetryJson(analysis, pet);
                    setTelemetryMenuOpen(false);
                  }}
                  data-testid={`button-download-telemetry-json-${analysis.id}`}
                >
                  Download JSON
                </button>
              </div>
            )}
          </div>
        </div>
      </section>
    )}

    {analysis.lowConfidence && (
      <section className="alert-note p-5 mt-7 flex gap-3 items-start" role="alert" data-testid="text-low-confidence">
        <CircleAlert size={19} style={{ flexShrink: 0 }} />
        <div>
          <h2 className="font-bold text-sm">Low confidence — try a clearer clip</h2>
          <p className="text-sm leading-relaxed mt-2">The pose model could not see the body clearly enough to measure the legs. Film from the side with the whole body in frame. Values that were not measured are shown as “Not measured”, not as zero.</p>
        </div>
      </section>
    )}

    {analysis.qualityNotes && analysis.qualityNotes.length > 0 && (
      <section className="soft-note p-5 mt-5" data-testid="text-quality-notes">
        <h2 className="font-bold text-sm">Before the next clip</h2>
        <ul className="text-sm leading-relaxed mt-2 list-disc pl-5">
          {analysis.qualityNotes.map((note) => <li key={note}>{note}</li>)}
        </ul>
      </section>
    )}

    {analysis.concerningChange && (
      <section className="alert-note p-5 mt-7 flex gap-3 items-start stagger" data-testid="text-vet-recommendation">
        <Stethoscope size={19} style={{ flexShrink: 0 }} />
        <div>
          <h2 className="font-bold text-sm">Worth asking a veterinarian about</h2>
          <p className="text-sm leading-relaxed mt-2">The measured values changed enough to be worth a professional opinion. PetLens cannot tell you why they changed, and this is not a diagnosis — a veterinarian can examine what a video cannot show.</p>
        </div>
      </section>
    )}

    <div className="detail-grid mt-7 stagger-2">
      <div className="panel panel-padded col-span-full">
        <div className="flex flex-wrap justify-between items-center gap-5">
          <div>
            <div className="eyebrow">Overall wellness indicator</div>
            <div className="analytical-only metric-number mt-4" data-testid="text-overall-score">{score === null ? 'Not scored' : <>{score}<span className="text-2xl tracking-normal">/100</span></>}</div>
            <p className="body-muted text-sm mt-3">It describes this clip, not your pet’s health.</p>
            <p className="normal-mode-only body-muted text-sm leading-relaxed mt-3" data-testid="simple-mode-overall-explanation">
              {score === null
                ? 'There was not enough usable information in this clip to create an overall movement summary.'
                : 'This is a short summary of the movement details that could be read in this clip. It does not say whether your pet is healthy or explain why a movement pattern occurred.'}
            </p>
          </div>
          {score !== null && <div className="analytical-only score-ring" style={{ '--score': `${score * 3.6}deg` } as CSSProperties}><div><div className="metric-number text-3xl">{score}</div><div className="text-[9px] body-muted mt-1">SCORE</div></div></div>}
        </div>
        <div className="analytical-only flex flex-wrap gap-2 mt-7">
          {analysis.signalQuality && <span className="tag">{SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality}</span>}
          {analysis.pipeline && <span className="tag">{PIPELINE_LABELS[analysis.pipeline] ?? analysis.pipeline}</span>}
          {analysis.modelInfo && <span className="tag">{analysis.modelInfo.modelName}</span>}
          {analysis.usedLlm && <span className="tag">Model-written summary</span>}
        </div>
        {analysis.signalNote && <p className="analytical-only body-muted text-xs leading-relaxed mt-4">{analysis.signalNote}</p>}
        {analysis.modelInfo && <p className="analytical-only body-muted text-xs leading-relaxed mt-2">Measured on the server with {analysis.modelInfo.modelName}, version {analysis.modelInfo.modelVersion}.</p>}
        {aiUseResultLines(analysis.aiUse).length > 0 && (
          <ul className="analytical-only mt-3 flex flex-col gap-1" data-testid="text-ai-use-lines">
            {aiUseResultLines(analysis.aiUse).map((line) => (
              <li key={line} className="body-muted text-xs leading-relaxed">{line}</li>
            ))}
          </ul>
        )}
      </div>
    </div>

    <SimpleModeDetails analysis={analysis} />

    <div className="analytical-only"><PipelineVisual analysis={analysis} /></div>
    {/* Per-frame pose tracks are not stored; avoid implying that aggregate mean landmarks are frame-synchronized. */}

    {factors && (
      <section id="factor-scores" className="analytical-only panel panel-padded mt-5 stagger-3 telemetry-card">
        <div className="eyebrow">Where the score came from</div>
        <h2 className="display-title text-2xl mt-2">Factor breakdown</h2>
        <p className="body-muted text-sm mt-2 max-w-2xl">Each factor is measured separately. A factor with no score means this clip did not carry enough signal to measure it — it does not mean zero.</p>
        <div className="mt-5">
          {FACTOR_LABELS.map((factor) => (
            <FactorRow key={factor.key} label={factor.label} help={factor.help} score={factors[factor.key]} />
          ))}
        </div>
        {analysis.weightsUsed && Object.keys(analysis.weightsUsed).length > 0 && (
          <p className="body-muted text-xs mt-5">
            Weights used: {Object.entries(analysis.weightsUsed).map(([name, weight]) => `${WEIGHT_LABELS[name] ?? name} (${Math.round((weight ?? 0) * 100)}%)`).join(' • ')}
          </p>
        )}
      </section>
    )}

    {measurements && (
      <section className="analytical-only panel panel-padded mt-5 stagger-3">
        <div className="eyebrow">Raw measurements</div>
        <div className="measure-grid mt-5">
          {([
            ['Frames read', formatMeasure(measurements.frameCount, '', 0)],
            ['Measured length', formatMeasure(measurements.durationSeconds, 's', 2)],
            ['Mean frame motion', formatMeasure(measurements.motionMean, '', 4)],
            ['Motion variation', formatMeasure(measurements.motionStd, '', 4)],
            ['Frame Motion Coverage', formatMeasure(typeof measurements.motionCoverage === 'number' ? measurements.motionCoverage * 100 : undefined, '%', 0)],
            ['Front strides', formatStrideCounts(measurements.strides?.frontLeft?.strideCount, measurements.strides?.frontRight?.strideCount)],
            ['Rear strides', formatStrideCounts(measurements.strides?.rearLeft?.strideCount, measurements.strides?.rearRight?.strideCount)],
            ['Front symmetry', formatMeasure(measurements.limbSymmetry?.front)],
            ['Rear symmetry', formatMeasure(measurements.limbSymmetry?.rear)],
            ['Front stride length', formatMeasure(measurements.strideLengthBodyLengths?.front, ' body lengths')],
            ['Rear stride length', formatMeasure(measurements.strideLengthBodyLengths?.rear, ' body lengths')],
            ['Cadence', formatMeasure(measurements.cadenceStridesPerMinute, ' / min', 1)],
            ['Stride regularity', formatMeasure(measurements.strideTimeCv)],
            ['Head vertical asymmetry', formatMeasure(measurements.headBobAsymmetry)],
            ['Pelvis vertical asymmetry', formatMeasure(measurements.pelvisAsymmetry)],
            ['Observed dog detections', formatMeasure(typeof measurements.subject?.dogFramesShare === 'number' ? measurements.subject.dogFramesShare * 100 : undefined, '%', 0)],
            ['Stride symmetry', formatMeasure(measurements.strideSymmetry)],
            ['Asymmetry', formatMeasure(analysis.asymmetryPercent, '%', 2)],
            ['Hip stability', formatMeasure(measurements.hipStability)],
            ['Pose confidence', formatMeasure(analysis.confidence, '%', 1)],
            ['Confident frames', formatPoseFrames(analysis.framesUsed, analysis.framesTotal)],
          ] as [string, string][]).filter(([, value]) => value !== 'Not measured').map(([label, value]) => (
            <div className="soft-note p-3" key={label}><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">{label}</div><div className="font-mono font-medium text-lg mt-1">{value}</div></div>
          ))}
        </div>
        {(measurements.notMeasuredReasons ?? []).length > 0 && (
          <ul className="body-muted text-sm mt-4 flex flex-col gap-1" data-testid="text-not-measured-reasons">
            {measurements.notMeasuredReasons?.map((reason) => <li key={reason}>Not measured: {reason}</li>)}
          </ul>
        )}
      </section>
    )}

    {analysis.demo && demoTourActive && (
      <ProductTour
        initialStep={1}
        onComplete={() => { setShowReport(false); onDemoTourComplete(); }}
        onStepChange={(step) => setShowReport(step === 3)}
      />
    )}
    {showReport && <VetReportModal analysis={analysis} pet={pet} onClose={() => setShowReport(false)} />}
  </div>;
}

export default function History({ pets, analyses, deleteAnalysis, demoAnalysis, demoTourActive = false, onDemoTourComplete = () => {} }: Props) {
  const params = useParams<{ id?: string }>();
  const selected = params.id
    ? analyses.find((analysis) => analysis.id === params.id) ?? (demoAnalysis?.id === params.id ? demoAnalysis : undefined)
    : undefined;
  if (params.id && selected) {
    return <ResultDetail analysis={selected} pet={pets.find((pet) => pet.id === selected.petId)} onDelete={() => deleteAnalysis(selected.id)} demoTourActive={demoTourActive} onDemoTourComplete={onDemoTourComplete} />;
  }
  if (params.id && !selected) {
    return <div className="page-frame"><div className="panel panel-padded text-center max-w-lg mx-auto mt-16"><CircleAlert size={28} className="mx-auto text-status-error" /><h1 className="display-title text-3xl mt-5">That <span className="text-petlens-trim">observation</span> moved on.</h1><p className="body-muted mt-3">It may have been removed from local storage.</p><Link href="/history" className="btn-primary mt-6" data-testid="link-return-history">Back to history</Link></div></div>;
  }
  return <div className="page-frame max-w-5xl">
    <div className="flex flex-wrap justify-between items-end gap-5 stagger"><h1 className="display-title text-5xl">Your pet’s <span className="text-petlens-trim">history</span></h1><Link href="/analyze" className="btn-primary" data-testid="link-history-new-analysis"><FileVideo size={16} /> New analysis</Link></div>
    <div className="analytical-only flex items-center gap-2 body-muted text-xs mt-8"><CalendarDays size={14} /> {analyses.length} saved observation{analyses.length === 1 ? '' : 's'} on this device</div>
    <div className="mt-4 stagger-2"><AnalysisList analyses={analyses} pets={pets} /></div>
  </div>;
}
