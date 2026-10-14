package local.pocketchat;

import java.util.Collections;
import java.util.EnumMap;
import java.util.Map;

/** Build-bound native enhancement inventory. It never enables a feature by assertion. */
final class NativeCapabilityManifest {
  static final String SDK_COORDINATE = "org.mozilla.geckoview:geckoview:157.0.20261005135250";
  static final String UPSTREAM_REVISION = "737ec77d798755890b062aab541a90d6c75afd19";
  static final String SDK_INPUT_AAR_SHA256 = "15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268";
  static final String SDK_RUNTIME_COORDINATE = "local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket1";
  static final String SDK_BUILD_KIND = "source-derived-java";

  enum Capability { INDEPENDENT_TIMEZONE, CANVAS_READBACK, WEBGL_IDENTITY, AUDIO_IDENTITY, FONT_IDENTITY }
  enum Status { UNSUPPORTED }

  private final Map<Capability, Status> capabilities;
  private NativeCapabilityManifest() {
    EnumMap<Capability, Status> values = new EnumMap<>(Capability.class);
    for (Capability capability : Capability.values()) values.put(capability, Status.UNSUPPORTED);
    capabilities = Collections.unmodifiableMap(values);
  }
  // Legacy factory name; the shipped SDK is explicitly source-derived.
  static NativeCapabilityManifest officialGecko() { return new NativeCapabilityManifest(); }
  Map<Capability, Status> capabilities() { return capabilities; }
  Status status(Capability capability) {
    if (capability == null) throw new IllegalArgumentException("A capability is required.");
    return capabilities.get(capability);
  }
  boolean supports(Capability capability) { status(capability); return false; }
  boolean usesOfficialSdk() { return false; }
  void requireSupported(Capability capability) {
    if (!supports(capability)) throw new IllegalArgumentException("Native capability is unavailable: " + capability);
  }
  String unsupportedSummary() {
    return "官方 GeckoView 基础，含输入同步修正；独立时区、Canvas、WebGL、音频和字体的自定义原生控制尚不支持。原生隐私保护不等于这些自定义能力。";
  }
}
