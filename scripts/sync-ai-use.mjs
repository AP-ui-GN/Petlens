#!/usr/bin/env node
/**
 * Copy lib/ai-use/registry.json into the web app and write docs/AI_USE.md
 * from the same file. Edit the registry, then run this script.
 *
 *   node scripts/sync-ai-use.mjs
 *   node scripts/sync-ai-use.mjs --check
 */

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const registryPath = path.join(root, "lib", "ai-use", "registry.json");
const copies = [
  path.join(root, "artifacts", "silverpaws-beta", "src", "lib", "ai-use-registry.json"),
  path.join(root, "mobile", "src", "lib", "ai-use-registry.json"),
];
const markdownPath = path.join(root, "docs", "AI_USE.md");

export function readRegistry() {
  return JSON.parse(readFileSync(registryPath, "utf8"));
}

export function registryJson(registry = readRegistry()) {
  return `${JSON.stringify(registry, null, 2)}\n`;
}

export function renderAiUseMarkdown(registry = readRegistry()) {
  const sections = registry.entries
    .map((entry) => {
      const code =
        entry.codePath === "repository"
          ? "Code: the repository as a whole, not one clip."
          : `Code: \`${entry.codePath}\``;
      return [
        `## ${entry.id}`,
        "",
        `**What it is.** ${entry.whatItIs}`,
        "",
        `**What it does.** ${entry.whatItDoes}`,
        "",
        `**What it doesn't do.** ${entry.whatItDoesnt}`,
        "",
        code,
        "",
      ].join("\n");
    })
    .join("\n");

  return [
    "# How AI is used in PetLens",
    "",
    registry.summary,
    "",
    "This page is generated from `lib/ai-use/registry.json`. Edit that file and run `node scripts/sync-ai-use.mjs`. Do not edit the copies by hand.",
    "",
    "Pose landmarks are described further in `docs/MODEL_CARD.md`.",
    "",
    sections,
  ].join("\n");
}

function writeOrCheck(filePath, next, check) {
  if (!check) {
    writeFileSync(filePath, next);
    return;
  }
  const current = readFileSync(filePath, "utf8");
  if (current !== next) {
    console.error(`Out of date: ${path.relative(root, filePath)}`);
    process.exitCode = 1;
  }
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isMain) {
  const check = process.argv.includes("--check");
  const json = registryJson();
  const markdown = renderAiUseMarkdown();

  for (const copy of copies) writeOrCheck(copy, json, check);
  writeOrCheck(markdownPath, markdown, check);

  if (process.exitCode) {
    console.error("Run node scripts/sync-ai-use.mjs to refresh the copies.");
  } else if (!check) {
    console.log("AI-use registry copied.");
  }
}
