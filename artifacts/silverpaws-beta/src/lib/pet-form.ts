/**
 * Checks for the pet profile form.
 *
 * Age and weight are optional. When an owner types one, it has to be a positive
 * number. A blank name cannot be saved. None of these failures is stored as zero.
 */

export type PetFormInput = {
  name: string;
  age: string;
  weight: string;
};

export type PetFormErrors = {
  name?: string;
  age?: string;
  weight?: string;
};

function positiveNumberProblem(label: string, raw: string): string | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;

  const value = Number(trimmed);
  if (!Number.isFinite(value) || value <= 0) {
    return `${label} needs to be a positive number, or left blank.`;
  }
  return undefined;
}

/** Visible messages for the fields that are filled in wrong. Empty means the form can be saved. */
export function validatePetForm(input: PetFormInput): PetFormErrors {
  const errors: PetFormErrors = {};

  if (!input.name.trim()) {
    errors.name = "Add a name so this profile can be saved.";
  }

  const age = positiveNumberProblem("Age", input.age);
  if (age) errors.age = age;

  const weight = positiveNumberProblem("Weight", input.weight);
  if (weight) errors.weight = weight;

  return errors;
}

export function petFormIsValid(errors: PetFormErrors): boolean {
  return !errors.name && !errors.age && !errors.weight;
}
