/**
 * Health of the analysis server, with backoff while it is offline.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { checkHealth, MISSING_API_URL_MESSAGE, resolveApiUrl } from '../lib/api';

export type ConnectionState =
  | { kind: 'checking' }
  | { kind: 'online'; url: string }
  | { kind: 'offline'; message: string };

const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000];

export function useConnection(active: boolean) {
  const [state, setState] = useState<ConnectionState>({ kind: 'checking' });
  const attempt = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const check = useCallback(async () => {
    setState((current) => (current.kind === 'online' ? current : { kind: 'checking' }));
    const url = await resolveApiUrl();
    if (!url) {
      attempt.current = 0;
      setState({ kind: 'offline', message: MISSING_API_URL_MESSAGE });
      return;
    }
    const outcome = await checkHealth(url);
    if (outcome.ok) {
      attempt.current = 0;
      setState({ kind: 'online', url });
      return;
    }
    setState({ kind: 'offline', message: outcome.message });
  }, []);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;

    const run = async () => {
      if (cancelled) return;
      await check();
    };
    void run();

    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [active, check]);

  useEffect(() => {
    if (!active || state.kind !== 'offline') return;
    const delay = BACKOFF_MS[Math.min(attempt.current, BACKOFF_MS.length - 1)] ?? 30000;
    attempt.current += 1;
    timer.current = setTimeout(() => {
      void check();
    }, delay);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [active, state.kind, state.kind === 'offline' ? state.message : '', check]);

  const retry = useCallback(() => {
    attempt.current = 0;
    void check();
  }, [check]);

  return { state, retry };
}
