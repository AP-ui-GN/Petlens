import { Router, type IRouter } from "express";
import { HealthCheckResponse } from "@workspace/api-zod";

import { getReadiness, type ReadinessReport } from "../lib/readiness";

export function createHealthRouter(
  readinessCheck: () => Promise<ReadinessReport> = getReadiness,
): IRouter {
  const router: IRouter = Router();

  // Liveness intentionally verifies only that the Node process can respond.
  router.get("/healthz", (_req, res) => {
    const data = HealthCheckResponse.parse({ status: "ok" });
    res.json(data);
  });

  // Readiness distinguishes a usable motion-only fallback from an unavailable
  // Python/OpenCV runtime. Missing optional pose weights do not fail readiness.
  router.get("/readyz", async (_req, res) => {
    try {
      const report = await readinessCheck();
      res.status(report.status === "ready" ? 200 : 503).json(report);
    } catch {
      res.status(503).json({
        status: "unavailable",
        capabilities: [],
        poseModelAvailable: false,
        warnings: ["The readiness probe failed unexpectedly."],
      } satisfies ReadinessReport);
    }
  });

  return router;
}

export default createHealthRouter();
