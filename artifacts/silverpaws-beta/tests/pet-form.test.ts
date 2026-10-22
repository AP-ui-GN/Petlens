/**
 * Pet profile checks. Run from the web package:
 *   node --test tests/pet-form.test.ts tests/trends.test.ts
 *
 * A form that fails these checks must not be saved. The page calls
 * validatePetForm before addPet / updatePet.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { petFormIsValid, validatePetForm } from "../src/lib/pet-form.ts";

test("a blank name does not pass and explains what to fix", () => {
  const errors = validatePetForm({ name: "   ", age: "", weight: "" });

  assert.equal(petFormIsValid(errors), false);
  assert.match(errors.name ?? "", /name/i);
  assert.equal(errors.age, undefined);
  assert.equal(errors.weight, undefined);
});

test("age or weight that is present but not a positive number is rejected", () => {
  for (const value of ["0", "-3", "abc", "1e"]) {
    const errors = validatePetForm({ name: "Mabel", age: value, weight: value });

    assert.equal(petFormIsValid(errors), false, value);
    assert.match(errors.age ?? "", /positive number/);
    assert.match(errors.weight ?? "", /positive number/);
  }
});

test("a blank age and weight are allowed, and a positive number is kept", () => {
  const errors = validatePetForm({ name: " Mabel ", age: "7.5", weight: "" });

  assert.equal(petFormIsValid(errors), true);
  assert.deepEqual(errors, {});
});
