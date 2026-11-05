package org.mozilla.geckoview;

/** Application-owned, compile-time adapter to the pinned SDK session identifier.
 * Gecko's chrome window name is this identifier; an extension tab number is not.
 * No SDK archive, native library, provider reflection or Android setting changes.
 */
public final class AppSessionIdentity {
  private AppSessionIdentity() {}

  public static String id(GeckoSession session) {
    if (session == null) throw new IllegalArgumentException("Gecko session required");
    String value = session.getId();
    if (value == null || !value.matches("[A-Za-z0-9_.:-]{1,160}")) {
      throw new IllegalStateException("Pinned Gecko session identity unavailable");
    }
    return value;
  }
}
