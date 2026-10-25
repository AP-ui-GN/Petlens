import assert from "node:assert/strict";
import test from "node:test";

import { latestNoteHeadline } from "../src/lib/headline.ts";

test("a walk with no usable signal is never called steady", () => {
  assert.equal(latestNoteHeadline({ signalQuality: "unusable" }), "No usable signal this time");
  assert.equal(latestNoteHeadline({ signalQuality: "good" }), "A steady picture");
  assert.equal(latestNoteHeadline({ signalQuality: "limited" }), "A limited picture");
  assert.equal(latestNoteHeadline(undefined), "Nothing to compare yet");
});
