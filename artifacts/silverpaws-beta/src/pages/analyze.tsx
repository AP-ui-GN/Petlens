import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, CircleAlert, FileVideo, LockKeyhole, PawPrint, Play, RotateCcw } from 'lucide-react';
import { Link, useLocation } from 'wouter';
import { toast } from 'sonner';
import LocationSpecialistCard from '@/components/LocationSpecialistCard';
import VideoFrameScrubber from '@/components/VideoFrameScrubber';
import ProductTour from '@/components/ProductTour';
import { findBaseline, toAnalysisRecord, type Analysis, type Pet } from '@/lib/storage';
import { checkClip, describeAnalysisError, MAX_UPLOAD_MB, requestAnalysis } from '@/lib/analysis-api';
import { formatDuration } from '@/lib/format';
import { observationFromResult } from '@/lib/saved-observation';
import { createSampleAnalysis } from '@/lib/sample-analysis';

type Props = {
  pets: Pet[];
  analyses: Analysis[];
  addAnalysis: (analysis: Omit<Analysis, 'id' | 'createdAt'>) => Analysis;
  openDemoAnalysis: (analysis: Analysis, continueTour: boolean) => void;
};

type Phase = 'upload' | 'review' | 'processing' | 'done';

// The service does not report live phases. One status stays up for the whole
// request. A browser timer used to abort at four minutes and show this page as
// "Finalizing your observation" the whole time, including while pose was still
// loading. The service owns the deadline now.
const PROCESSING_STATUS = 'Measuring this clip';

