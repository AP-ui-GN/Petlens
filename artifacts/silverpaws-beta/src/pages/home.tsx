import { ArrowRight, CalendarDays, ChevronRight, CircleHelp, FileVideo, HeartHandshake, PawPrint, Sparkles } from 'lucide-react';
import { Link } from 'wouter';
import MobilityTrendTracker from '@/components/MobilityTrendTracker';
import { displayScore, type Analysis, type Pet } from '@/lib/storage';
import { formatRelative } from '@/lib/format';

type Props = { pets: Pet[]; analyses: Analysis[] };

export default function Home({ pets, analyses }: Props) {
  const pet = pets[0];
  const latest = analyses.find((item) => item.status === 'complete');
  const latestScore = latest ? displayScore(latest) : null;
  const recent = analyses.slice(0, 3);

  if (!pet) {
    return (
      <div className="page-frame">
        <section className="panel panel-padded text-center max-w-xl mx-auto mt-16">
          <div className="empty-art mx-auto mb-5"><PawPrint size={28} /></div>
          <div className="eyebrow">First, a little context</div>
          <h1 className="display-title text-4xl mt-3">Tell us who you’re watching over.</h1>
          <p className="body-muted mt-3 leading-relaxed">A pet profile helps keep each walking observation connected to the right companion.</p>
          <Link href="/pet" className="btn-primary mt-7" data-testid="link-create-first-pet">Create pet profile <ArrowRight size={16} /></Link>
        </section>
      </div>
    );
  }

  return (
    <div className="page-frame">
      <div className="flex flex-wrap justify-between gap-5 items-end stagger">
        <div>
          <div className="eyebrow font-sans text-[11px] font-bold uppercase tracking-wider text-slate-400/90">A quiet read on movement</div>
          <h1 className="display-title text-4xl sm:text-5xl mt-3">Good morning,<br /><span className="accent-label">{pet.name}.</span></h1>
          <p className="body-muted mt-4 max-w-md leading-relaxed">One short walk can become a useful note to bring into a bigger conversation.</p>
        </div>
        <Link href="/analyze" className="btn-primary mb-1" data-testid="link-start-analysis"><Sparkles size={16} /> Start an analysis</Link>
      </div>

      <section className="grid md:grid-cols-[1.1fr_.9fr] gap-5 mt-10 stagger-2">
        <div className="panel panel-padded relative overflow-hidden">
          <div className="absolute -right-4 -top-8 text-[170px] leading-none opacity-10" style={{ color: '#3794a4' }}>◒</div>
          <div className="relative">
            <div className="flex items-center gap-4">
              <div className="pet-orb">{pet.name.slice(0, 2).toUpperCase()}</div>
              <div>
                <div className="eyebrow font-sans text-[11px] font-bold uppercase tracking-wider text-slate-400/90">Selected companion</div>
                <h2 className="font-sans font-bold text-xl text-white tracking-normal leading-snug mt-1">{pet.name}</h2>
                <p className="body-muted text-sm mt-1">{pet.species}{pet.age ? ` · ${pet.age} years` : ''}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-8 max-w-sm">
              <div><div className="body-muted text-xs font-bold uppercase tracking-wider">Last read</div><div className="font-semibold text-sm mt-1">{latest ? formatRelative(latest.createdAt) : 'Not yet'}</div></div>
              <div><div className="body-muted text-xs font-bold uppercase tracking-wider">On device</div><div className="font-semibold text-sm mt-1"><span className="font-mono">{analyses.length}</span> observation{analyses.length === 1 ? '' : 's'}</div></div>
            </div>
          </div>
        </div>
        <div className="panel panel-padded flex flex-col justify-between">
          <div className="flex justify-between gap-4">
            <div><div className="eyebrow font-sans text-[11px] font-bold uppercase tracking-wider text-slate-400/90">Latest mobility note</div><h2 className="font-sans font-bold text-xl text-white tracking-normal leading-snug mt-2">{latest ? 'A steady picture' : 'Nothing to compare yet'}</h2></div>
            <HeartHandshake size={25} style={{ color: '#3eb49c' }} />
          </div>
          {latest ? (
            <>
              <p className="body-muted text-sm leading-relaxed mt-3">{latest.observation}</p>
              {latestScore !== null && (
                <div className="mt-7">
                  <div className="flex justify-between items-center text-xs mb-2"><span className="font-semibold">Overall indicator</span><span className="font-mono">{latestScore}/100</span></div>
                  <div className="progress-track"><div className="progress-fill" style={{ width: `${latestScore}%` }} /></div>
                </div>
              )}
              <Link href={`/history/${latest.id}`} className="btn-quiet self-start mt-5 -ml-3" data-testid={`link-view-latest-${latest.id}`}>Open observation <ArrowRight size={15} /></Link>
            </>
          ) : (
            <div className="mt-3"><p className="body-muted text-sm leading-relaxed">Upload a walking video to create your first educational observation.</p><Link href="/analyze" className="btn-primary mt-5" data-testid="link-upload-first">Upload a walk <ArrowRight size={15} /></Link></div>
          )}
        </div>
      </section>

      <MobilityTrendTracker analyses={analyses} petId={pet.id} />

      <section className="grid lg:grid-cols-[1.2fr_.8fr] gap-5 mt-5 stagger-3">
        <div className="panel panel-padded">
          <div className="flex items-center justify-between mb-3"><div><div className="eyebrow font-sans text-[11px] font-bold uppercase tracking-wider text-slate-400/90">Recent analyses</div><h2 className="font-sans font-bold text-xl text-white tracking-normal leading-snug mt-2">Your observation trail</h2></div><Link href="/history" className="btn-quiet" data-testid="link-see-all-history">See all <ChevronRight size={15} /></Link></div>
          {recent.length ? recent.map((analysis) => (
            <Link href={`/history/${analysis.id}`} key={analysis.id} className="analysis-row no-underline" data-testid={`link-analysis-${analysis.id}`}>
              <div className="flex gap-3 items-center min-w-0"><div className="video-icon"><FileVideo size={16} /></div><div className="min-w-0"><div className="font-semibold text-sm truncate">{analysis.fileName}</div><div className="body-muted text-xs mt-1"><span className={`status-dot status-${analysis.status}`} />{formatRelative(analysis.createdAt)} · {analysis.status === 'complete' ? 'Observation ready' : 'Processing'}</div></div></div>
              <div className="text-right"><div className="font-bold text-sm">{displayScore(analysis) === null ? 'Not scored' : `${displayScore(analysis)}/100`}</div><div className="body-muted text-[10px] mt-1">overall</div></div>
            </Link>
          )) : <div className="body-muted text-sm py-8 text-center">Your completed observations will collect here.</div>}
        </div>
        <div className="soft-note p-5">
          <CircleHelp size={20} style={{ color: '#3794a4' }} />
          <h2 className="font-sans font-bold text-xl text-white tracking-normal leading-snug mt-4">How to get a useful clip</h2>
          <ul className="body-muted text-sm leading-relaxed mt-3 space-y-2 list-disc pl-4"><li>Keep the camera low and level.</li><li>Capture a few steps from the side.</li><li>Let your pet move naturally.</li></ul>
          <div className="flex items-center gap-2 mt-5 text-xs font-semibold"><CalendarDays size={14} /> Repeat over time, not just once.</div>
        </div>
      </section>
      <p className="body-muted text-[11px] mt-7 flex items-center gap-2"><CircleHelp size={13} /> PetLens AI is experimental and educational. It does not diagnose injury or illness.</p>
    </div>
  );
}