import type { Server } from "node:http";

export interface ShutdownLogger {
  info(fields: Record<string, unknown>, message: string): void;
  error(fields: Record<string, unknown>, message: string): void;
}

export interface GracefulShutdownOptions {
  logger: ShutdownLogger;
  stopActiveWork: () => void;
  timeoutMs?: number;
}

/**
 * Build an idempotent signal handler that stops accepting requests, lets
 * in-flight work drain, and force-closes remaining work at a bounded deadline.
 */
export function createGracefulShutdown(
  server: Server,
  options: GracefulShutdownOptions,
): (signal: string) => void {
  const timeoutMs = options.timeoutMs ?? 15_000;
  let started = false;

  return (signal: string): void => {
    if (started) return;
    started = true;

    options.logger.info({ signal }, "Graceful shutdown started");

    const deadline = setTimeout(() => {
      options.logger.error(
        { signal, timeoutMs },
        "Graceful shutdown deadline reached; stopping remaining analysis work",
      );
      try {
        options.stopActiveWork();
      } finally {
        server.closeAllConnections?.();
      }
    }, timeoutMs);
    deadline.unref();

    // Stop accepting new requests and close idle keep-alive sockets immediately.
    server.close((error) => {
      clearTimeout(deadline);
      if (error) {
        options.logger.error({ signal, err: error }, "HTTP server shutdown failed");
        options.stopActiveWork();
        server.closeAllConnections?.();
        return;
      }
      options.logger.info({ signal }, "HTTP server closed cleanly");
    });
    server.closeIdleConnections?.();
  };
}
