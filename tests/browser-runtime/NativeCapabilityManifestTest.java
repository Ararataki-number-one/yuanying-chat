package local.pocketchat;

public final class NativeCapabilityManifestTest {
  public static void main(String[] args) {
    NativeCapabilityManifest manifest = NativeCapabilityManifest.officialGecko();
    int checks = 0;
    if (manifest.usesOfficialSdk()) throw new AssertionError("source-derived backend must not claim unmodified official SDK"); checks++;
    if (!manifest.unsupportedSummary().contains("输入同步修正")) throw new AssertionError("derived SDK disclosure"); checks++;
    for (NativeCapabilityManifest.Capability capability : NativeCapabilityManifest.Capability.values()) {
      if (manifest.supports(capability) || manifest.status(capability) != NativeCapabilityManifest.Status.UNSUPPORTED)
        throw new AssertionError("False native claim: " + capability);
      checks++;
      try { manifest.requireSupported(capability); throw new AssertionError("Unsupported setting accepted"); }
      catch (IllegalArgumentException expected) { checks++; }
    }
    try { manifest.capabilities().clear(); throw new AssertionError("Mutable capability registry"); }
    catch (UnsupportedOperationException expected) { checks++; }
    try { manifest.status(null); throw new AssertionError("Unknown capability accepted"); }
    catch (IllegalArgumentException expected) { checks++; }
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false,\"nativeControlsEnabled\":false}");
  }
}
