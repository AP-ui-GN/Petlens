/**
 * Tests for the upload reader used by POST /api/analyze.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  MultipartError,
  parseBoundary,
  parseMultipart,
} from "../src/lib/multipart.ts";

const BOUNDARY = "----SilverPawsTestBoundary";

/** Build a multipart body the way a browser FormData upload would. */
function buildBody(
  parts: { name: string; value: string | Buffer; fileName?: string; type?: string }[],
): Buffer {
  const chunks: Buffer[] = [];

  for (const part of parts) {
    const disposition = part.fileName
      ? `form-data; name="${part.name}"; filename="${part.fileName}"`
      : `form-data; name="${part.name}"`;
    const headers =
      `--${BOUNDARY}\r\nContent-Disposition: ${disposition}\r\n` +
      (part.type ? `Content-Type: ${part.type}\r\n` : "") +
      "\r\n";

    chunks.push(Buffer.from(headers));
    chunks.push(Buffer.isBuffer(part.value) ? part.value : Buffer.from(part.value));
    chunks.push(Buffer.from("\r\n"));
  }

  chunks.push(Buffer.from(`--${BOUNDARY}--\r\n`));
  return Buffer.concat(chunks);
}

test("reads the boundary from a content-type header", () => {
  assert.equal(
    parseBoundary(`multipart/form-data; boundary=${BOUNDARY}`),
    BOUNDARY,
  );
  assert.equal(
    parseBoundary(`multipart/form-data; boundary="${BOUNDARY}"`),
    BOUNDARY,
  );
});

test("ignores content types that are not multipart", () => {
  assert.equal(parseBoundary("application/json"), null);
  assert.equal(parseBoundary(undefined), null);
});

test("separates text fields from the uploaded file", () => {
  const form = parseMultipart(
    buildBody([
      { name: "petName", value: "Mabel" },
      { name: "previousOverall", value: "82.5" },
      {
        name: "video",
        value: Buffer.from([0, 1, 2, 3]),
        fileName: "walk.mp4",
        type: "video/mp4",
      },
    ]),
    BOUNDARY,
  );

  assert.equal(form.fields["petName"], "Mabel");
  assert.equal(form.fields["previousOverall"], "82.5");
  assert.equal(form.files.length, 1);
  assert.equal(form.files[0]?.fieldName, "video");
  assert.equal(form.files[0]?.fileName, "walk.mp4");
  assert.equal(form.files[0]?.contentType, "video/mp4");
});

test("keeps binary file content byte for byte", () => {
  // Includes bytes that would break if the body were treated as text.
  const bytes = Buffer.from([0x00, 0x0d, 0x0a, 0xff, 0x2d, 0x2d, 0x80]);

  const form = parseMultipart(
    buildBody([{ name: "video", value: bytes, fileName: "clip.mp4", type: "video/mp4" }]),
    BOUNDARY,
  );

  assert.deepEqual(form.files[0]?.data, bytes);
});

test("does not split binary content on boundary-like bytes", () => {
  const payload = Buffer.concat([
    Buffer.from([0x00, 0xff, 0x0d, 0x0a]),
    Buffer.from(`--${BOUNDARY}not-a-real-boundary\r\ninside-video--${BOUNDARY}X`),
    Buffer.from([0x80, 0x00, 0x11]),
  ]);

  const form = parseMultipart(
    buildBody([{ name: "video", value: payload, fileName: "clip.mp4", type: "video/mp4" }]),
    BOUNDARY,
  );

  assert.equal(form.files.length, 1);
  assert.deepEqual(form.files[0]?.data, payload);
});

test("rejects a body with no boundary marker", () => {
  assert.throws(
    () => parseMultipart(Buffer.from("just some bytes"), BOUNDARY),
    MultipartError,
  );
});

test("rejects a body that stops before its closing boundary", () => {
  const truncated = buildBody([
    { name: "video", value: Buffer.from([1, 2]), fileName: "clip.mp4", type: "video/mp4" },
  ]).subarray(0, 80);

  assert.throws(() => parseMultipart(truncated, BOUNDARY), MultipartError);
});

test("an upload with no file part yields no files", () => {
  const form = parseMultipart(buildBody([{ name: "petName", value: "Mabel" }]), BOUNDARY);

  assert.equal(form.files.length, 0);
  assert.equal(form.fields["petName"], "Mabel");
});
