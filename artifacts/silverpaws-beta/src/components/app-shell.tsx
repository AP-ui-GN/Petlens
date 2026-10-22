import { Activity, ClipboardList, Plus, ShieldAlert, UserRound } from 'lucide-react';
import { type ReactNode } from 'react';
import { Link, useLocation } from 'wouter';
import { EMERGENCY_NOTE, SAFETY_DISCLAIMER } from '@/lib/disclaimers';

const items = [
  { href: '/', label: 'Overview', icon: Activity },
  { href: '/analyze', label: 'New analysis', icon: Plus },
  { href: '/history', label: 'History', icon: ClipboardList },
  { href: '/pet', label: 'Pet profile', icon: UserRound },
  { href: '/ai-use', label: 'AI use', icon: ShieldAlert },
];

function NavItems({ mobile = false }: { mobile?: boolean }) {
  const [location] = useLocation();
  return (
    <nav className={mobile ? 'mobile-bottom-nav' : 'flex flex-col gap-2 mt-14'}>
      {items.map(({ href, label, icon: Icon }) => {
        const active = href === '/' ? location === '/' : location.startsWith(href);
        return (
          <Link
            href={href}
            key={href}
            className={`nav-link ${active ? 'active' : ''}`}
            data-testid={`link-${label.toLowerCase().replaceAll(' ', '-')}`}
          >
            <Icon size={17} strokeWidth={active ? 2.4 : 1.8} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="app-nav">
        <Link href="/" className="brand-lockup flex items-center gap-3 no-underline" data-testid="link-brand">
          <img src={`${import.meta.env.BASE_URL}petlens-dog-mark.png`} alt="PetLens analysis for dogs" className="brand-mark" />
          <span>
            <span className="brand-word block">PetLens</span>
            <span className="brand-sub block">analysis for dogs</span>
          </span>
        </Link>
        <NavItems />
        <div className="mt-auto">
          <div className="rounded-2xl p-4" style={{ background: 'rgba(255,255,255,.08)' }}>
            <div className="eyebrow" style={{ color: '#3eb49c' }}>Browser beta</div>
            <p className="text-xs leading-relaxed mt-2" style={{ color: 'rgba(230,247,251,.72)' }}>
              Your videos and observations stay on this device while testing.
            </p>
          </div>
          <div className="text-[10px] mt-5" style={{ color: 'rgba(230,247,251,.52)' }}>v0.3 · educational use</div>
        </div>
      </aside>
      <div className="content-wrap">
        <header className="mobile-header">
          <Link href="/" className="flex items-center gap-3 no-underline" data-testid="link-mobile-brand">
            <img src={`${import.meta.env.BASE_URL}petlens-dog-mark.png`} alt="PetLens analysis for dogs" className="brand-mark" style={{ width: 36, height: 36 }} />
            <span>
              <span className="brand-word block">PetLens</span>
              <span className="brand-sub block">analysis for dogs</span>
            </span>
          </Link>
          <span className="eyebrow">Beta</span>
        </header>
        <main className="page-content">
          <img
            src={`${import.meta.env.BASE_URL}petlens-dog-mark.png`}
            alt=""
            aria-hidden="true"
            className="page-watermark"
          />
          {children}
        </main>
        <footer className="page-frame pt-0" data-testid="text-safety-disclaimer">
          <div className="soft-note p-4 text-xs leading-relaxed flex gap-3 items-start">
            <ShieldAlert size={16} className="shrink-0 mt-[1px]" />
            <span>
              {SAFETY_DISCLAIMER}
              <span className="block mt-2 font-semibold">{EMERGENCY_NOTE}</span>
            </span>
          </div>
        </footer>
        <NavItems mobile />
      </div>
    </div>
  );
}