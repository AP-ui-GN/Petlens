import { ArrowRight, ChartNoAxesCombined, ChevronRight, FileVideo, HeartHandshake } from 'lucide-react';
import { Link } from 'wouter';
import { displayScore, type Analysis, type Pet } from '@/lib/storage';
import { formatRelative } from '@/lib/format';
import { latestNoteHeadline } from '@/lib/headline';

type Props = {
  pets: Pet[];
  analyses: Analysis[];
  clearSampleWalks: () => void;
};

export default function Home({ pets, analyses, clearSampleWalks }: Props) {
  const pet = pets[0];
  const petAnalyses = pet ? analyses.filter((item) => item.petId === pet.id) : [];
  const latest = petAnalyses.find((item) => item.status === 'complete');
  const latestScore = latest ? displayScore(latest) : null;
  const recent = petAnalyses.slice(0, 3);
  const sampleCount = analyses.filter((analysis) => analysis.sampleData).length;
  const latestHeadline = latestNoteHeadline(latest);

  if (!pet) {
    return (
      <div className="page-frame">
        <section className="panel panel-padded text-center max-w-xl mx-auto mt-16">
          <h1 className="display-title text-4xl mt-3">Tell us who you’re <span className="text-petlens-trim">watching</span> over.</h1>
          <p className="body-muted mt-3 leading-relaxed">A pet profile keeps each walking observation connected to the right pet.</p>
          <Link href="/pet" className="btn-primary mt-7" data-testid="link-create-first-pet">Create pet profile <ArrowRight size={16} /></Link>
        </section>
      </div>
    );
  }

  return (
    <div className="page-frame">
      <div className="flex flex-wrap justify-between gap-5 items-end stagger">
        <div>
          <h1 className="display-title text-4xl sm:text-5xl mt-3">Good morning,<br /><span className="accent-label">{pet.name}.</span></h1>
        </div>
      </div>

      <section className="grid md:grid-cols-[1.1fr_.9fr] gap-5 mt-10 stagger-2">
        <div className="panel panel-padded relative overflow-hidden">
          <div className="absolute -right-4 -top-8 text-[170px] leading-none opacity-10 text-petlens-teal">◒</div>
          <div className="relative">
            <div className="flex items-center gap-4">
              <div className="pet-orb">{pet.name.slice(0, 2).toUpperCase()}</div>
              <div>
                
                <h2 className="font-sans font-bold text-xl tracking-normal leading-snug mt-1">{pet.name}</h2>
                <p className="body-muted text-sm mt-1">{pet.species}{pet.age ? ` · ${pet.age} years` : ''}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-8 max-w-sm">
              <div><div className="body-muted text-xs font-bold uppercase tracking-wider">Last read</div><div className="font-semibold text-sm mt-1">{latest ? formatRelative(latest.createdAt) : 'Not yet'}</div></div>
              <div className="analytical-only"><div className="body-muted text-xs font-bold uppercase tracking-wider">On device</div><div className="font-semibold text-sm mt-1"><span className="font-mono">{petAnalyses.length}</span> observation{petAnalyses.length === 1 ? '' : 's'}</div></div>
            </div>
          </div>
        </div>
        <div className="panel panel-padded flex flex-col justify-between">
          <div className="flex justify-between gap-4">
            <div><h2 className="font-sans font-bold text-xl tracking-normal leading-snug mt-2">{latestHeadline}</h2></div>
            <HeartHandshake size={25} className="text-petlens-emerald" />
          </div>
          {latest ? (
            <>
              {latest.sampleData && <div className="eyebrow mt-4">Sample data</div>}
              <p className="body-muted text-sm leading-relaxed mt-3">{latest.observation}</p>
              {latestScore !== null && (
                <div className="analytical-only mt-7">
                  <div className="flex justify-between items-center text-xs mb-2"><span className="font-semibold">Overall indicator</span><span className="font-mono">{latestScore}/100</span></div>
                  <div className="progress-track"><div className="progress-fill" style={{ width: `${latestScore}%` }} /></div>
                </div>
              )}
              <Link href={`/history/${latest.id}`} className="btn-quiet self-start mt-5 -ml-3" data-testid={`link-view-latest-${latest.id}`}>Open observation <ArrowRight size={15} /></Link>
            </>
          ) : (
            <div className="mt-3"><p className="body-muted text-sm leading-relaxed">Upload a walking video to create your first educational observation.</p><Link href="/analyze" className="btn-primary mt-5" data-testid="link-upload-first">Upload your dog's walk <ArrowRight size={15} /></Link></div>
          )}
        </div>
      </section>

      <div className="analytical-only">
        <section className="panel panel-padded mt-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <ChartNoAxesCombined aria-hidden="true" className="mt-1 shrink-0 text-petlens-emerald" size={20} />
            <div>
              <h2 className="font-sans font-bold text-xl tracking-normal leading-snug">Walk-by-walk graphs</h2>
              <p className="body-muted mt-2 max-w-xl text-sm leading-relaxed">Compare movement scores across saved walks and review where scores improved or declined.</p>
            </div>
          </div>
          <Link className="btn-primary" href="/analytics" data-testid="link-home-analytics">Open analytics <ArrowRight size={15} /></Link>
        </section>
      </div>
      <section className="normal-mode-only panel panel-padded mt-5" data-testid="normal-mode-walk-summary">
        <div className="eyebrow">Your walk, in words</div>
        <h2 className="font-sans font-bold text-xl tracking-normal leading-snug mt-2">
          {latest ? `What we noticed about ${pet.name}` : `Get to know ${pet.name}'s walk`}
        </h2>
        {latest ? (
          <>
            <p className="leading-relaxed mt-4" data-testid="normal-mode-walk-observation">
              {latest.observation ?? 'No plain-language interpretation was saved for this video.'}
            </p>
            <p className="body-muted text-sm leading-relaxed mt-3">
              {latest.signalQuality === 'unusable'
                ? 'This video did not provide enough clear movement information for a reliable observation. Try filming from the side with your pet’s whole body in frame.'
                : latest.signalQuality === 'limited' || latest.lowConfidence
                  ? 'The video gave us only a partial view of movement, so treat this as a limited observation.'
                  : 'This describes movement visible in one video. It is not a diagnosis or a complete picture of your pet’s health.'}
            </p>
            {latest.qualityNotes && latest.qualityNotes.length > 0 && (
              <ul className="body-muted text-sm leading-relaxed mt-3 list-disc pl-5">
                {latest.qualityNotes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            )}
            <Link href={`/history/${latest.id}`} className="btn-quiet self-start mt-4 -ml-3" data-testid={`link-view-plain-language-${latest.id}`}>
              Read the full observation <ArrowRight size={15} />
            </Link>
          </>
        ) : (
          <>
            <p className="body-muted text-sm leading-relaxed mt-3">
              After you upload a walking video, you’ll see a written description of the movement visible in the clip here. It can help you notice patterns, but it can’t diagnose a health condition.
            </p>
            <Link href="/analyze" className="btn-primary mt-5" data-testid="link-upload-first-walk-summary">
              Upload a walking video <ArrowRight size={15} />
            </Link>
          </>
        )}
      </section>
      <section className="normal-mode-only soft-note p-5 mt-5" data-testid="normal-mode-trend-explainer">
        <div className="eyebrow">What repeated walks can show</div>
        <h2 className="font-sans font-bold text-xl tracking-normal leading-snug mt-2">A simple picture over time</h2>
        <p className="body-muted text-sm leading-relaxed mt-3">
          One video gives you a starting observation. As you add more walks, PetLens can compare the movement seen in each clip and show whether the pattern looks similar or has changed. In Analytical mode, those check-ins appear over time as a graph; Simple mode keeps the explanation in words.
        </p>
        <div className="rounded-xl border border-petlens-azure/20 bg-petlens-ink/20 p-4 mt-4">
          <div className="text-xs font-bold uppercase tracking-wider">Example of what it might say</div>
          <p className="body-muted text-sm leading-relaxed mt-2">
            “Across several walks, the movement observations look broadly similar. Keep adding occasional videos to build a clearer picture.”
          </p>
        </div>
        <p className="body-muted text-xs leading-relaxed mt-3">
          This is only an example, not a result about {pet.name}. A video-based movement trend is not a diagnosis, and some details may not be measurable in every clip.
        </p>
        {latest && (
          <div className="normal-mode-only mt-4" data-testid="simple-mode-history-interpretation">
            <div className="text-xs font-bold uppercase tracking-wider">About {pet.name}’s saved observations</div>
            <p className="body-muted text-sm leading-relaxed mt-2">
              {petAnalyses.length < 2
                ? 'One saved walk is a starting point. More videos, recorded in similar conditions, are needed before describing a pattern over time.'
                : 'Each saved video is one check-in. Comparing clips recorded in similar conditions can help show whether the visible movement pattern stays similar or changes.'}
            </p>
          </div>
        )}
      </section>

      <section className="mt-5 stagger-3">
        <div className="panel panel-padded">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3"><div><div className="eyebrow font-sans text-[11px] font-bold uppercase tracking-wider text-slate-400/90">Recent analyses</div><h2 className="font-sans font-bold text-xl tracking-normal leading-snug mt-2">Your observation trail</h2></div><div className="flex items-center gap-2">{sampleCount > 0 && <button type="button" className="btn-quiet" onClick={() => { if (window.confirm('Clear all generated sample walks? Your real video observations will not be changed.')) clearSampleWalks(); }} data-testid="button-home-clear-sample-walks">Clear all sample walks ({sampleCount})</button>}<Link href="/history" className="btn-quiet" data-testid="link-see-all-history">See all <ChevronRight size={15} /></Link></div></div>
          {recent.length ? recent.map((analysis) => (
            <Link href={`/history/${analysis.id}`} key={analysis.id} className="analysis-row no-underline" data-testid={`link-analysis-${analysis.id}`}>
              <div className="flex gap-3 items-center min-w-0"><div className="video-icon"><FileVideo size={16} /></div><div className="min-w-0"><div className="font-semibold text-sm truncate">{analysis.fileName}</div><div className="body-muted text-xs mt-1"><span className={`status-dot status-${analysis.status}`} />{analysis.sampleData ? 'Sample data · ' : ''}{formatRelative(analysis.createdAt)} · {analysis.status === 'complete' ? 'Observation ready' : 'Processing'}</div></div></div>
              <div className="analytical-only text-right"><div className="font-bold text-sm">{displayScore(analysis) === null ? 'Not scored' : `${displayScore(analysis)}/100`}</div><div className="body-muted text-[10px] mt-1">overall</div></div>
            </Link>
          )) : <div className="body-muted text-sm py-8 text-center">Your completed observations will collect here.</div>}
        </div>
      </section>

    </div>
  );
}