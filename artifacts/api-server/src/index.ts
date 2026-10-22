import app from "./app";
import { createGracefulShutdown } from "./lib/graceful-shutdown";
import { logger } from "./lib/logger";
import { stopActiveAnalyses } from "./lib/analysis-runner";
import { boundedPositiveInteger } from "./lib/hosting";

const rawPort = process.env["PORT"] ?? "8080";
const port = Number(rawPort);

if (!Number.isInteger(port) || port <= 0 || port > 65_535) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const server = app.listen(port, () => {
  logger.info({ port }, "Server listening");
});

server.on("error", (err: Error) => {
  logger.error({ err, port }, "Error listening on port");
  process.exitCode = 1;
});

const shutdown = createGracefulShutdown(server, {
  logger,
  stopActiveWork: stopActiveAnalyses,
  timeoutMs: boundedPositiveInteger(process.env["SHUTDOWN_TIMEOUT_MS"], 15_000, 1_000, 120_000),
});

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
