/**
 * Cached, no-download readiness probe for the Python analysis path.
 *
 * Liveness (/healthz) deliberately remains cheap and dependency-independent.
 * Readiness checks the lightweight OpenCV fallback first; missing optional pose
 * weights do not make the whole service unavailable because the fallback can
 * still return an honest motion-only result.
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";

import { REPOSITORY_ROOT, resolvePythonCommand } from "./analysis-runner";

const execFileAsync = promisify(execFile);
const SETUP_SCRIPT = path.join(REPOSITORY_ROOT, "scripts", "check_setup.py");
const PROBE_TIMEOUT_MS = 10_000;
const CACHE_TTL_MS = 60_000;

export interface ReadinessReport {
  status: "ready" | "unavailable";
  capabilities: string[];
  poseModelAvailable: boolean;
  warnings: string[];
}

interface SetupReport {
  opencv: string | null;
  fallbackReady: boolean;
  detectorReady: boolean;
  poseReady: boolean;
}

let cached: { expiresAt: number; report: ReadinessReport } | undefined;
let inFlight: Promise<ReadinessReport> | undefined;

function unavailableReport(message: string): ReadinessReport {
  return {
    status: "unavailable",
    capabilities: [],
    poseModelAvailable: false,
    warnings: [message],
  };
}

function readSetupPayload(stdout: string): SetupReport | null {
  try {
    const value: unknown = JSON.parse(stdout);
    if (typeof value !== "object" || value === null) return null;
    const row = value as Record<string, unknown>;
    if (
      typeof row["fallbackReady"] !== "boolean" ||
      typeof row["detectorReady"] !== "boolean" ||
      typeof row["poseReady"] !== "boolean" ||
      !(typeof row["opencv"] === "string" || row["opencv"] === null)
    ) {
      return null;
    }
    return {
      opencv: row["opencv"],
      fallbackReady: row["fallbackReady"],
      detectorReady: row["detectorReady"],
      poseReady: row["poseReady"],
    };
  } catch {
    return null;
  }
}

async function inspectReadiness(): Promise<ReadinessReport> {
  let stdout: string;
  try {
    const result = await execFileAsync(
      resolvePythonCommand(),
      [SETUP_SCRIPT, "--json"],
      {
        cwd: REPOSITORY_ROOT,
        timeout: PROBE_TIMEOUT_MS,
        maxBuffer: 128 * 1024,
        encoding: "utf8",
      },
    );
    stdout = result.stdout;
  } catch (error) {
    // When Python exits non-zero it may still have emitted a valid JSON report.
    const captured = error as Error & { stdout?: string };
    stdout = typeof captured.stdout === "string" ? captured.stdout : "";
    if (!stdout.trim()) {
      return unavailableReport(
        "The configured Python interpreter could not run the local setup check.",
      );
    }
  }

  const setup = readSetupPayload(stdout);
  if (!setup) {
    return unavailableReport(
      "The Python setup check returned an invalid report. Check the Python/OpenCV environment.",
    );
  }

  if (!setup.fallbackReady || setup.opencv === null) {
    return unavailableReport(
      "Python is running, but OpenCV is unavailable. Install requirements-opencv.txt.",
    );
  }

  const warnings: string[] = [];
  const capabilities = ["opencv-motion"];
  if (setup.detectorReady) {
    capabilities.push("dog-detection");
  }
  if (setup.poseReady) {
    capabilities.push("coco-17-keypoints");
    warnings.push(
      "The cached pose checkpoint exposes COCO-17 human landmarks; stride length and left/right gait symmetry remain unmeasured.",
    );
  } else if (setup.detectorReady) {
    warnings.push(
      "Dog detection is available, but pose weights are unavailable; only dog-in-frame coverage can be measured, not anatomical landmarks or gait.",
    );
  } else {
    warnings.push(
      "Optional pose dependencies or cached weights are unavailable; only OpenCV picture-motion analysis is available.",
    );
    warnings.push(
      "Stride length and left/right gait symmetry remain unmeasured with the current checkpoint.",
    );
  }

  return {
    status: "ready",
    capabilities,
    poseModelAvailable: setup.poseReady,
    warnings,
  };
}

export async function getReadiness(): Promise<ReadinessReport> {
  const now = Date.now();
  if (cached && cached.expiresAt > now) return cached.report;
  if (inFlight) return inFlight;

  inFlight = inspectReadiness()
    .catch(() =>
      unavailableReport("The readiness probe failed unexpectedly; inspect server logs."),
    )
    .then((report) => {
      cached = { report, expiresAt: Date.now() + CACHE_TTL_MS };
      return report;
    })
    .finally(() => {
      inFlight = undefined;
    });

  return inFlight;
}

/** Reset only the in-process cache; exported for deterministic tests. */
export function resetReadinessCache(): void {
  cached = undefined;
  inFlight = undefined;
}
