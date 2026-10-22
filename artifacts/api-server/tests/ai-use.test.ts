/**
 * The AI-use registry is the only wording source. Copies must match it, every
 * code path must exist, and a clip must not claim a step the pipeline does not run.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { aiUseForResult } from "../src/lib/ai-use.ts";
import { readRegistry, registryJson, renderAiUseMarkdown } from "../../../scripts/sync-ai-use.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

const copies = [
  "artifacts/silverpaws-beta/src/lib/ai-use-registry.json",
  "mobile/src/lib/ai-use-registry.json",
];

test("registry copies and AI_USE.md match the source", () => {
  const json = registryJson();
  for (const copy of copies) {
    assert.equal(readFileSync(path.join(root, copy), "utf8"), json, copy);
  }
  assert.equal(readFileSync(path.join(root, "docs", "AI_USE.md"), "utf8"), renderAiUseMarkdown());
});

test("every registry entry points at real code, and development stays a product fact", () => {
  const registry = readRegistry();
  const ids = registry.entries.map((entry: { id: string }) => entry.id);
  assert.deepEqual(ids, [
    "dog-detector",
    "pose-model",
    "motion-fallback",
    "scoring",
    "observation-rules",
    "llm-rewrite",
    "development",
  ]);

  for (const entry of registry.entries) {
    assert.ok(entry.resultLine.length > 0, entry.id);
    if (entry.codePath === "repository") {
      assert.equal(entry.id, "development");
      continue;
    }
    const full = path.join(root, entry.codePath);
    const source = readFileSync(full, "utf8");
    assert.ok(source.length > 0, entry.codePath);
  }

  const byId = new Map(registry.entries.map((entry: { id: string; codePath: string }) => [entry.id, entry.codePath]));
  assert.equal(byId.get("dog-detector"), "gait_engine/pose_backend.py");
  assert.equal(byId.get("pose-model"), "gait_engine/pose_backend.py");
  assert.equal(byId.get("motion-fallback"), "gait_engine/motion.py");
  assert.equal(byId.get("scoring"), "gait_engine/wellness.py");
  assert.equal(byId.get("observation-rules"), "gait_engine/wellness.py");
  assert.equal(byId.get("llm-rewrite"), "artifacts/api-server/src/lib/explanation.ts");

  const pipeline = readFileSync(path.join(root, "gait_engine", "pipeline.py"), "utf8");
  for (const id of ["dog-detector", "pose-model", "motion-fallback", "scoring", "observation-rules"]) {
    assert.match(pipeline, new RegExp(`"${id}"`));
  }
  assert.doesNotMatch(pipeline, /"llm-rewrite"/);
  assert.doesNotMatch(pipeline, /"development"/);

  const explanation = readFileSync(path.join(root, "artifacts", "api-server", "src", "lib", "explanation.ts"), "utf8");
  assert.match(explanation, /requestModelRewrite/);
  assert.match(explanation, /validateExplanation/);
  const pose = readFileSync(path.join(root, "gait_engine", "pose_backend.py"), "utf8");
  assert.match(pose, /VitPose/);
  const motion = readFileSync(path.join(root, "gait_engine", "motion.py"), "utf8");
  assert.match(motion, /frame-to-frame/);
});

test("a validated rewrite is the only way llm-rewrite is attached to a clip", () => {
  const pose = ["pose-model", "motion-fallback", "scoring", "observation-rules"];
  assert.deepEqual(aiUseForResult(pose, false), pose);
  assert.deepEqual(aiUseForResult(pose, true), [...pose, "llm-rewrite"]);
  assert.deepEqual(aiUseForResult([...pose, "development", "llm-rewrite"], false), pose);
  assert.deepEqual(
    aiUseForResult(["motion-fallback", "scoring", "observation-rules"], false),
    ["motion-fallback", "scoring", "observation-rules"],
  );
});
