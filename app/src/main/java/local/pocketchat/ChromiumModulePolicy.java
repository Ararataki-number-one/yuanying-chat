package local.pocketchat;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.PublicKey;
import java.security.Signature;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Trust contract shared with the offline, original-signed release staging tool. */
final class ChromiumModulePolicy {
  static final String PACKAGE_NAME = "local.pocketchat";
  static final String MODULE = "chromium";
  static final int MIN_ANDROID = 29;
  static final int MAX_METADATA = 65_536;
  static final int MAX_SIGNATURE = 8192;
  private static final String RELEASES = "https://github.com/" + AppUpdatePolicy.REPO + "/releases/download/";
  private static final byte[] DOMAIN = "PocketChat Chromium module manifest 1\n".getBytes(StandardCharsets.US_ASCII);
  private static final Pattern ASSET = Pattern.compile(Pattern.quote(RELEASES)
      + "(v([0-9]+[.][0-9]+(?:[.][0-9]+)?)(?:-candidate([1-9][0-9]{0,2}))?-gecko)"
      + "/PocketChat-([0-9]+[.][0-9]+(?:[.][0-9]+)?)-chromium-(arm64-v8a|x86_64)"
      + "(?:[.](json|sig)|--(chromium(?:[.]config[.][A-Za-z0-9_]{1,60})?)[.]apk)");

  static final class Installed {
    final String version, tag, abi, baseSha256;
    final long code;
    Installed(String version, long code, String tag, String abi, String baseSha256) {
      this.version = version;
      this.code = code;
      this.tag = tag;
      this.abi = abi;
      this.baseSha256 = baseSha256;
    }
  }

  static final class Split {
    final String name, sha256;
    final long bytes;
    Split(String name, long bytes, String sha256) {
      this.name = name;
      this.bytes = bytes;
      this.sha256 = sha256;
    }
  }

  static final class Release {
    final List<Split> splits;
    final long totalBytes;
    Release(List<Split> splits, long totalBytes) {
      this.splits = splits;
      this.totalBytes = totalBytes;
    }
  }

  private ChromiumModulePolicy() {}

  static boolean abi(String abi) {
    return "arm64-v8a".equals(abi) || "x86_64".equals(abi);
  }

  static String nativeSplit(String abi) {
    return MODULE + ".config." + abi.replace('-', '_');
  }

  static String metadata(Installed installed, boolean signature) {
    return originStem(installed) + (signature ? ".sig" : ".json");
  }

  static String artifact(Installed installed, Split split) {
    return originStem(installed) + "--" + split.name + ".apk";
  }

  private static String originStem(Installed installed) {
    return RELEASES + installed.tag + "/PocketChat-" + installed.version + "-chromium-" + installed.abi;
  }

  static boolean officialOrigin(String origin) {
    if (origin == null) return false;
    Matcher asset = ASSET.matcher(origin);
    if (!asset.matches()) return false;
    String version = asset.group(2), candidate = asset.group(3);
    return version.equals(asset.group(4)) && AppUpdatePolicy.version(version)
        && AppUpdatePolicy.tag(version, candidate == null ? AppUpdatePolicy.versionChannel(version) : "candidate",
            candidate == null ? 0 : Integer.parseInt(candidate)).equals(asset.group(1))
        && (asset.group(6) != null || allowedSplit(asset.group(7), asset.group(5)));
  }

  static Release verify(byte[] manifest, byte[] detached, byte[] installedCert, Installed installed) throws IOException {
    if (!AppUpdatePolicy.SIGNER.equals(AppUpdatePolicy.hash(installedCert)) || manifest.length > MAX_METADATA
        || detached.length == 0 || detached.length > MAX_SIGNATURE) throw invalid();
    try {
      X509Certificate certificate = (X509Certificate) CertificateFactory.getInstance("X.509")
          .generateCertificate(new ByteArrayInputStream(installedCert));
      if (!validSignature(manifest, detached, certificate.getPublicKey())) throw invalid();
      return parse(manifest, installed);
    } catch (GeneralSecurityException e) {
      throw invalid();
    }
  }

  static boolean validSignature(byte[] manifest, byte[] detached, PublicKey key) throws GeneralSecurityException {
    String algorithm = key.getAlgorithm();
    if (!"RSA".equals(algorithm) && !"EC".equals(algorithm)) return false;
    String signatureType = "RSA".equals(algorithm) ? "SHA256withRSA" : "SHA256withECDSA";
    Signature signature = Signature.getInstance(signatureType);
    signature.initVerify(key);
    signature.update(DOMAIN);
    signature.update(manifest);
    return signature.verify(detached);
  }

  static Release parse(byte[] manifest, Installed installed) throws IOException {
    try {
      JSONObject metadata = new JSONObject(new String(manifest, StandardCharsets.UTF_8));
      if (number(metadata, "schema") != 1 || number(metadata, "versionCode") != installed.code
          || number(metadata, "minSdk") != MIN_ANDROID || !match(metadata, "package", PACKAGE_NAME)
          || !match(metadata, "version", installed.version) || !match(metadata, "tag", installed.tag)
          || !match(metadata, "abi", installed.abi) || !match(metadata, "baseSha256", installed.baseSha256)
          || !match(metadata, "signerSha256", AppUpdatePolicy.SIGNER)) throw invalid();
      JSONArray entries = metadata.getJSONArray("splits");
      String nativeRole = metadata.getString("nativeSplit"), expectedAbiRole = nativeSplit(installed.abi);
      if (!MODULE.equals(nativeRole) && !expectedAbiRole.equals(nativeRole)) throw invalid();
      if (entries.length() < 1 || entries.length() > 64) throw invalid();
      List<Split> splits = new ArrayList<>();
      Set<String> names = new HashSet<>();
      long total = 0;
      for (int i = 0; i < entries.length(); i++) {
        JSONObject entry = entries.getJSONObject(i);
        String name = entry.getString("name"), sha = entry.getString("sha256");
        long bytes = number(entry, "bytes");
        if (!allowedSplit(name, installed.abi) || !names.add(name) || !sha.matches("[a-f0-9]{64}")
            || bytes <= 0 || bytes > AppUpdatePolicy.MAX_APK - total) throw invalid();
        total += bytes;
        splits.add(new Split(name, bytes, sha));
      }
      if (!names.contains(MODULE) || !names.contains(nativeRole)
          || MODULE.equals(nativeRole) && names.contains(expectedAbiRole)) throw invalid();
      return new Release(Collections.unmodifiableList(splits), total);
    } catch (JSONException e) {
      throw invalid();
    }
  }

  private static boolean match(JSONObject object, String key, String value) throws JSONException {
    return value.equals(object.get(key));
  }

  private static long number(JSONObject object, String name) throws JSONException, IOException {
    Object value = object.get(name);
    if (!(value instanceof Integer || value instanceof Long)) throw invalid();
    return ((Number) value).longValue();
  }

  private static boolean allowedSplit(String split, String abi) {
    if (split == null || !split.matches("chromium(?:[.]config[.][A-Za-z0-9_]{1,60})?")) return false;
    boolean nativeRole = split.matches("chromium[.]config[.](arm64_v8a|armeabi|armeabi_v7a|x86_64|x86|riscv64|mips|mips64)");
    return !nativeRole || nativeSplit(abi).equals(split);
  }

  private static IOException invalid() {
    return new IOException("Chromium 组件签名或版本不匹配，请重新检查");
  }
}
