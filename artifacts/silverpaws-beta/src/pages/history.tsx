import { type CSSProperties, useState } from 'react';
import { ArrowLeft, ArrowRight, CalendarDays, CircleAlert, Download, FileVideo, Gauge, Info, Ruler, Stethoscope, Trash2 } from 'lucide-react';
import { Link, useParams } from 'wouter';
import { displayScore, type Analysis, type Pet } from '@/lib/storage';
import { SAFETY_DISCLAIMER } from '@/lib/disclaimers';
import { aiUseResultLines } from '@/lib/ai-use';
import { formatDate, formatDuration, formatPoseFrames, formatRelative } from '@/lib/format';
import { downloadAnalysisReport } from '@/lib/report';
import { downloadTelemetryCsv, downloadTelemetryJson } from '@/lib/telemetry-export';
import { TrendPanel } from '@/components/trend-panel';
import ProductTour from '@/components/ProductTour';
import VetReportModal from '@/components/VetReportModal';
import { SAMPLE_DATA_LABEL } from '@/lib/sample-analysis';

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
  const legacy = analysis.pipeline === 'movenet' ? measurements?.poseKeypoints : undefined;
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
        <div className="eyebrow">Computer vision activity</div>
        <h2 className="display-title text-2xl mt-2">Frame Motion Coverage</h2>
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
      <div className="eyebrow">Computer vision activity</div>
      <h2 className="display-title text-2xl mt-2">{sampleFrame ? 'COCO-17 output summary' : analysis.pipeline === 'movenet' ? 'MoveNet landmark summary' : 'Saved landmark summary'}</h2>
      <p className="body-muted text-sm mt-2">
        {sampleFrame
          ? 'Sample frame (not your video). These are COCO-17 human joint labels normalized to the detected dog box, not validated canine anatomical landmarks. This head has no neck or tail-base point, so stride length and left/right gait symmetry are not measured.'
          : 'Mean normalized COCO-17 landmark positions from confident frames; canine anatomical interpretation is unvalidated.'}
      </p>
      {points.length ? (
        <>
          <div className="grid md:grid-cols-[1.2fr_.8fr] gap-5 items-center mt-5">
            <svg
              className="w-full rounded-xl bg-[#0a4267]"
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
                    stroke="#3794a4"
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
                  fill="#3eb49c"
                  stroke="#e8f7fb"
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
                <p className="body-muted text-xs mt-3">These are the checkpoint's COCO-17 labels, not validated canine anatomy. Wrists and ankles must not be interpreted as paws or hocks.</p>
              </div>
            </div>
          </div>
          <p className="body-muted text-xs mt-3">
            {selectedPoint
              ? `${selectedPoint.name.replaceAll('_', ' ')} · ${Math.round(selectedPoint.confidence * 100)}% confidence`
              : 'Select a keypoint to inspect its confidence.'}
            {' · '}{points.length} landmarks averaged across {formatPoseFrames(analysis.framesUsed, analysis.framesTotal)}.
          </p>
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

function getScoreColor(score: number) {
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#d97706';
  return '#dc2626';
}

function AnalysisList({ analyses, pets }: { analyses: Analysis[]; pets: Pet[] }) {
  if (!analyses.length) {
    return <div className="panel panel-padded text-center py-16"><div className="empty-art mx-auto"><FileVideo size={27} /></div><h2 className="display-title text-3xl mt-5">No walks saved yet.</h2><p className="body-muted text-sm mt-3">Your first observation will appear here after you run an analysis.</p><Link href="/analyze" className="btn-primary mt-6" data-testid="link-history-start-analysis">Record a walk <ArrowRight size={15} /></Link></div>;
  }
  return <div className="panel panel-padded">
    {analyses.map((analysis) => {
      const pet = pets.find((item) => item.id === analysis.petId);
      const score = displayScore(analysis);
      return <Link href={`/history/${analysis.id}`} className="analysis-row no-underline" key={analysis.id} data-testid={`link-history-analysis-${analysis.id}`}>
        <div className="flex gap-3 items-center min-w-0"><div className="video-icon"><FileVideo size={16} /></div><div className="min-w-0"><div className="font-semibold truncate text-sm">{analysis.fileName}</div><div className="body-muted text-xs mt-1">{pet?.name ?? 'Unknown pet'} · {formatRelative(analysis.createdAt)} · {formatDuration(analysis.durationSeconds)}</div></div></div>
        <div className="flex items-center gap-5"><div className="text-right"><div className="font-bold text-sm">{score === null ? 'Not scored' : `${score}/100`}</div><div className="body-muted text-[10px] mt-1">{analysis.signalQuality ? SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality : 'overall'}</div></div><ArrowRight size={16} className="body-muted" /></div>
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
    <Link href="/history" className="btn-quiet -ml-3" data-testid="link-back-history"><ArrowLeft size={15} /> All observations</Link>
    <div className="flex flex-wrap items-end justify-between gap-5 mt-6 stagger">
      <div><div className="eyebrow">{analysis.demo ? 'Demo result' : `Saved observation · ${formatDate(analysis.createdAt)}`}</div><h1 className="display-title text-5xl mt-3">A closer look at<br /><span className="accent-label">{analysis.demo ? 'the sample pet' : pet?.name ?? 'your pet'}’s walk.</span></h1></div>
       <div className="flex flex-wrap gap-2">
         <button id="vet-summary-export" type="button" className="btn-secondary" onClick={() => setShowReport(true)} data-testid={`button-vet-summary-report-${analysis.id}`}>Export Movement Report PDF</button>
         {!analysis.demo && <button className="btn-quiet" onClick={() => { if (window.confirm('Remove this saved observation from this device?')) onDelete(); }} data-testid={`button-delete-analysis-${analysis.id}`}><Trash2 size={15} /> Remove</button>}
       </div>
    </div>

    {!analysis.demo && (
      <section className="panel panel-padded mt-5" aria-label="Export Options">
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
              className="btn-secondary"
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

    {analysis.demo && (
      <div className="soft-note p-4 mt-5" role="note" data-testid="text-sample-data-badge">
        <strong>{SAMPLE_DATA_LABEL}</strong>
        <p className="body-muted text-sm mt-1">This example is mock data, was not analyzed from a video, and is not saved to your history.</p>
      </div>
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
      <div className="panel panel-padded">
        <div className="flex flex-wrap justify-between items-center gap-5">
          <div>
            <div className="eyebrow">Overall wellness indicator</div>
            <div className="metric-number mt-4" data-testid="text-overall-score">{score === null ? 'Not scored' : <>{score}<span className="text-2xl tracking-normal">/100</span></>}</div>
            <p className="body-muted text-sm mt-3">A blend of the factors below. It describes this clip, not your pet’s health.</p>
          </div>
          {score !== null && <div className="score-ring" style={{ '--score': `${score * 3.6}deg` } as CSSProperties}><div><div className="metric-number text-3xl">{score}</div><div className="text-[9px] body-muted mt-1">SCORE</div></div></div>}
        </div>
        <div className="flex flex-wrap gap-2 mt-7">
          {analysis.signalQuality && <span className="tag">{SIGNAL_LABELS[analysis.signalQuality] ?? analysis.signalQuality}</span>}
          {analysis.pipeline && <span className="tag">{PIPELINE_LABELS[analysis.pipeline] ?? analysis.pipeline}</span>}
          {analysis.modelInfo && <span className="tag">{analysis.modelInfo.modelName}</span>}
          {analysis.usedLlm && <span className="tag">Model-written summary</span>}
        </div>
        {analysis.signalNote && <p className="body-muted text-xs leading-relaxed mt-4">{analysis.signalNote}</p>}
        {analysis.modelInfo && <p className="body-muted text-xs leading-relaxed mt-2">Measured on the server with {analysis.modelInfo.modelName}, version {analysis.modelInfo.modelVersion}.</p>}
        {aiUseResultLines(analysis.aiUse).length > 0 && (
          <ul className="mt-3 flex flex-col gap-1" data-testid="text-ai-use-lines">
            {aiUseResultLines(analysis.aiUse).map((line) => (
              <li key={line} className="body-muted text-xs leading-relaxed">{line}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="panel panel-padded">
        <div className="flex items-center gap-2"><Gauge size={18} style={{ color: '#3eb49c' }} /><div className="eyebrow">What we noticed</div></div>
        <p className="text-base leading-relaxed mt-5" data-testid="text-observation">{analysis.observation ?? 'No interpretation was saved for this observation.'}</p>
        <div className="video-meta mt-7"><div className="video-icon"><FileVideo size={16} /></div><div><div className="font-semibold text-sm">{analysis.fileName}</div><div className="body-muted text-xs mt-1">{formatDuration(analysis.durationSeconds)} · {analysis.demo ? 'Sample pet' : pet?.name ?? 'Pet'}</div></div></div>
      </div>
    </div>

    <PipelineVisual analysis={analysis} />
    {/* Per-frame pose tracks are not stored; avoid implying that aggregate mean landmarks are frame-synchronized. */}

    {factors && (
      <section id="factor-scores" className="panel panel-padded mt-5 stagger-3 telemetry-card">
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
      <section className="panel panel-padded mt-5 stagger-3">
        <div className="flex items-center gap-2"><Ruler size={17} style={{ color: '#3eb49c' }} /><div className="eyebrow">Raw measurements</div></div>
        <p className="body-muted text-sm mt-3 max-w-2xl">The values the pipeline measured, before any interpretation.</p>
        <div className="measure-grid mt-5">
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Frames read</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.frameCount, '', 0)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Measured length</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.durationSeconds, 's', 2)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Mean frame motion</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.motionMean, '', 4)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Motion variation</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.motionStd, '', 4)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Frame Motion Coverage</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(typeof measurements.motionCoverage === 'number' ? measurements.motionCoverage * 100 : undefined, '%', 0)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Front strides</div><div className="font-mono font-medium text-lg mt-1">{formatStrideCounts(measurements.strides?.frontLeft?.strideCount, measurements.strides?.frontRight?.strideCount)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Rear strides</div><div className="font-mono font-medium text-lg mt-1">{formatStrideCounts(measurements.strides?.rearLeft?.strideCount, measurements.strides?.rearRight?.strideCount)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Front symmetry</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.limbSymmetry?.front)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Rear symmetry</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.limbSymmetry?.rear)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Front stride length</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.strideLengthBodyLengths?.front, ' body lengths')}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Rear stride length</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.strideLengthBodyLengths?.rear, ' body lengths')}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Cadence</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.cadenceStridesPerMinute, ' / min', 1)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Stride regularity</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.strideTimeCv)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Head vertical asymmetry</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.headBobAsymmetry)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Pelvis vertical asymmetry</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.pelvisAsymmetry)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90" title="Fraction of analyzed frames with an accepted dog detection. The detector checks every fifth frame; skipped frames are not inferred.">Observed dog detections</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(typeof measurements.subject?.dogFramesShare === 'number' ? measurements.subject.dogFramesShare * 100 : undefined, '%', 0)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Stride symmetry</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.strideSymmetry)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Asymmetry</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(analysis.asymmetryPercent, '%', 2)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Hip stability</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(measurements.hipStability)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Pose confidence</div><div className="font-mono font-medium text-lg mt-1">{formatMeasure(analysis.confidence, '%', 1)}</div></div>
          <div className="soft-note p-3"><div className="text-xs font-bold uppercase tracking-wider text-slate-400/90">Confident frames</div><div className="font-mono font-medium text-lg mt-1">{formatPoseFrames(analysis.framesUsed, analysis.framesTotal)}</div></div>
        </div>
        {(measurements.notMeasuredReasons ?? []).length > 0 && (
          <ul className="body-muted text-sm mt-4 flex flex-col gap-1" data-testid="text-not-measured-reasons">
            {measurements.notMeasuredReasons?.map((reason) => <li key={reason}>Not measured: {reason}</li>)}
          </ul>
        )}
      </section>
    )}

    <section className="soft-note p-5 mt-5 stagger-3 flex gap-3 items-start"><CircleAlert size={19} style={{ color: '#3794a4', flexShrink: 0 }} /><div><h2 className="font-bold text-sm">Important limitations</h2><p className="body-muted text-sm leading-relaxed mt-2" data-testid="text-limitations">{analysis.limitations ?? SAFETY_DISCLAIMER}</p></div></section>
    <p className="body-muted text-[11px] mt-6 flex items-center gap-2"><Info size={13} /> Compare observations over time, and share concerns with a veterinary professional.</p>
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
    return <div className="page-frame"><div className="panel panel-padded text-center max-w-lg mx-auto mt-16"><CircleAlert size={28} className="mx-auto" style={{ color: '#ff8b84' }} /><h1 className="display-title text-3xl mt-5">That observation moved on.</h1><p className="body-muted mt-3">It may have been removed from local storage.</p><Link href="/history" className="btn-primary mt-6" data-testid="link-return-history">Back to history</Link></div></div>;
  }
  return <div className="page-frame max-w-5xl">
    <div className="flex flex-wrap justify-between items-end gap-5 stagger"><div><div className="eyebrow">Your local notebook</div><h1 className="display-title text-5xl mt-3">History, not<br /><span style={{ color: '#3eb49c' }}>a verdict.</span></h1><p className="body-muted mt-4 max-w-md leading-relaxed">A dated trail of observations to help you notice patterns and ask better questions.</p></div><Link href="/analyze" className="btn-primary" data-testid="link-history-new-analysis"><FileVideo size={16} /> New analysis</Link></div>
    <div className="flex items-center gap-2 body-muted text-xs mt-8"><CalendarDays size={14} /> {analyses.length} saved observation{analyses.length === 1 ? '' : 's'} on this device</div>
    <TrendPanel analyses={analyses} />
    <div className="mt-4 stagger-2"><AnalysisList analyses={analyses} pets={pets} /></div>
    <div className="soft-note p-4 mt-5 text-xs leading-relaxed"><Info size={14} className="inline mr-2" /> Results are intentionally cautious. A high or low score is not a medical conclusion.</div>
  </div>;
}
