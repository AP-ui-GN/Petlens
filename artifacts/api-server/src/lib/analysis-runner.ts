/**
 * Runs the Python analysis pipeline for one clip.
 *
 * The API never re-implements analysis logic. It hands a file to
 * `scripts/analyze_clip.py`, then validates whatever comes back against the
 * generated schema before anything reaches a user.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { AnalyzeMovementClipResponse, type AnalyzeResult } from "@workspace/api-zod";

import { logger } from "./logger";
import {
  ANALYSIS_TIMEOUT_MS,
  isFinishedAnalysis,
  readPipelineFailure,
} from "./saved-result";

export { ANALYSIS_TIMEOUT_MS, DEFAULT_ANALYSIS_TIMEOUT_MS } from "./saved-result";

// This file is bundled to artifacts/api-server/dist, so the repository root is
// three levels up. SILVERPAWS_REPO_ROOT overrides it for other layouts.
export const REPOSITORY_ROOT =
  process.env["SILVERPAWS_REPO_ROOT"] ??
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

const ANALYSIS_SCRIPT = path.join(REPOSITORY_ROOT, "scripts", "analyze_clip.py");

/** Exit code the CLI uses when the uploaded clip itself was the problem. */
const CLIP_PROBLEM_EXIT_CODE = 2;

const STDERR_LOG_LIMIT = 4000;
const activePipelines = new Set<ChildProcess>();

/** Stop in-flight Python workers when graceful shutdown reaches its deadline. */
export function stopActiveAnalyses(): void {
  for (const child of activePipelines) stopPipeline(child);
}

function stopPipeline(child: ChildProcess): void {
  const pid = child.pid;
  if (pid && process.platform !== "win32") {
    try {
      process.kill(-pid, "SIGKILL");
      return;
    } catch {
      // The group is already gone.
    }
  }
  try {
    child.kill("SIGKILL");
  } catch {
    // Already exited.
  }
}

export interface AnalysisRequest {
  videoPath: string;
  petName?: string;
  previousOverall?: number;
  previousPipeline?: string;
  requestId?: string;
}

export type AnalysisErrorCode =
  | "PIPELINE_UNAVAILABLE"
  | "PIPELINE_TIMEOUT"
  | "INVALID_VIDEO"
  | "PIPELINE_INVALID_OUTPUT"
  | "SCHEMA_MISMATCH"
  | "ANALYSIS_FAILED";

export type AnalysisOutcome =
  | { ok: true; result: AnalyzeResult }
  | { ok: false; status: 400 | 502; error: string; code: AnalysisErrorCode };

/**
 * Pick the Python interpreter to run. A project virtual environment is used when
 * present so the server does not depend on the machine's global Python.
 */
export function resolvePythonCommand(): string {
  const configured = process.env["SILVERPAWS_PYTHON"];
  if (configured) return configured;

  const candidates =
    process.platform === "win32"
      ? [path.join(REPOSITORY_ROOT, ".venv", "Scripts", "python.exe")]
      : [path.join(REPOSITORY_ROOT, ".venv", "bin", "python")];

  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }

  return process.platform === "win32" ? "python" : "python3";
}

function buildArguments(request: AnalysisRequest, outputPath: string): string[] {
  const args = [ANALYSIS_SCRIPT, request.videoPath, "--output-json", outputPath];

  if (request.petName) args.push("--pet-name", request.petName);
  if (request.previousOverall !== undefined) {
    args.push("--previous-overall", String(request.previousOverall));
  }
  if (request.previousPipeline) {
    args.push("--previous-pipeline", request.previousPipeline);
  }
  if (request.requestId) args.push("--request-id", request.requestId);

  return args;
}

interface ProcessOutcome {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
  spawnError: Error | null;
}

function runPython(command: string, args: string[]): Promise<ProcessOutcome> {
  return new Promise((resolve) => {
    // Keep analysis in a separate process so its timeout and failure stay isolated.
    const child = spawn(command, args, {
      cwd: REPOSITORY_ROOT,
      detached: process.platform !== "win32",
    });
    activePipelines.add(child);

    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let spawnError: Error | null = null;

    const timer = setTimeout(() => {
      timedOut = true;
      stopPipeline(child);
    }, ANALYSIS_TIMEOUT_MS);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      if (stderr.length < STDERR_LOG_LIMIT) stderr += chunk.toString();
    });

    child.on("error", (error: Error) => {
      spawnError = error;
    });

    child.on("close", (exitCode) => {
      activePipelines.delete(child);
      clearTimeout(timer);
      resolve({ exitCode, stdout, stderr, timedOut, spawnError });
    });
  });
}

