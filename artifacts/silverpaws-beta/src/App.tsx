import { type ReactNode, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ErrorBoundary } from '@/components/error-boundary';
import { AppShell } from '@/components/app-shell';
import Home from '@/pages/home';
import Analyze from '@/pages/analyze';
import History from '@/pages/history';
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
  const [demoAnalysis, setDemoAnalysis] = useState<Analysis | null>(null);
  const [demoTourActive, setDemoTourActive] = useState(false);
  const openDemoAnalysis = (analysis: Analysis, continueTour: boolean) => {
    setDemoAnalysis(analysis);
    setDemoTourActive(continueTour);
    setLocation(`/history/${analysis.id}`);
  };
  return (
    <>
      <AppShell>
        <RoutedErrorBoundary>
          <Switch>
            <Route path="/" component={() => <Home pets={data.pets} analyses={data.analyses} />} />
            <Route path="/analyze" component={() => <Analyze pets={data.pets} analyses={data.analyses} addAnalysis={data.addAnalysis} openDemoAnalysis={openDemoAnalysis} />} />
            <Route path="/history" component={() => <History pets={data.pets} analyses={data.analyses} deleteAnalysis={data.deleteAnalysis} demoAnalysis={demoAnalysis} demoTourActive={demoTourActive} onDemoTourComplete={() => setDemoTourActive(false)} />} />
            <Route path="/history/:id" component={() => <History pets={data.pets} analyses={data.analyses} deleteAnalysis={data.deleteAnalysis} demoAnalysis={demoAnalysis} demoTourActive={demoTourActive} onDemoTourComplete={() => setDemoTourActive(false)} />} />
            <Route path="/pet">
              <PetProfile pets={data.pets} addPet={data.addPet} updatePet={data.updatePet} />
            </Route>
            <Route component={NotFound} />
          </Switch>
        </RoutedErrorBoundary>
      </AppShell>
      <Toaster position="top-center" theme="dark" richColors />
    </>
  );
}

function App() {
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