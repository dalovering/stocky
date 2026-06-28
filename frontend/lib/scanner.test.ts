import { describe, expect, it } from "vitest";

import { EMPTY_SCAN_STATE, feedKey, MIN_SCAN_LENGTH, type ScanState } from "./scanner";

/** Feed a whole string quickly (10ms apart), then Enter, and return what was scanned. */
function scanFast(text: string, startState: ScanState = EMPTY_SCAN_STATE) {
  let state = startState;
  let t = 1000;
  for (const ch of text) {
    ({ state } = feedKey(state, ch, t));
    t += 10; // well under the gap threshold
  }
  const res = feedKey(state, "Enter", t);
  return res;
}

describe("barcode scanner state machine", () => {
  it("emits a fast-typed code on Enter", () => {
    const { scanned } = scanFast("U0427193855");
    expect(scanned).toBe("U0427193855");
  });

  it("ignores a too-short buffer", () => {
    const { scanned } = scanFast("ab"); // length 2 < MIN_SCAN_LENGTH (3)
    expect(MIN_SCAN_LENGTH).toBe(3);
    expect(scanned).toBeNull();
  });

  it("does not accumulate slowly-typed (human) characters", () => {
    let state = EMPTY_SCAN_STATE;
    let t = 0;
    for (const ch of "I123456") {
      ({ state } = feedKey(state, ch, t));
      t += 500; // human typing: 500ms apart, far above the gap
    }
    const { scanned } = feedKey(state, "Enter", t);
    // Each slow char reset the buffer, so only the last char remains -> too short.
    expect(scanned).toBeNull();
  });

  it("starts a fresh scan after a long pause", () => {
    const first = scanFast("FIRST123");
    expect(first.scanned).toBe("FIRST123");
    // A new fast scan after the reset works independently.
    const second = scanFast("SECOND456", first.state);
    expect(second.scanned).toBe("SECOND456");
  });
});
