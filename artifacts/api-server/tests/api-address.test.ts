/**
 * Release builds must not guess a laptop address.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { chooseApiUrl } from "../../../mobile/src/lib/api-address.ts";

const fallback = "http://localhost:8080";

test("a saved tester address wins over the build setting", () => {
  assert.equal(
    chooseApiUrl({
      saved: "https://api.example.com",
      configured: "https://other.example.com",
      devGuess: "http://10.0.0.2:8080",
      dev: false,
      devFallback: fallback,
    }),
    "https://api.example.com",
  );
});

test("a release build uses only the configured URL", () => {
  assert.equal(
    chooseApiUrl({
      saved: null,
      configured: "https://api.example.com",
      devGuess: "http://10.0.0.2:8080",
      dev: false,
      devFallback: fallback,
    }),
    "https://api.example.com",
  );
  assert.equal(
    chooseApiUrl({
      saved: null,
      configured: null,
      devGuess: "http://10.0.0.2:8080",
      dev: false,
      devFallback: fallback,
    }),
    null,
  );
});

test("development may guess the laptop when nothing else is set", () => {
  assert.equal(
    chooseApiUrl({
      saved: null,
      configured: null,
      devGuess: "http://10.0.0.2:8080",
      dev: true,
      devFallback: fallback,
    }),
    "http://10.0.0.2:8080",
  );
  assert.equal(
    chooseApiUrl({
      saved: null,
      configured: null,
      devGuess: null,
      dev: true,
      devFallback: fallback,
    }),
    fallback,
  );
});
