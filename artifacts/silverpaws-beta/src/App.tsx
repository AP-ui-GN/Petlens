import { type ReactNode} from 'react';
import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ErrorBoundary } from '@/components/error-boundary';
import { AppShell } from '@/components/app-shell';
import Home from '@/pages/home';
import Analyze from '@/pages/analyze';
import History from '@/pages/history';
import Analytics from '@/pages/analytics';
import PetProfile from '@/pages/pet';
import NotFound from '@/pages/not-found';
import { useLocalData } from '@/hooks/use-local-data';
import { Route, Router as WouterRouter, Switch, useLocation } from 'wouter';
import type { Analysis } from '@/lib/storage';

const queryClient = new QueryClient();

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function Router() {
  const data = useLocalData();
  const [, setLocation] = useLocation();
  const [demoTourActive, setDemoTourActive] = useState(false);
  const openSampleWalk = (analysis: Analysis, continueTour: boolean) => {
    setDemoTourActive(continueTour);
    setLocation(`/history/${analysis.id}`);
  };
  return (
    <>
      <AppShell>
        <RoutedErrorBoundary>
          <Switch>
            <Route path="/" component={() => <Home pets={data.pets} analyses={data.analyses} clearSampleWalks={data.clearSampleWalks} />} />
            <Route path="/analyze" component={() => <Analyze pets={data.pets} analyses={data.analyses} addAnalysis={data.addAnalysis} addSampleWalks={data.addSampleWalks} clearSampleWalks={data.clearSampleWalks} openSampleWalk={openSampleWalk} />} />
            <Route path="/history" component={() => <History pets={data.pets} analyses={data.analyses} deleteAnalysis={data.deleteAnalysis} demoTourActive={demoTourActive} onDemoTourComplete={() => setDemoTourActive(false)} />} />
            <Route path="/history/:id" component={() => <History pets={data.pets} analyses={data.analyses} deleteAnalysis={data.deleteAnalysis} demoTourActive={demoTourActive} onDemoTourComplete={() => setDemoTourActive(false)} />} />
            <Route path="/analytics" component={() => <Analytics pets={data.pets} analyses={data.analyses} />} />
            <Route path="/pet">
              <PetProfile pets={data.pets} addPet={data.addPet} updatePet={data.updatePet} deletePet={data.deletePet} />
            </Route>
            <Route component={NotFound} />
          </Switch>
        </RoutedErrorBoundary>
      </AppShell>
      <Toaster position="top-center" theme="dark" richColors />
    </>
  );
}

function AnimatedLogo() {
  const logoSrc = `${import.meta.env.BASE_URL}gold-hexagonal-petlens-logo-Photoroom.png`;

  return (
    <>
      <svg className="petlens-svg-defs" aria-hidden="true">
        <filter
          id="petlens-dog-outline"
          x="-10%"
          y="-10%"
          width="120%"
          height="120%"
        >
          <feMorphology
            in="SourceAlpha"
            operator="dilate"
            radius="2"
            result="expanded"
          />
          <feFlood floodColor="white" result="outlineColor" />
          <feComposite
            in="outlineColor"
            in2="expanded"
            operator="in"
            result="expandedColor"
          />
          <feComposite
            in="expandedColor"
            in2="SourceAlpha"
            operator="out"
          />
        </filter>
      </svg>
      <img className="petlens-logo" src={logoSrc} alt="" />
      <img className="petlens-outline" src={logoSrc} alt="" />
    </>
  );
}

function SplashScreen({ onFinish }: { onFinish: () => void }) {
  useEffect(() => {
    const duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ? 1000
      : 3500;
    const timer = window.setTimeout(onFinish, duration);
    return () => window.clearTimeout(timer);
  }, [onFinish]);

  return (
    <div className="app-splash" role="status" aria-label="Loading PetLens">
      <div className="app-splash-logo" aria-hidden="true">
        <AnimatedLogo />
      </div>
    </div>
  );
}
function App() {
  const [showSplash, setShowSplash] = useState(
    () => window.sessionStorage.getItem('pet-lens-splash-seen') !== 'true'
  );
  useEffect(() => {
    if (showSplash) {
      window.sessionStorage.setItem('pet-lens-splash-seen', 'true');
    }
  }, [showSplash]);
  if (showSplash) {
    return <SplashScreen onFinish={() => setShowSplash(false)} />;
  }
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;