export default function Analyze({ pets, analyses, addAnalysis, openDemoAnalysis }: Props) {
  const [, setLocation] = useLocation();
  const [petId, setPetId] = useState(pets[0]?.id ?? '');
  const [file, setFile] = useState<File | null>(null);
  const [duration, setDuration] = useState(0);
  const [showDurationWarning, setShowDurationWarning] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');
  const [source, setSource] = useState('');
  const [license, setLicense] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [phase, setPhase] = useState<Phase>('upload');
  const [showTour, setShowTour] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  // Drop an in-flight request if the user navigates away mid-analysis.
  useEffect(() => () => requestRef.current?.abort(), []);

  useEffect(() => {
    if (phase !== 'processing') return;
    const started = Date.now();
    const timer = window.setInterval(() => {
      const seconds = Math.floor((Date.now() - started) / 1000);
      setElapsed(seconds);
    }, 500);
    return () => window.clearInterval(timer);
  }, [phase]);

  const selectFile = (selected: File | undefined) => {
    if (!selected) return;
    setError('');

    if (selected.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setFile(null);
      setDuration(0);
      setShowDurationWarning(false);
      setPreviewUrl('');
      setPhase('upload');
      setError('File exceeds the 60 MB limit. Please select a shorter or lower-resolution clip.');
      if (inputRef.current) inputRef.current.value = '';
      return;
    }

    const immediateProblem = checkClip(selected, 0);
    if (immediateProblem) {
      setError(immediateProblem.message);
      return;
    }

    const url = URL.createObjectURL(selected);
    setFile(selected);
    setPreviewUrl(url);
    setPhase('review');
    setDuration(0);
    setShowDurationWarning(false);

    // Duration is read for display and for the length check. A container the
    // browser cannot measure is still accepted, because the pipeline measures it.
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.onloadedmetadata = () => {
      const seconds = Number.isFinite(video.duration) ? Math.round(video.duration) : 0;
      setDuration(seconds);
      setShowDurationWarning(Number.isFinite(video.duration) && video.duration > 15);
      const durationProblem = checkClip(selected, seconds);
      if (durationProblem) setError(durationProblem.message);
    };
    video.onerror = () => {
      setDuration(0);
      setShowDurationWarning(false);
    };
    video.src = url;
  };

  const reset = () => {
    requestRef.current?.abort();
    setFile(null);
    setDuration(0);
    setShowDurationWarning(false);
    setPreviewUrl('');
    setSource('');
    setLicense('');
    setSourceUrl('');
    setElapsed(0);
    setPhase('upload');
    setError('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const tryDemo = () => {
    requestRef.current?.abort();
    openDemoAnalysis(createSampleAnalysis(), showTour);
  };

  const runAnalysis = async () => {
    if (!file) return;

    const problem = checkClip(file, duration);
    if (problem) {
      setError(problem.message);
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setError('');
    setElapsed(0);
    setPhase('processing');

    const pet = pets.find((item) => item.id === petId);
    const baseline = findBaseline(analyses, petId);

    try {
      const result = await requestAnalysis({
        file,
        petName: pet?.name,
        previousOverall: baseline?.overallScore,
        previousPipeline: baseline?.pipeline,
        signal: controller.signal,
      });

      const record = toAnalysisRecord(result, {
        petId,
        fileName: file.name,
        durationSeconds: duration,
        source,
        license,
        sourceUrl,
      });
      const poseTimedOut = result.signalNote?.includes('Pose analysis exceeded its time limit') ?? false;
      if (poseTimedOut) {
        toast.info('Pose analysis timed out. Picture motion was measured. Stride length and symmetry were not measured.', {
          duration: 6000,
        });
      }
      // usedLlm false means the server kept its rule-based note. That note is
      // the saved observation. It is not replaced with a generic success line,
      // and an opencv-motion result stays labeled as picture motion.
      record.observation = observationFromResult(result);
      const saved = addAnalysis(record);

      setPhase('done');
      window.setTimeout(() => setLocation(`/history/${saved.id}`), 400);
    } catch (caught) {
      if (controller.signal.aborted) return;
      setError(describeAnalysisError(caught));
      setPhase('review');
    } finally {
      requestRef.current = null;
    }
  };

  const currentPet = pets.find((pet) => pet.id === petId);

  return (
    <div className={`page-frame max-w-4xl${showTour ? ' pb-60' : ''}`}>
      <div className="mt-6 flex flex-wrap items-start justify-between gap-4 stagger">
        <div>
          <h1 className="display-title text-3xl sm:text-4xl">Analyze how your dog walks</h1>
          <p className="max-w-2xl text-sm font-normal leading-relaxed text-slate-300/90 sm:text-base mt-3">Choose a video of your dog. We’ll look for patterns in your pet’s movement and give you an easy-to-understand observation.</p>
        </div>
        <button
          className="btn-secondary"
          onClick={() => setShowTour(true)}
          type="button"
          data-testid="button-replay-guided-tour"
        >
          Replay Guided Tour
        </button>
      </div>

      <div className="flex items-center gap-2 mt-9 text-xs font-semibold">
        {['Choose video', 'Review clip', 'Analysis'].map((label, index) => {
          const active = index === 0 ? phase === 'upload' : index === 1 ? phase === 'review' : phase === 'processing' || phase === 'done';
          const complete = (index === 0 && phase !== 'upload') || (index === 1 && (phase === 'processing' || phase === 'done'));
          return <div key={label} className="flex items-center gap-2"><span className={`grid h-7 w-7 place-items-center rounded-full ${active ? 'bg-[#1669aa] text-white ring-2 ring-[#5e17eb] shadow-[0_0_10px_rgba(94,23,235,0.4)]' : 'border border-slate-700 bg-slate-800 text-slate-300'}`}>{complete ? <Check size={14} /> : index + 1}</span><span className={active ? 'text-white' : 'text-slate-300'}>{label}</span>{index < 2 && <span className="w-8 h-px bg-border mx-1" />}</div>;
        })}
      </div>

      {phase === 'upload' && (
        <section className="mt-7 rounded-2xl border border-[#1669aa]/50 border-t-[#3794a4]/40 bg-[#0a2b3e] p-6 shadow-2xl backdrop-blur-md stagger-2">
          <div className="grid md:grid-cols-[1fr_220px] gap-7">
            <div>
              
              {pets.length
                ? <select id="pet-select" className="field-input border-[#1669aa]/60 text-white placeholder:text-slate-400" value={petId} onChange={(event) => setPetId(event.target.value)} data-testid="select-analysis-pet">{pets.map((pet) => <option value={pet.id} key={pet.id}>{pet.name} · {pet.species}</option>)}</select>
                : <div className="soft-note p-3 text-sm" data-testid="text-no-pet-warning">Create a pet profile before starting an analysis. <Link href="/pet" className="font-bold underline">Add a pet</Link></div>}
              <div id="tour-upload-dropzone" className="dotted-drop mt-6 min-h-[245px] flex flex-col items-center justify-center text-center p-7">
                
                <h2 className="font-bold text-lg mt-5">Please upload a side video of your dog walking.</h2>
                <p className="body-muted text-sm mt-2">Side view, steady camera. A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to 120 seconds.</p>
                <div className="flex flex-wrap justify-center gap-3 mt-5">
                  <button type="button" className="btn-secondary" onClick={() => inputRef.current?.click()} disabled={!pets.length} data-testid="button-choose-video">Choose video</button>
                  <button id="try-sample-btn" type="button" className="btn-quiet scroll-mt-20 font-semibold text-[#3eb49c] transition-colors hover:text-white" onClick={tryDemo} data-testid="button-try-demo">Try Sample Dog Walk</button>
                </div>
                <p className="body-muted text-xs mt-3">Click 'Try Sample Dog Walk' below to run a sample movement tracking test.</p>
                <input ref={inputRef} className="hidden" type="file" accept="video/*" onChange={(event) => selectFile(event.target.files?.[0])} data-testid="input-walking-video" />
              </div>
              {error && <div className="text-sm mt-3 flex items-center gap-2" style={{ color: '#ff8b84' }} role="alert" data-testid="text-upload-error"><CircleAlert size={15} />{error}</div>}
            </div>
            <div className="soft-note p-4 h-fit">
              <LockKeyhole size={17} />
              <h3 className="font-bold text-sm mt-3">Sent only for analysis</h3>
              <p className="body-muted text-xs leading-relaxed mt-2">The clip is sent to the PetLens analysis service and deleted right after. Only the numbers and summary are saved in your current browser.</p>
            </div>
          </div>
        </section>
      )}

      {phase === 'review' && file && (
        <section className="panel panel-padded mt-7 stagger-2">
          <div className="flex justify-between items-start gap-4"><div><div className="eyebrow">Step two · check your clip</div><h2 className="display-title text-3xl mt-2">Looks ready to read.</h2></div><button className="btn-quiet" onClick={reset} data-testid="button-replace-video"><RotateCcw size={15} /> Replace</button></div>
          <div className="grid md:grid-cols-[1.1fr_.9fr] gap-7 mt-7">
            <div className="rounded-2xl overflow-hidden aspect-video bg-[#0a4267] flex items-center justify-center relative">
              {previewUrl ? <video src={previewUrl} controls className="w-full h-full object-contain" data-testid="video-preview" /> : <FileVideo size={42} style={{ color: '#3eb49c' }} />}
              {!previewUrl && <div className="absolute inset-0 grid place-items-center"><Play size={25} /></div>}
            </div>
            <div>
              <div className="video-meta"><div className="video-icon"><FileVideo size={16} /></div><div className="min-w-0"><div className="font-semibold text-sm truncate">{file.name}</div><div className="body-muted text-xs mt-1">{duration ? formatDuration(duration) : 'Duration will be measured'} · {Math.round(file.size / 1024)} KB</div></div></div>
              {showDurationWarning && (
                <div className="text-sm mt-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-900" role="status" data-testid="text-duration-warning">
                  Clips over 15 seconds take longer to process. For optimal analysis, use a 5–15 second clip.
                </div>
              )}
              <div className="mt-6"><label className="field-label" htmlFor="pet-select-review">Pet</label><select id="pet-select-review" className="field-input" value={petId} onChange={(event) => setPetId(event.target.value)} data-testid="select-review-pet">{pets.map((pet) => <option value={pet.id} key={pet.id}>{pet.name}</option>)}</select></div>
               <div className="soft-note p-4 mt-6">
                 <div className="eyebrow">Optional sharing context</div>
                 <p className="body-muted text-xs leading-relaxed mt-2">Add attribution details if this clip came from a shared library or another source. Leave these blank for a private local video.</p>
                 <div className="mt-4">
                   <label className="field-label" htmlFor="analysis-source">Source</label>
                   <input id="analysis-source" className="field-input" value={source} onChange={(event) => setSource(event.target.value)} placeholder="e.g. Personal video or test library" data-testid="input-analysis-source" />
                 </div>
                 <div className="mt-4">
                   <label className="field-label" htmlFor="analysis-license">License</label>
                   <input id="analysis-license" className="field-input" value={license} onChange={(event) => setLicense(event.target.value)} placeholder="e.g. CC BY 4.0 or permission granted" data-testid="input-analysis-license" />
                 </div>
                 <div className="mt-4">
                   <label className="field-label" htmlFor="analysis-source-url">Source link</label>
                   <input id="analysis-source-url" type="url" className="field-input" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://..." data-testid="input-analysis-source-url" />
                 </div>
               </div>
              {error && <div className="text-sm mt-4 flex items-start gap-2" style={{ color: '#ff8b84' }} role="alert" data-testid="text-analysis-error"><CircleAlert size={15} className="mt-[2px] shrink-0" />{error}</div>}
              <button className="btn-primary w-full mt-6" onClick={runAnalysis} disabled={!petId} data-testid="button-run-analysis">Run analysis <ArrowRight size={15} /></button>
              <p className="body-muted text-[11px] leading-relaxed mt-4">The result describes visible movement only. It is not a diagnosis and should never replace veterinary advice.</p>
            </div>
          </div>
        </section>
      )}

      {phase === 'processing' && (
        <>
        <section className="panel panel-padded mt-7 stagger-2 text-center max-w-2xl mx-auto" aria-busy="true">
          
          <div className="eyebrow mt-7">Analysis in progress</div>
          <h2 className="display-title text-3xl mt-2" data-testid="text-processing-stage">{PROCESSING_STATUS}</h2>
          <p className="body-muted text-sm mt-3">This page waits while the analysis service is still working.</p>
          <div className="progress-track progress-indeterminate mt-8" role="progressbar" aria-label="Analyzing clip" />
          <div className="text-xs body-muted mt-3"><span className="font-mono">{elapsed}s</span> elapsed · a longer clip takes longer to measure</div>
          <p className="body-muted mt-2 text-xs">Progress is not reported live. If pose runs past the service limit, the motion measurements already taken are kept. Stride values that were not measured stay unmeasured.</p>
          <button
            className="btn-quiet mt-3"
            onClick={() => {
              requestRef.current?.abort();
              requestRef.current = null;
              setError('Analysis cancelled.');
              setPhase('review');
            }}
            type="button"
            data-testid="button-cancel-analysis"
          >
            Cancel analysis
          </button>
        </section>
        {previewUrl && <VideoFrameScrubber videoUrl={previewUrl} />}
        </>
      )}

      {phase === 'done' && (
        <section className="panel panel-padded mt-7 text-center"><h2 className="display-title text-3xl mt-5">Your note is ready.</h2><p className="body-muted text-sm mt-2">Opening the saved observation for {currentPet?.name ?? 'your pet'}…</p></section>
      )}
      <div className="mt-5" id="vet-summary-export">
        <LocationSpecialistCard />
      </div>
      {phase === 'review' && <div className="flex items-center gap-2 body-muted text-xs mt-6"><PawPrint size={14} /> You’re in control — review the clip before anything runs.</div>}
      {showTour && <ProductTour onComplete={() => setShowTour(false)} />}
    </div>
  );
}
