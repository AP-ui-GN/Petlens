import assert from "node:assert/strict";
import test from "node:test";
import type { Server } from "node:http";

import { createGracefulShutdown } from "../src/lib/graceful-shutdown.ts";

function loggerCapture() {
  const info: string[] = [];
  const error: string[] = [];
  return {
    info,
    error,
    logger: {
      info(_fields: Record<string, unknown>, message: string) {
        info.push(message);
      },
      error(_fields: Record<string, unknown>, message: string) {
        error.push(message);
      },
    },
  };
}

test("graceful shutdown drains once and closes idle keep-alive connections", () => {
  const calls: string[] = [];
  const capture = loggerCapture();
  const server = {
    close(callback?: (error?: Error) => void) {
      calls.push("close");
      callback?.();
      return this;
    },
    closeIdleConnections() {
      calls.push("closeIdleConnections");
    },
    closeAllConnections() {
      calls.push("closeAllConnections");
    },
  } as unknown as Server;
  let stopped = 0;

  const shutdown = createGracefulShutdown(server, {
    logger: capture.logger,
    stopActiveWork() {
      stopped += 1;
    },
    timeoutMs: 100,
  });

  shutdown("SIGTERM");
  shutdown("SIGINT");

  assert.deepEqual(calls, ["close", "closeIdleConnections"]);
  assert.equal(stopped, 0);
  assert.deepEqual(capture.info, ["Graceful shutdown started", "HTTP server closed cleanly"]);
});

test("graceful shutdown bounds the drain and stops active work at the deadline", async () => {
  const calls: string[] = [];
  const capture = loggerCapture();
  const server = {
    // Deliberately hold the close callback to simulate an in-flight request.
    close() {
      calls.push("close");
      return this;
    },
    closeIdleConnections() {
      calls.push("closeIdleConnections");
    },
    closeAllConnections() {
      calls.push("closeAllConnections");
    },
  } as unknown as Server;
  let stopped = 0;

  const shutdown = createGracefulShutdown(server, {
    logger: capture.logger,
    stopActiveWork() {
      stopped += 1;
    },
    timeoutMs: 15,
  });

  shutdown("SIGTERM");
  await new Promise((resolve) => setTimeout(resolve, 40));

  assert.deepEqual(calls, ["close", "closeIdleConnections", "closeAllConnections"]);
  assert.equal(stopped, 1);
  assert.equal(capture.error.length, 1);
  assert.equal(capture.error[0], "Graceful shutdown deadline reached; stopping remaining analysis work");
});
