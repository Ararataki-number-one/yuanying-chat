package local.pocketchat;

import android.content.Context;
import org.json.JSONObject;
import org.mozilla.geckoview.GeckoSession;
import java.io.*;
import java.nio.file.Files;
import java.security.*;
import java.security.cert.*;
import java.util.*;
import javax.net.ssl.*;

/** Public synthetic trust material. Included only in the integration source set. */
final class SafeIdleTestTrust {
  static final String ASSET = "network-safe-idle-trust/";
  static final String HOST = "chatgpt.com";
  static final String CA_SHA = "794f38936cb5ebc28b6d0f681f9d5b00a2431f48ced181137f4f3bf45fe67226";
  static final String LEAF_SHA = "66c659c8f20a9ea7d132d66e4020897be19fab099aa3cc17fa870a967c16266c";
  static final String DB_SHA = "a3114642d39ee1f3bc23c4428b08035abeb101de367547dcfe32680af6286023";
  static final String P12_SHA = "5fe7edd5f9b89854977cc3f6181faf8b38386eb03f4829ec9d39bd3cbfb6acc3";
  final X509Certificate ca, leaf;
  final SSLContext serverTls;
  final JSONObject preparation;

  private SafeIdleTestTrust(X509Certificate ca, X509Certificate leaf, SSLContext tls, JSONObject preparation) {
    this.ca = ca; this.leaf = leaf; this.serverTls = tls; this.preparation = preparation;
  }

  static String hash(byte[] bytes) throws GeneralSecurityException {
    StringBuilder result = new StringBuilder();
    for (byte value : MessageDigest.getInstance("SHA-256").digest(bytes)) result.append(String.format(Locale.ROOT, "%02x", value & 255));
    return result.toString();
  }

  static byte[] asset(Context context, String name, String expected) throws Exception {
    byte[] bytes;
    try (InputStream input = context.getAssets().open(ASSET + name); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
      byte[] buffer = new byte[8192];
      for (int count; (count = input.read(buffer)) != -1;) output.write(buffer, 0, count);
      bytes = output.toByteArray();
    }
    if (!hash(bytes).equals(expected)) throw new GeneralSecurityException("Synthetic trust asset does not match its source identity: " + name);
    return bytes;
  }

  static X509Certificate certificate(byte[] bytes) throws CertificateException {
    return (X509Certificate) CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(bytes));
  }

  static boolean hostname(X509Certificate value) throws CertificateParsingException {
    Collection<List<?>> names = value.getSubjectAlternativeNames();
    if (names == null) return false;
    for (List<?> name : names) if (name.size() == 2 && Integer.valueOf(2).equals(name.get(0)) && HOST.equals(name.get(1))) return true;
    return false;
  }

  static SafeIdleTestTrust prepare(Context context) throws Exception {
    if (!"local.pocketchat.test".equals(context.getPackageName())) throw new SecurityException("Synthetic CA is restricted to the integration package");
    X509Certificate ca = certificate(asset(context, "root-ca.der", CA_SHA));
    X509Certificate leaf = certificate(asset(context, "server-leaf.der", LEAF_SHA));
    ca.checkValidity(); ca.verify(ca.getPublicKey());
    leaf.checkValidity(); leaf.verify(ca.getPublicKey());
    if (ca.getBasicConstraints() < 0 || ca.getKeyUsage() == null || !ca.getKeyUsage()[5] || leaf.getBasicConstraints() >= 0 || !hostname(leaf)
        || leaf.getExtendedKeyUsage() == null || !leaf.getExtendedKeyUsage().contains("1.3.6.1.5.5.7.3.1")) throw new GeneralSecurityException("Invalid synthetic CA/server identity");
    byte[] database = asset(context, "cert9.db", DB_SHA);
    File profile = new File(context.getNoBackupFilesDir(), "gecko-browser").getCanonicalFile();
    if (!profile.isDirectory() && !profile.mkdirs()) throw new IOException("Cannot prepare the isolated test NSS profile");
    File target = new File(profile, "cert9.db");
    if (target.exists()) throw new IOException("Refuse to replace an existing browser trust database; this test requires pm clear");
    Files.write(target.toPath(), database);
    if (!hash(Files.readAllBytes(target.toPath())).equals(DB_SHA)) throw new IOException("NSS public CA database copy changed");
    KeyStore keys = KeyStore.getInstance("PKCS12");
    keys.load(new ByteArrayInputStream(asset(context, "server.p12", P12_SHA)), "network-safe-idle".toCharArray());
    String alias = keys.aliases().nextElement();
    java.security.cert.Certificate[] chain = keys.getCertificateChain(alias);
    if (keys.size() != 1 || chain == null || chain.length != 2 || !hash(chain[0].getEncoded()).equals(LEAF_SHA) || !hash(chain[1].getEncoded()).equals(CA_SHA)) throw new GeneralSecurityException("Synthetic TLS server chain changed");
    KeyManagerFactory manager = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
    manager.init(keys, "network-safe-idle".toCharArray());
    SSLContext tls = SSLContext.getInstance("TLS"); tls.init(manager.getKeyManagers(), null, null);
    JSONObject preparation = J.obj("schema", 1, "method", "NSS SQL public-root profile preload", "assetDirectory", ASSET,
        "hostname", HOST, "testCaSha256", CA_SHA, "testLeafSha256", LEAF_SHA, "profileDbSha256", DB_SHA,
        "profilePath", profile.getAbsolutePath(), "preparedBeforeRuntime", true, "databaseCopyShaVerified", true,
        "serverChainShaVerified", true, "certificateValidityChecked", true, "certificateHostnameSanMatches", true,
        "productionTrustChanged", false, "certificateExceptionUsed", false);
    return new SafeIdleTestTrust(ca, leaf, tls, preparation);
  }

  JSONObject observed(GeckoSession.ProgressDelegate.SecurityInformation info) {
    boolean signature = false, validity = false, san = false, same = false;
    String digest = "", error = "";
    try {
      if (info.certificate == null) throw new GeneralSecurityException("No native server certificate");
      digest = hash(info.certificate.getEncoded());
      info.certificate.verify(ca.getPublicKey()); signature = true;
      info.certificate.checkValidity(); ca.checkValidity(); validity = true;
      san = hostname(info.certificate); same = digest.equals(LEAF_SHA);
    } catch (Exception failure) { error = failure.toString(); }
    boolean accepted = info.isSecure && !info.isException && HOST.equals(info.host) && signature && validity && san && same;
    return J.obj("callback", "GeckoSession.ProgressDelegate.onSecurityChange", "isSecure", info.isSecure, "isException", info.isException,
        "host", info.host, "origin", info.origin == null ? "" : info.origin, "certificateSha256", digest, "testCaSha256", CA_SHA,
        "certificateSignedByTestCa", signature, "certificateValidityChecked", validity, "certificateHostnameSanMatches", san,
        "certificateMatchesPackagedLeaf", same, "accepted", accepted, "verificationError", error);
  }
}
