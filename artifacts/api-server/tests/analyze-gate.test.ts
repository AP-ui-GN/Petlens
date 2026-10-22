/**
 * Capacity checks happen before the upload is parsed. A refused request must
 * not continue, and it must drop the socket after the reply.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  ANALYSIS_BUSY_MESSAGE,
  ANALYSIS_RATE_MESSAGE,
  gateAnalyzeUpload,
  resetAnalyzeSlots,
  type UploadGate,
} from "../src/lib/hosting.ts";

function harness(remote = "203.0.113.8", forwarded?: string) {
  const finish: Array<() => void> = [];
  const close: Array<() => void> = [];
  let destroyed = false;
  let statusCode = 0;
  let error: string | undefined;
  let continued = false;
  const gate: UploadGate = {
    forwardedFor: forwarded,
    remoteAddress: remote,
    trustProxy: false,
    now: 1_700_000_000_000,
    writeRefusal(status, message) {
      statusCode = status;
      error = message;
    },
    afterResponse(fn) {
      finish.push(fn);
    },
    onClose(fn) {
      close.push(fn);
    },
    destroy() {
      destroyed = true;
    },
  };
  return {
    gate,
    close,
    finish,
    get destroyed() {
      return destroyed;
    },
    get statusCode() {
      return statusCode;
    },
    get error() {
      return error;
    },
    get continued() {
      return continued;
    },
    run() {
      gateAnalyzeUpload(gate, () => {
        continued = true;
      });
    },
  };
}

test("a busy server refuses before the upload continues", () => {
  resetAnalyzeSlots();
  const previousConcurrent = process.env["ANALYZE_MAX_CONCURRENT"];
  process.env["ANALYZE_MAX_CONCURRENT"] = "1";
  const held = harness();
  try {
    held.run();
    assert.equal(held.continued, true);

    const refused = harness("203.0.113.9", "198.51.100.20");
    refused.run();
    assert.equal(refused.continued, false);
    assert.equal(refused.statusCode, 429);
    assert.equal(refused.error, ANALYSIS_BUSY_MESSAGE);
    assert.equal(refused.destroyed, false);
    for (const fn of refused.finish) fn();
    assert.equal(refused.destroyed, true);

    for (const fn of held.close) fn();
    const after = harness();
    after.run();
    assert.equal(after.continued, true);
    for (const fn of after.close) fn();
  } finally {
    if (previousConcurrent === undefined) delete process.env["ANALYZE_MAX_CONCURRENT"];
    else process.env["ANALYZE_MAX_CONCURRENT"] = previousConcurrent;
    resetAnalyzeSlots();
  }
});

test("a spoofed forwarded address does not get a second rate-limit bucket", () => {
  resetAnalyzeSlots();
  const previousRate = process.env["ANALYZE_RATE_LIMIT_PER_MINUTE"];
  const previousConcurrent = process.env["ANALYZE_MAX_CONCURRENT"];
  process.env["ANALYZE_RATE_LIMIT_PER_MINUTE"] = "1";
  process.env["ANALYZE_MAX_CONCURRENT"] = "4";
  const first = harness("198.51.100.8", "203.0.113.1");
  const second = harness("198.51.100.8", "203.0.113.2");
  try {
    first.run();
    assert.equal(first.continued, true);

    second.run();
    assert.equal(second.continued, false);
    assert.equal(second.statusCode, 429);
    assert.equal(second.error, ANALYSIS_RATE_MESSAGE);
    for (const fn of second.finish) fn();
    assert.equal(second.destroyed, true);
    for (const fn of first.close) fn();
  } finally {
    if (previousRate === undefined) delete process.env["ANALYZE_RATE_LIMIT_PER_MINUTE"];
    else process.env["ANALYZE_RATE_LIMIT_PER_MINUTE"] = previousRate;
    if (previousConcurrent === undefined) delete process.env["ANALYZE_MAX_CONCURRENT"];
    else process.env["ANALYZE_MAX_CONCURRENT"] = previousConcurrent;
    resetAnalyzeSlots();
  }
});
