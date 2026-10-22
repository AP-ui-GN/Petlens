import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Printer, X } from 'lucide-react';
import { displayScore, type Analysis, type Pet } from '@/lib/storage';
import { SAFETY_DISCLAIMER } from '@/lib/disclaimers';

type VetReportModalProps = {
  analysis: Analysis;
  pet?: Pet;
  onClose: () => void;
};

type ReportFactor = {
  key: keyof NonNullable<Analysis['factors']>;
  label: string;
};

const REPORT_FACTORS: ReportFactor[] = [
  { key: 'movementConsistency', label: 'Movement consistency' },
  { key: 'symmetry', label: 'Stride symmetry' },
  { key: 'mobility', label: 'Mobility' },
  { key: 'activity', label: 'Activity coverage' },
  { key: 'historicalChange', label: 'Baseline change' },
];

function formatValue(value: number | null | undefined, suffix = '', digits = 1) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not measured';
  return `${Number(value.toFixed(digits))}${suffix}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'Date unavailable';
  return new Intl.DateTimeFormat('en', { month: 'long', day: 'numeric', year: 'numeric' }).format(date);
}

function getPipelineName(analysis: Analysis) {
  if (analysis.modelInfo?.modelName) {
    return `${analysis.modelInfo.modelName}${analysis.modelInfo.modelVersion ? ` ${analysis.modelInfo.modelVersion}` : ''}`;
  }
  if (analysis.pipeline === 'movenet') return 'MoveNet Thunder v2';
  if (analysis.pipeline === 'opencv-motion') return 'Picture motion analysis';
  return 'Not recorded';
}

export default function VetReportModal({ analysis, pet, onClose }: VetReportModalProps) {
  const overallScore = displayScore(analysis);
  const measurements = analysis.measurements;
  const poseFrames = typeof analysis.framesUsed === 'number' && typeof analysis.framesTotal === 'number'
    ? `${analysis.framesUsed} / ${analysis.framesTotal}`
    : 'Not measured';
  const notes = [
    analysis.observation,
    ...(analysis.qualityNotes ?? []),
    analysis.signalNote,
    analysis.concerningChange
      ? 'The saved telemetry indicates a change from baseline. Consider discussing the comparison with a veterinary professional.'
      : undefined,
  ].filter((note): note is string => Boolean(note?.trim()));

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return createPortal(
    <div className="vet-report-print-root fixed inset-0 z-[1000001] flex items-center justify-center bg-slate-950/80 p-4 print:static print:block print:bg-white print:p-0">
      <section
        aria-labelledby="vet-report-title"
        aria-modal="true"
        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl print:fixed print:inset-0 print:block print:max-h-none print:max-w-none print:overflow-visible print:rounded-none print:border-none print:shadow-none"
        role="dialog"
      >
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-700 px-5 py-3 print:hidden">
          <h2 className="text-base font-bold text-white" id="vet-report-title">Movement report preview</h2>
          <div className="flex items-center gap-2">
            <button className="btn-primary" onClick={() => window.print()} type="button">
              <Printer size={15} /> Print / Export PDF
            </button>
            <button aria-label="Close report preview" className="btn-quiet" onClick={onClose} type="button">
              <X size={18} />
              <span className="sr-only">Close</span>
            </button>
          </div>
        </header>

        <div className="min-h-0 overflow-y-auto p-5 print:overflow-visible print:p-0">
          <article className="vet-report-page mx-auto min-h-[10.5in] max-w-[8.5in] bg-white p-8 font-sans text-slate-900 shadow-xl print:min-h-0 print:max-w-none print:p-0 print:shadow-none">
            <div className="border-b-4 border-[#0a4267] pb-5">
              <div className="text-xs font-bold uppercase tracking-[0.16em] text-[#1669aa]">Pet movement observation report</div>
              <h1 className="mt-2 text-2xl font-extrabold leading-tight" id="vet-report-document-title">
                SILVER PAWS AI — Movement Observation Summary
              </h1>
              <div className="mt-4 flex flex-wrap justify-between gap-2 text-xs text-slate-600">
                <span>Reference: {analysis.id.slice(0, 12).toUpperCase()}</span>
                <span>Report date: {formatDate(new Date().toISOString())}</span>
              </div>
            </div>

            <section className="mt-5">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">Analysis demographics</h2>
              <div className="mt-2 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-4 print:grid-cols-4">
                {[
                  ['Pet name', pet?.name ?? 'Not provided'],
                  ['Source video', analysis.fileName || 'Not provided'],
                  ['Pipeline model', getPipelineName(analysis)],
                  ['Analysis status', analysis.status],
                ].map(([label, value]) => (
                  <div className="min-w-0 bg-slate-50 p-3" key={label}>
                    <div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</div>
                    <div className="mt-1 break-words text-xs font-semibold">{value}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-5 grid grid-cols-[1.15fr_1fr] gap-3">
              <div className="rounded-xl bg-[#0a4267] p-4 text-white">
                <div className="text-xs font-semibold uppercase tracking-wide text-white/75">Overall movement indicator</div>
                <div className="mt-2 font-mono text-4xl font-bold">{overallScore === null ? 'Not scored' : `${overallScore}/100`}</div>
                <div className="mt-2 text-xs text-white/75">A clip-level educational indicator, not a diagnosis.</div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Stride asymmetry', formatValue(analysis.asymmetryPercent, '%')],
                  ['Pose confidence', formatValue(analysis.confidence, '%')],
                  ['Hip stability index', formatValue(measurements?.hipStability)],
                  ['Valid pose frames', poseFrames],
                ].map(([label, value]) => (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" key={label}>
                    <div className="text-[10px] font-semibold text-slate-500">{label}</div>
                    <div className="mt-1 font-mono text-sm font-semibold">{value}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-6">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">Factor breakdown</h2>
              <div className="mt-3 space-y-3">
                {REPORT_FACTORS.map(({ key, label }) => {
                  const score = analysis.factors?.[key];
                  const isMeasured = typeof score === 'number' && Number.isFinite(score);
                  const boundedScore = isMeasured ? Math.max(0, Math.min(100, score)) : 0;
                  return (
                    <div className="grid grid-cols-[9rem_1fr_4rem] items-center gap-3 text-xs" key={key}>
                      <span className="font-semibold">{label}</span>
                      <div aria-label={`${label}: ${isMeasured ? `${score}/100` : 'Not measured'}`} className="h-2 overflow-hidden rounded-full bg-slate-200" role="img">
                        {isMeasured && <div className="h-full rounded-full bg-[#3794a4]" style={{ width: `${boundedScore}%` }} />}
                      </div>
                      <span className="text-right font-mono">{isMeasured ? `${score}/100` : 'N/M'}</span>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="mt-6">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-700">Plain-language observations</h2>
              <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-700">
                {notes.length > 0
                  ? notes.map((note, index) => <li key={`${index}-${note}`}>{note}</li>)
                  : <li>No plain-language interpretation was saved for this observation.</li>}
                {analysis.lowConfidence && <li>Pose confidence was limited; unavailable measurements should not be interpreted as zero.</li>}
              </ul>
            </section>

            <div className="mt-6 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs leading-relaxed text-slate-700">
              <strong className="text-slate-900">Important limitations.</strong>{' '}
              This report contains observational movement data from one video. It is not a diagnosis or a
              validated clinical assessment and cannot replace a veterinary examination. Interpret any
              available measurements in context; a missing value means not measured, not zero. {SAFETY_DISCLAIMER}
            </div>
          </article>

          <article className="vet-report-page mx-auto mt-5 min-h-[10.5in] max-w-[8.5in] bg-white p-8 font-sans text-slate-900 shadow-xl print:mt-0 print:min-h-0 print:max-w-none print:p-0 print:shadow-none">
            <div className="flex items-start justify-between border-b border-slate-300 pb-4">
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.16em] text-[#1669aa]">Supplemental telemetry</div>
                <h2 className="mt-2 text-xl font-extrabold">Measurement details &amp; interpretation notes</h2>
              </div>
              <div className="text-right text-xs text-slate-500">Reference {analysis.id.slice(0, 12).toUpperCase()}</div>
            </div>

            <section className="mt-6">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">Recorded clip measurements</h3>
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 print:grid-cols-3">
                {[
                  ['Clip duration', formatValue(analysis.durationSeconds, ' s', 2)],
                  ['Frames read', formatValue(measurements?.frameCount, ' frames', 0)],
                  ['Frame motion coverage', formatValue(typeof measurements?.motionCoverage === 'number' ? measurements.motionCoverage * 100 : undefined, '%')],
                  ['Hip stability', formatValue(measurements?.hipStability)],
                  ['Stride symmetry score', formatValue(analysis.strideSymmetryScore, '/100')],
                  ['Detection confidence', formatValue(analysis.confidence, '%')],
                ].map(([label, value]) => (
                  <div className="rounded-lg border border-slate-200 p-3" key={label}>
                    <div className="text-[10px] font-semibold text-slate-500">{label}</div>
                    <div className="mt-1 font-mono text-sm font-semibold">{value}</div>
                  </div>
                ))}
              </div>
            </section>

            {analysis.signalNote && (
              <section className="mt-6 rounded-lg bg-slate-50 p-4">
                <h3 className="text-sm font-bold">Signal quality note</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-700">{analysis.signalNote}</p>
              </section>
            )}

            <section className="mt-6 rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-bold">Interpretation boundaries</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-700">
                {analysis.limitations ?? 'This observation describes visible movement in one clip. It cannot explain why a movement pattern occurred or rule out pain or injury.'}
              </p>
              <p className="mt-3 text-sm leading-relaxed text-slate-700">
                Scores and factor values summarize the available telemetry. They should not be used alone to make treatment decisions.
                Compare like-for-like clips over time and assess alongside history and physical examination.
              </p>
            </section>
            <footer className="mt-10 border-t border-slate-200 pt-3 text-[10px] text-slate-500">
              SILVER PAWS AI · Movement Observation Summary · Page 2 of 2
            </footer>
          </article>
        </div>
      </section>
    </div>,
    document.body,
  );
}
