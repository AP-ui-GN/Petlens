/**
 * orval appends `export * from './generated/types'` to the hand-written barrel.
 * That star export collides with the zod schema of the same name. Drop the line.
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const barrel = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "api-zod",
  "src",
  "index.ts",
);
const generatedFiles = [
  path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "api-client-react",
    "src",
    "generated",
    "api.schemas.ts",
  ),
  path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "api-client-react",
    "src",
    "generated",
    "api.ts",
  ),
  path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "api-zod",
    "src",
    "generated",
    "api.ts",
  ),
];
for (const file of generatedFiles) {
  const source = readFileSync(file, "utf8");
  const normalized = `${source.trimEnd()}\n`;
  if (normalized !== source) writeFileSync(file, normalized);
}

const source = readFileSync(barrel, "utf8");
const next = source
  .replaceAll("export * from './generated/types';\n", "")
  .replaceAll('export * from "./generated/types";\n', "");
if (next !== source) writeFileSync(barrel, next);
