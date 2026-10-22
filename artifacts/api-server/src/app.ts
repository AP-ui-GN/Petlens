import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import router from "./routes";
import {
  allowedCorsOrigins,
  httpsOnlyApplies,
  requestIsHttps,
  trustProxyEnabled,
} from "./lib/hosting";
import { logger } from "./lib/logger";

const app: Express = express();
const corsOrigins = allowedCorsOrigins();

if (trustProxyEnabled()) {
  app.set("trust proxy", 1);
}

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);

// Set conservative headers suitable for a JSON API without adding a runtime
// dependency. HSTS is sent only for requests that this server recognizes as HTTPS.
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("X-Permitted-Cross-Domain-Policies", "none");

  if (
    process.env["NODE_ENV"] === "production" &&
    requestIsHttps(req.secure, req.header("x-forwarded-proto"), trustProxyEnabled())
  ) {
    res.setHeader("Strict-Transport-Security", "max-age=15552000");
  }
  next();
});

// Explicit browser-origin allowlist. Origin-less native clients are not subject
// to browser CORS; this middleware is not an authentication mechanism.
app.use(
  cors({
    origin(origin, callback) {
      if (!origin) {
        callback(null, true);
        return;
      }
      callback(null, corsOrigins.has(origin));
    },
    optionsSuccessStatus: 204,
  }),
);

app.use((req, res, next) => {
  if (!httpsOnlyApplies(process.env["NODE_ENV"], req.path)) {
    next();
    return;
  }
  if (requestIsHttps(req.secure, req.header("x-forwarded-proto"), trustProxyEnabled())) {
    next();
    return;
  }
  res.status(400).json({
    ok: false,
    error: "Open this server with https://.",
    code: "HTTPS_REQUIRED",
  });
});

// Current routes only consume multipart uploads or no body. If a future route
// requires JSON or URL-encoded data, attach the parser to that route specifically.
app.use("/api", router);

export default app;
