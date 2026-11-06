import { ChartNoAxesCombined, ClipboardList, House, Plus, UserRound } from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'wouter';

const items = [
  { href: '/', label: 'Home', icon: House },
  { href: '/analyze', label: 'New analysis', mobileLabel: 'Analyze', icon: Plus },
  { href: '/history', label: 'History', icon: ClipboardList },
  { href: '/analytics', label: 'Analytics', icon: ChartNoAxesCombined },
  { href: '/pet', label: 'Pet profile', mobileLabel: 'Pet', icon: UserRound },
];

type AppMode = 'analytical' | 'normal';
const APP_MODE_KEY = 'petlens:app-mode';
const ANALYTICAL_LOGO = `${import.meta.env.BASE_URL}gold-hexagonal-petlens-logo-Photoroom.png`;
const NORMAL_LOGO = `${import.meta.env.BASE_URL}red-petlens-logo-Photoroom.png`;

function getInitialMode(): AppMode {
  try {
    return window.localStorage.getItem(APP_MODE_KEY) === 'normal' ? 'normal' : 'analytical';
  } catch {
    return 'analytical';
  }
}

function ModeSwitch({ mode, onChange }: { mode: AppMode; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={mode === 'normal'}
      aria-label={mode === 'analytical' ? 'Switch to simple mode' : 'Switch to analytical mode'}
      onClick={onChange}
      className="mode-switch"
      data-testid="button-mode-switch"
    >
      <span className="mode-switch-label">{mode === 'analytical' ? 'Analytical mode' : 'Simple mode'}</span>
      <span className="mode-switch-track" aria-hidden="true"><span className="mode-switch-thumb" /></span>
    </button>
  );
}

function BrandMark({ mode, mobile = false }: { mode: AppMode; mobile?: boolean }) {
  return (
    <img
      key={mode}
      src={mode === 'normal' ? NORMAL_LOGO : ANALYTICAL_LOGO}
      alt=""
      aria-hidden="true"
      className={`brand-mark${mobile ? ' brand-mark-mobile' : ''}`}
      data-testid="brand-mark"
      data-mode={mode}
    />
  );
}

function ModeTransition({ from, to, onComplete }: { from: AppMode; to: AppMode; onComplete: () => void }) {
  const fromLogo = from === 'analytical' ? ANALYTICAL_LOGO : NORMAL_LOGO;
  const toLogo = to === 'analytical' ? ANALYTICAL_LOGO : NORMAL_LOGO;

  useEffect(() => {
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 150 : 3000;
    const timer = window.setTimeout(onComplete, duration);
    return () => window.clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="mode-transition" role="status" aria-label={`Switching to ${to === 'normal' ? 'Simple' : 'Analytical'} mode`}>
      <div className="mode-transition-content">
        <div className="mode-transition-art" aria-hidden="true">
          <img src={fromLogo} alt="" className="mode-transition-source" />
          <img src={toLogo} alt="" className="mode-transition-target" />
          <span className="mode-transition-sweep" />
        </div>
        <div className="mode-transition-title">{to === 'normal' ? 'Simple mode' : 'Analytical mode'}</div>
      </div>
    </div>
  );
}

function NavItems({ mobile = false }: { mobile?: boolean }) {
  const [location] = useLocation();
  const navRef = useRef<HTMLElement>(null);
  const [indicator, setIndicator] = useState<{ top: number; height: number } | null>(null);

  useLayoutEffect(() => {
    if (mobile) return;
    const nav = navRef.current;
    if (!nav) return;

    const updateIndicator = () => {
      const activeLink = nav.querySelector<HTMLElement>('.nav-link.active');
      if (!activeLink) return;

      const navBounds = nav.getBoundingClientRect();
      const linkBounds = activeLink.getBoundingClientRect();
      setIndicator({ top: linkBounds.top - navBounds.top, height: linkBounds.height });
    };

    updateIndicator();
    window.addEventListener('resize', updateIndicator);
    return () => window.removeEventListener('resize', updateIndicator);
  }, [location, mobile]);

  return (
    <nav
      ref={navRef}
      className={mobile ? 'mobile-bottom-nav' : 'sidebar-navigation flex flex-col gap-2 mt-14'}
    >
      {!mobile && indicator && (
        <span
          className="sidebar-nav-indicator"
          aria-hidden="true"
          style={{ height: indicator.height, transform: `translateY(${indicator.top}px)` }}
        />
      )}
      {items.map(({ href, label, mobileLabel, icon: Icon }) => {
        const active = href === '/' ? location === '/' : location.startsWith(href);
        return (
          <Link
            href={href}
            key={href}
            className={`nav-link ${active ? 'active' : ''}`}
            aria-label={mobile ? label : undefined}
            data-testid={`link-${label.toLowerCase().replaceAll(' ', '-')}`}
          >
            <Icon size={17} strokeWidth={active ? 2.4 : 1.8} />
            <span>{mobile ? mobileLabel ?? label : label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AppMode>(getInitialMode);
  const [modeTransition, setModeTransition] = useState<{ from: AppMode; to: AppMode } | null>(null);
  const animatedDestinations = useRef(new Set<AppMode>());

  useEffect(() => {
    try {
      window.localStorage.setItem(APP_MODE_KEY, mode);
    } catch {
      // The selected mode still applies for this session if storage is unavailable.
    }
  }, [mode]);

  const changeMode = () => {
    const nextMode = mode === 'normal' ? 'analytical' : 'normal';
    setMode(nextMode);
    if (animatedDestinations.current.has(nextMode)) return;

    animatedDestinations.current.add(nextMode);
    setModeTransition({ from: mode, to: nextMode });
  };

  return (
    <div className={`app-shell${mode === 'normal' ? ' normal-mode' : ''}`}>
      <aside className="app-nav">
        <Link href="/" className="brand-lockup flex items-center gap-3 no-underline" data-testid="link-brand">
          <BrandMark mode={mode} />
          <span>
            <span className="brand-word block">{mode === 'analytical' ? 'PetLens' : 'PetLens 2.0'}</span>
            <span className="brand-sub block">analysis for dogs</span>
          </span>
        </Link>
        <NavItems />
        <ModeSwitch mode={mode} onChange={changeMode} />
        <div className="mt-auto">
          <div className="rounded-2xl p-4" style={{ background: 'color-mix(in srgb, var(--color-white) 8%, transparent)' }}>

            <p className="text-xs leading-relaxed mt-2" style={{ color: 'color-mix(in srgb, var(--color-white) 72%, transparent)' }}>
              Your videos and observations stay on this device while testing.
            </p>
          </div>
        </div>
      </aside>
      <div className="content-wrap">
        <header className="mobile-header">
          <Link href="/" className="flex items-center gap-3 no-underline" data-testid="link-mobile-brand">
            <BrandMark mode={mode} mobile />
            <span>
              <span className="brand-word block">{mode === 'analytical' ? 'PetLens' : 'PetLens 2.0'}</span>
              <span className="brand-sub block">analysis for dogs</span>
            </span>
          </Link>
          <ModeSwitch mode={mode} onChange={changeMode} />
        </header>
        <main className="page-content">
          {children}
        </main>
        <NavItems mobile />
      </div>
      {modeTransition && (
        <ModeTransition
          from={modeTransition.from}
          to={modeTransition.to}
          onComplete={() => setModeTransition(null)}
        />
      )}
    </div>
  );
}