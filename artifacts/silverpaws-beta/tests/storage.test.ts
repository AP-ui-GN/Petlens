import assert from "node:assert/strict";
import test from "node:test";

import { getPets } from "../src/lib/storage.ts";

test("legacy web pet weights are converted from kilograms to pounds once", (t) => {
  const values = new Map<string, string>();
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
      },
    },
  });
  t.after(() => {
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow);
    else Reflect.deleteProperty(globalThis, "window");
  });

  values.set(
    "silverpaws:pets",
    JSON.stringify([{ id: "pet-1", name: "Mabel", species: "Dog", breed: "", age: "", weight: "10", notes: "", createdAt: "2026-01-01" }]),
  );

  assert.equal(getPets()[0]?.weight, "22");
  assert.equal(getPets()[0]?.weightUnit, "lb");
  assert.equal(JSON.parse(values.get("silverpaws:pets") ?? "[]")[0]?.weight, "22");
});
