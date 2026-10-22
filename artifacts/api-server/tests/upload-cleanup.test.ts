/**
 * The uploaded clip is written under SILVERPAWS_UPLOAD_DIR and removed after
 * the request, including when the pipeline rejects the file.
 */

import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";
import type { AddressInfo } from "node:net";
import { build } from "esbuild";

const SERVER_ENTRY = fileURLToPath(new URL("./upload-server-entry.ts", import.meta.url));

async function loadApp(): Promise<{ default: import("express").Express }> {
  const outfile = fileURLToPath(new URL("./.tmp-upload-server.mjs", import.meta.url));
  await build({
    entryPoints: [SERVER_ENTRY],
    bundle: true,
    platform: "node",
    format: "esm",
    outfile,
    // Bundle our source (extensionless imports) and zod. Leave express and pino
    // external so their Node builtins keep working.
    external: ["express", "pino", "pino-http", "pino-pretty", "cors"],
    logLevel: "silent",
  });
  // Production logging has no pino-pretty worker, so the bundled server can start.
  process.env["NODE_ENV"] = "production";
  return import(pathToFileURL(outfile).href);
}

const BOUNDARY = "----SilverPawsCleanupBoundary";

function videoBody(): Buffer {
  const header =
    `--${BOUNDARY}\r\n` +
    `Content-Disposition: form-data; name="video"; filename="walk.mp4"\r\n` +
    `Content-Type: video/mp4\r\n\r\n`;
  const footer = `\r\n--${BOUNDARY}--\r\n`;
  return Buffer.concat([
    Buffer.from(header),
    Buffer.from("this is not a real video"),
    Buffer.from(footer),
  ]);
}

async function listen(server: Server): Promise<number> {
  await new Promise<void>((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve());
  });
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("test server did not bind a port");
  }
  return (address as AddressInfo).port;
}

test("an uploaded video is deleted after the request finishes", async () => {
  const uploadDir = await mkdtemp(path.join(tmpdir(), "silverpaws-upload-test-"));
  const previous = process.env["SILVERPAWS_UPLOAD_DIR"];
  process.env["SILVERPAWS_UPLOAD_DIR"] = uploadDir;
  const previousTrust = process.env["TRUST_PROXY"];
  process.env["TRUST_PROXY"] = "1";
  const previousOrigins = process.env["ALLOWED_ORIGINS"];
  process.env["ALLOWED_ORIGINS"] = "https://allowed.example";
  const { default: app } = await loadApp();
  const server = createServer(app);

  try {
    const port = await listen(server);
    const response = await fetch(`http://127.0.0.1:${port}/api/analyze`, {
      method: "POST",
      headers: {
        "content-type": `multipart/form-data; boundary=${BOUNDARY}`,
        "x-forwarded-proto": "https",
      },
      body: videoBody(),
    });

    assert.ok(
      response.status === 400 || response.status === 502,
      `expected the fake clip to be rejected, got ${response.status}`,
    );
    const payload = (await response.json()) as { error?: string; code?: string };
    assert.equal(typeof payload.error, "string");
    assert.equal(typeof payload.code, "string");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("x-frame-options"), "DENY");
    assert.equal(response.headers.get("referrer-policy"), "no-referrer");
    assert.equal(response.headers.get("x-permitted-cross-domain-policies"), "none");
    assert.equal(response.headers.get("strict-transport-security"), "max-age=15552000");

    const allowedOriginResponse = await fetch(`http://127.0.0.1:${port}/api/healthz`, {
      headers: { origin: "https://allowed.example" },
    });
    assert.equal(allowedOriginResponse.status, 200);
    assert.equal(
      allowedOriginResponse.headers.get("access-control-allow-origin"),
      "https://allowed.example",
    );

    const rejectedOriginResponse = await fetch(`http://127.0.0.1:${port}/api/healthz`, {
      headers: { origin: "https://untrusted.example" },
    });
    assert.equal(rejectedOriginResponse.status, 200);
    assert.equal(rejectedOriginResponse.headers.get("access-control-allow-origin"), null);
    // These early replies return before the temp file is written. Anything else
    // means the clip was on disk and the finally block had to delete it.
    assert.notEqual(payload.error, "Choose a video file to analyze.");
    assert.doesNotMatch(payload.error ?? "", /not a video PetLens can read/);

    // The response is flushed before the route's finally block finishes deleting
    // the temp directory. Wait until that cleanup has actually removed it.
    let leftover: string[] = [];
    for (let attempt = 0; attempt < 40; attempt += 1) {
      leftover = await readdir(uploadDir);
      if (leftover.length === 0) break;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    assert.deepEqual(
      leftover,
      [],
      `upload directory still has ${leftover.join(", ") || "entries"} after the request`,
    );
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
    if (previous === undefined) delete process.env["SILVERPAWS_UPLOAD_DIR"];
    else process.env["SILVERPAWS_UPLOAD_DIR"] = previous;
    if (previousTrust === undefined) delete process.env["TRUST_PROXY"];
    else process.env["TRUST_PROXY"] = previousTrust;
    if (previousOrigins === undefined) delete process.env["ALLOWED_ORIGINS"];
    else process.env["ALLOWED_ORIGINS"] = previousOrigins;
    await rm(uploadDir, { recursive: true, force: true });
    await rm(new URL("./.tmp-upload-server.mjs", import.meta.url), { force: true });
  }
});
