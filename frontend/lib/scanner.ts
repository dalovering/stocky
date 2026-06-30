// Pure barcode-scan detection logic, decoupled from React so it can be unit-tested.
//
// USB barcode scanners act as keyboards: they "type" the code's characters very fast and
// finish with Enter. We accumulate characters that arrive in quick succession and emit the
// buffer when Enter is pressed. Slow (human) typing keeps resetting the buffer, so manual
// keystrokes never masquerade as a scan. This lets the kiosk react to scans WITHOUT any
// input box being focused — the core UX requirement from the spec.

export interface ScanState {
  buffer: string;
  lastTime: number;
}

export const EMPTY_SCAN_STATE: ScanState = { buffer: "", lastTime: 0 };

// Max gap (ms) between characters for them to count as part of one scan.
export const SCAN_CHAR_GAP_MS = 60;
// Minimum length for a buffer to be considered a real barcode (filters stray Enters).
export const MIN_SCAN_LENGTH = 3;

export interface FeedResult {
  state: ScanState;
  scanned: string | null;
}

/**
 * Feed one key into the scan state machine.
 * @param key a single printable character, or "Enter"
 * @param now monotonic timestamp in ms (performance.now())
 */
export function feedKey(state: ScanState, key: string, now: number): FeedResult {
  if (key === "Enter") {
    const buffer = state.buffer;
    const reset = { buffer: "", lastTime: now };
    if (buffer.length >= MIN_SCAN_LENGTH) {
      return { state: reset, scanned: buffer };
    }
    return { state: reset, scanned: null };
  }

  // A printable character. If it arrived too long after the previous one, treat it as the
  // start of a fresh (likely human) sequence rather than appending to a scan.
  if (now - state.lastTime > SCAN_CHAR_GAP_MS) {
    return { state: { buffer: key, lastTime: now }, scanned: null };
  }
  return { state: { buffer: state.buffer + key, lastTime: now }, scanned: null };
}

/** Whether a keydown should be ignored because the user is typing into a field. */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}