/**
 * Read the JSON the CLI produced. The output file is preferred because library
 * logging can add noise to stdout.
 */
async function readPipelineJson(
  outputPath: string,
  stdout: string,
): Promise<unknown> {
  try {
    return JSON.parse(await readFile(outputPath, "utf8"));
  } catch {
    const lastJsonLine = stdout
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.startsWith("{"))
      .pop();

    if (!lastJsonLine) return null;

    try {
      return JSON.parse(lastJsonLine);
    } catch {
      return null;
    }
  }
}

export async function runAnalysis(
  request: AnalysisRequest,
): Promise<AnalysisOutcome> {
  const command = resolvePythonCommand();
  const startedAt = Date.now();
  const requestId = request.requestId;
  const outputDirectory = await mkdtemp(path.join(tmpdir(), "petlens-result-"));
  const outputPath = path.join(outputDirectory, "analysis.json");

  try {
    // Prefer the JSON file, but preserve the CLI's last JSON line as a fallback.
    const outcome = await runPython(command, buildArguments(request, outputPath));

    if (outcome.spawnError) {
      logger.error(
        { requestId, err: outcome.spawnError, command },
        "Could not start the analysis pipeline",
      );
      return {
        ok: false,
        status: 502,
        code: "PIPELINE_UNAVAILABLE",
        error:
          "The analysis service is not available. Check that Python and the " +
          "requirements in requirements.txt are installed.",
      };
    }

    const payload = await readPipelineJson(outputPath, outcome.stdout);

    if (outcome.timedOut) {
      if (isFinishedAnalysis(payload)) {
        const saved = AnalyzeMovementClipResponse.safeParse(payload);
        if (saved.success && saved.data.ok === true) {
          logger.warn(
            { requestId, timeoutMs: ANALYSIS_TIMEOUT_MS, durationMs: Date.now() - startedAt },
            "Pose was stopped after the motion result was saved",
          );
          return { ok: true, result: saved.data };
        }
      }
      logger.error(
        { requestId, timeoutMs: ANALYSIS_TIMEOUT_MS, durationMs: Date.now() - startedAt },
        "Analysis pipeline timed out",
      );
      return {
        ok: false,
        status: 502,
        code: "PIPELINE_TIMEOUT",
        error: "Analysis took too long and was stopped. Try a shorter clip.",
      };
    }

    if (payload === null) {
      logger.error(
        { requestId, exitCode: outcome.exitCode, stderr: outcome.stderr },
        "Analysis pipeline returned no readable JSON",
      );
      return {
        ok: false,
        status: 502,
        code: "PIPELINE_INVALID_OUTPUT",
        error: "The analysis service returned an unreadable result.",
      };
    }

    // The pipeline reports its own failures as JSON so the message stays useful.
    const failure = readPipelineFailure(payload);
    if (failure !== null) {
      logger.warn(
        { requestId, exitCode: outcome.exitCode, message: failure },
        "Analysis pipeline failed",
      );
      return {
        ok: false,
        status: outcome.exitCode === CLIP_PROBLEM_EXIT_CODE ? 400 : 502,
        code: outcome.exitCode === CLIP_PROBLEM_EXIT_CODE ? "INVALID_VIDEO" : "ANALYSIS_FAILED",
        error: failure,
      };
    }

    // Validate the Python result before it crosses the API boundary.
    const parsed = AnalyzeMovementClipResponse.safeParse(payload);
    if (!parsed.success) {
      logger.error(
        { requestId, issues: parsed.error.issues.slice(0, 5) },
        "Analysis result did not match the API contract",
      );
      return {
        ok: false,
        status: 502,
        code: "SCHEMA_MISMATCH",
        error: "The analysis result did not match the expected format.",
      };
    }

    logger.info(
      {
        requestId,
        pipeline: parsed.data.pipeline,
        durationMs: Date.now() - startedAt,
        fallbackUsed: parsed.data.pipeline === "opencv-motion",
      },
      "Analysis completed",
    );
    return { ok: true, result: parsed.data };
  } finally {
    await rm(outputDirectory, { recursive: true, force: true });
  }
}
