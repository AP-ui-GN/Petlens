/**
 * Health of the analysis server. Only one check runs at a time, automatic
 * retries stop after a few tries, and a manual retry always works.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { checkHealth, MISSING_API_URL_MESSAGE, resolveApiUrl } from '../lib/api';
import { nextHealthRetryDelay, type FailureKind } from '../lib/connection-messages';

export type ConnectionState =
  | { kind: 'checking' }
  | { kind: 'online'; url: string }
  | { kind: 'offline'; message: string; failure: FailureKind | 'config' };

export function useConnection(active: boolean) {
  const [state, setState] = useState<ConnectionState>({ kind: 'checking' });
  const autoRetries = useRef(0);
  const inFlight = useRef(false);
  const alive = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const check = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    clearTimer();
    setState((current) => (current.kind === 'online' ? current : { kind: 'checking' }));
    try {
      const url = await resolveApiUrl();
      if (!alive.current) return;
      if (!url) {
        setState({ kind: 'offline', message: MISSING_API_URL_MESSAGE, failure: 'config' });
        return;
      }
      const outcome = await checkHealth(url);
      if (!alive.current) return;
      if (outcome.ok) {
        autoRetries.current = 0;
        setState({ kind: 'online', url });
        return;
      }
      setState({ kind: 'offline', message: outcome.message, failure: outcome.kind });
      const delay = nextHealthRetryDelay(autoRetries.current);
      if (delay !== null) {
        autoRetries.current += 1;
        timer.current = setTimeout(() => void check(), delay);
      }
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    if (!active) return;
    autoRetries.current = 0;
    void check();
    return () => {
      alive.current = false;
      clearTimer();
    };
  }, [active, check]);

  const retry = useCallback(() => {
    autoRetries.current = 0;
    void check();
  }, [check]);

  return { state, retry };
}
