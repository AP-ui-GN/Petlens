/**
 * Production hosting rules for the analysis API.
 *
 * HTTPS is required only when NODE_ENV is production. The Docker healthcheck
 * calls /api/healthz over plain HTTP on localhost, and that path stays open.
 * Rate limiting is a fixed window per client address. It does not store accounts.
 */

const WINDOW_MS = 60_000;

const slots = new Map<string, number[]>();

let activeAnalyses = 0;

/** A missing or unusable setting falls back instead of becoming NaN or zero. */
export function positiveInteger(
  value: string | undefined,
  fallback: number,
  minimum: number,
): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < minimum) return fallback;
  return Math.floor(parsed);
}

/** Parse bounded integer configuration to avoid NaN, overflow, and accidental resource-exhaustion settings. */
export function boundedPositiveInteger(
  value: string | undefined,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  if (value === undefined || value.trim() === "") return fallback;
  const parsed = Number(value);
  if (
    !Number.isSafeInteger(parsed) ||
    parsed < minimum ||
    parsed > maximum
  ) {
    return fallback;
  }
  return parsed;
}

export function analyzeRateLimitPerMinute(): number {
  return boundedPositiveInteger(process.env["ANALYZE_RATE_LIMIT_PER_MINUTE"], 10, 1, 1_000);
}

/** One CPU pose process can use about 1.6 GB; default to one concurrent analysis. */
export function analyzeMaxConcurrent(): number {
  return boundedPositiveInteger(process.env["ANALYZE_MAX_CONCURRENT"], 1, 1, 4);
}

/**
 * Forwarded client headers are ignored unless the operator set TRUST_PROXY.
 * A browser can send those headers itself, so they are not a client identity
 * on a server that is reachable directly.
 */
export function trustProxyEnabled(): boolean {
  const value = process.env["TRUST_PROXY"]?.trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

export function resetAnalyzeSlots(): void {
  slots.clear();
  activeAnalyses = 0;
}

/** True when this client may start another analysis. */
export function takeAnalyzeSlot(key: string, now: number, limit: number, windowMs = WINDOW_MS): boolean {
  const recent = (slots.get(key) ?? []).filter((stamp) => now - stamp < windowMs);
  if (recent.length >= limit) {
    if (recent.length === 0) slots.delete(key);
    else slots.set(key, recent);
    return false;
  }
  recent.push(now);
  slots.set(key, recent);
  return true;
}

/** Reserve one running analysis. False when the server is already at the cap. */
export function tryStartAnalysis(): boolean {
  if (activeAnalyses >= analyzeMaxConcurrent()) return false;
  activeAnalyses += 1;
  return true;
}

export function finishAnalysis(): void {
  activeAnalyses = Math.max(0, activeAnalyses - 1);
}

export function clientAddress(
  forwardedFor: string | undefined,
  remoteAddress: string | undefined,
  trustProxy = false,
): string {
  if (!trustProxy) return remoteAddress || "unknown";
  // The nearest proxy appends the address it actually saw. Earlier values
  // were supplied by the client and can be chosen freely.
  const forwarded = (forwardedFor ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return forwarded[forwarded.length - 1] || remoteAddress || "unknown";
}

export const ANALYSIS_BUSY_MESSAGE =
  "The analysis service is busy. Wait a moment and try again.";
export const ANALYSIS_RATE_MESSAGE =
  "Too many analyses from this address. Wait a minute and try again.";

/**
 * What the route must do so a refused upload is answered and then dropped
 * before the multipart body is read.
 */
export interface UploadGate {
  forwardedFor: string | undefined;
  remoteAddress: string | undefined;
  trustProxy: boolean;
  now: number;
  writeRefusal: (status: number, error: string) => void;
  afterResponse: (fn: () => void) => void;
  onClose: (fn: () => void) => void;
  destroy: () => void;
}

/** Reserve capacity, or refuse without asking the caller to read the body. */
export function gateAnalyzeUpload(gate: UploadGate, next: () => void): void {
  if (!tryStartAnalysis()) {
    gate.writeRefusal(429, ANALYSIS_BUSY_MESSAGE);
    gate.afterResponse(() => gate.destroy());
    return;
  }

  const allowed = takeAnalyzeSlot(
    clientAddress(gate.forwardedFor, gate.remoteAddress, gate.trustProxy),
    gate.now,
    analyzeRateLimitPerMinute(),
  );
  if (!allowed) {
    finishAnalysis();
    gate.writeRefusal(429, ANALYSIS_RATE_MESSAGE);
    gate.afterResponse(() => gate.destroy());
    return;
  }

  let released = false;
  gate.onClose(() => {
    if (released) return;
    released = true;
    finishAnalysis();
  });
  next();
}

export function requestIsHttps(
  secure: boolean,
  forwardedProto: string | undefined,
  trustProxy = false,
): boolean {
  if (secure) return true;
  if (!trustProxy) return false;
  const proto = forwardedProto?.split(",")[0]?.trim().toLowerCase();
  return proto === "https";
}

/** Health checks stay on HTTP so the container probe can reach them. */
export function httpsOnlyApplies(nodeEnv: string | undefined, path: string): boolean {
  if (nodeEnv !== "production") return false;
  return path !== "/api/healthz" && path !== "/healthz";
}

/**
 * Browser origins allowed to read API responses. Native mobile clients and
 * same-origin/server-to-server requests do not send an Origin header, so they
 * are not blocked by CORS. CORS is not authentication.
 *
 * In production, ALLOWED_ORIGINS must be configured explicitly. Development
 * falls back to the documented Vite origins when the variable is unset.
 */
export function allowedCorsOrigins(
  nodeEnv: string | undefined = process.env["NODE_ENV"],
  configured: string | undefined = process.env["ALLOWED_ORIGINS"],
): Set<string> {
  if (configured === undefined) {
    return new Set(
      nodeEnv === "production"
        ? []
        : ["http://127.0.0.1:4173", "http://localhost:4173"],
    );
  }

  const allowed = new Set<string>();
  for (const entry of configured.split(",").map((value) => value.trim()).filter(Boolean)) {
    let parsed: URL;
    try {
      parsed = new URL(entry);
    } catch {
      throw new Error(
        "ALLOWED_ORIGINS must contain comma-separated origin URLs, such as https://app.example.com.",
      );
    }

    if (
      (parsed.protocol !== "http:" && parsed.protocol !== "https:") ||
      parsed.username !== "" ||
      parsed.password !== "" ||
      parsed.pathname !== "/" ||
      parsed.search !== "" ||
      parsed.hash !== ""
    ) {
      throw new Error(
        `Invalid ALLOWED_ORIGINS entry "${entry}". Use only an origin such as https://app.example.com, without a path.`,
      );
    }
    allowed.add(parsed.origin);
  }
  return allowed;
}
