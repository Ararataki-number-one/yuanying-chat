/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
package org.mozilla.geckoview;

/** One non-composition replacement on the SDK's existing input-connection thread. */
public final class PocketSynthesizedInsertionScope {
  private static final ThreadLocal<int[]> FRAME = new ThreadLocal<>();

  private PocketSynthesizedInsertionScope() {}

  /** Start just the existing non-composition replacement branch. */
  public static int[] enter() {
    int[] previous = FRAME.get();
    FRAME.set(new int[1]);
    return previous;
  }

  /** Restore the prior action even when original synthesis or dispatch throws. */
  public static void exit(int[] previous) {
    if (previous == null) FRAME.remove();
    else FRAME.set(previous);
  }

  /** Count only original, non-modifier synthesized DOWN calls that returned. */
  public static void markDown(boolean actualDown) {
    int[] frame = FRAME.get();
    if (frame != null && actualDown && frame[0] < 2) frame[0]++;
  }

  /** Alter only the original predicate's length operand, once per action. */
  public static int offset(int length) {
    int[] frame = FRAME.get();
    if (frame == null) return length;
    boolean singleDown = frame[0] == 1;
    frame[0] = 0;
    return singleDown && length == 1 ? -1 : length;
  }
}
