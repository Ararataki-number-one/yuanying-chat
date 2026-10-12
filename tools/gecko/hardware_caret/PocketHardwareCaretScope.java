/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
package org.mozilla.geckoview;

/** Narrow hardware-input context on the existing SDK input-connection handler. */
public final class PocketHardwareCaretScope implements Runnable {
  private static final int SOURCE_KEYBOARD = 0x101;
  private static final int FLAG_SOFT_KEYBOARD = 0x2;
  private static final int ACTION_DOWN = 0;
  // Each original Runnable gets an independent frame. A reentrant input or an
  // exception must never leave eligibility on a later soft-IME operation.
  private static final ThreadLocal<int[]> FRAME = new ThreadLocal<>();
  private final Runnable original;
  private final boolean hardware;

  private PocketHardwareCaretScope(Runnable original, boolean hardware) {
    if (original == null) throw new NullPointerException("original");
    this.original = original;
    this.hardware = hardware;
  }

  public static Runnable wrap(Runnable original, int source, int flags, int action) {
    return new PocketHardwareCaretScope(original,
        (source & SOURCE_KEYBOARD) == SOURCE_KEYBOARD
        && (flags & FLAG_SOFT_KEYBOARD) == 0 && action == ACTION_DOWN);
  }

  @Override public void run() {
    int[] previous = FRAME.get();
    if (!hardware && previous == null) {
      original.run();
      return;
    }
    if (hardware) FRAME.set(new int[1]);
    else FRAME.remove();
    try {
      original.run();
    } finally {
      if (previous == null) FRAME.remove();
      else FRAME.set(previous);
    }
  }

  /** Called before every original synthesized-key attempt, including early returns. */
  public static void beginSynthetic() {
    int[] frame = FRAME.get();
    if (frame != null) frame[0] = 0;
  }

  /** Called only after the original non-modifier key dispatch returns normally. */
  public static void eligible(boolean actualDown, boolean notBatch) {
    int[] frame = FRAME.get();
    if (frame == null || !actualDown) return;
    // A character can synthesize several real keys, for example a dead-key
    // sequence. Only one normally returned nonbatch DOWN is admitted. Two is
    // a saturated rejection state, also used when any DOWN is in a batch.
    if (!notBatch) frame[0] = 2;
    else if (frame[0] < 2) frame[0]++;
  }

  /** Change just the existing forward-insertion predicate's length operand. */
  public static int offset(int length) {
    int[] frame = FRAME.get();
    if (frame == null) return length;
    boolean eligible = frame[0] == 1;
    frame[0] = 0;
    return eligible && length == 1 ? -1 : length;
  }
}
