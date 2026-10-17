package local.pocketchat;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** Shared encoding for persisted identities and integrity checks. No mutable digest is shared. */
final class Sha256 {
  private static final char[] HEX = "0123456789abcdef".toCharArray();

  private Sha256() {}

  static String hash(String text) {
    return hash(text.getBytes(StandardCharsets.UTF_8));
  }

  static String hash(byte[] bytes) {
    try {
      return hex(MessageDigest.getInstance("SHA-256").digest(bytes));
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  static String hex(byte[] bytes) {
    char[] encoded = new char[bytes.length * 2];
    for (int i = 0; i < bytes.length; i++) {
      int value = bytes[i] & 255;
      encoded[i * 2] = HEX[value >>> 4];
      encoded[i * 2 + 1] = HEX[value & 15];
    }
    return new String(encoded);
  }
}
