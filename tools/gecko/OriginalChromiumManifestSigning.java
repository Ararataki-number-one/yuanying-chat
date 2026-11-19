import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.Signature;
import java.util.Arrays;
import java.util.HexFormat;

/** Runs only inside the authorized original-APK signing environment. */
class OriginalChromiumManifestSigning {
  private static final String ORIGINAL_CERTIFICATE =
      "f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434";
  private static final byte[] PREFIX =
      "PocketChat Chromium module manifest 1\n".getBytes(StandardCharsets.US_ASCII);

  public static void main(String[] args) throws Exception {
    if (args.length != 3) throw new IllegalArgumentException("Expected keystore, manifest payload, detached signature");
    Path payloadPath = Path.of(args[1]);
    long length = Files.size(payloadPath);
    if (length <= PREFIX.length || length > 65_536 + PREFIX.length) {
      throw new IllegalArgumentException("Unexpected Chromium signing payload size");
    }
    byte[] payload = Files.readAllBytes(payloadPath);
    if (!Arrays.equals(PREFIX, Arrays.copyOf(payload, PREFIX.length))) {
      throw new IllegalArgumentException("Unexpected Chromium signing scope");
    }
    char[] storePassword = password("POCKET_STORE_PASSWORD");
    char[] keyPassword = password("POCKET_KEY_PASSWORD");
    try {
      KeyStore keyStore = KeyStore.getInstance(Path.of(args[0]).toFile(), storePassword);
      var certificate = keyStore.getCertificate("local");
      if (certificate == null || !ORIGINAL_CERTIFICATE.equals(HexFormat.of().formatHex(
          MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded())))) {
        throw new IllegalArgumentException("Chromium signing requires the original PocketChat certificate");
      }
      if (!(keyStore.getKey("local", keyPassword) instanceof PrivateKey key)) {
        throw new IllegalArgumentException("Original PocketChat signing entry unavailable");
      }
      String algorithm = switch (certificate.getPublicKey().getAlgorithm()) {
        case "RSA" -> "SHA256withRSA";
        case "EC" -> "SHA256withECDSA";
        default -> throw new IllegalArgumentException("Unsupported original PocketChat signing key");
      };
      Signature signature = Signature.getInstance(algorithm);
      signature.initSign(key);
      signature.update(payload);
      Files.write(Path.of(args[2]), signature.sign(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    } finally {
      Arrays.fill(storePassword, '\0');
      Arrays.fill(keyPassword, '\0');
    }
  }

  private static char[] password(String variable) {
    String password = System.getenv(variable);
    if (password == null || password.isEmpty()) {
      throw new IllegalArgumentException("Original APK signing credential environment is unavailable");
    }
    return password.toCharArray();
  }
}
