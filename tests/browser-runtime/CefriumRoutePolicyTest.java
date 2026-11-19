package local.pocketchat;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/** Host checks for candidate route classification before the optional engine starts. */
public final class CefriumRoutePolicyTest {
    public static void main(String[] args) {
        expect("http://proxy.example:8080", CefriumRoutePolicy.fixedProxy("http://Proxy.example:8080"));
        expect("https://[2001:db8::2]:443", CefriumRoutePolicy.fixedProxy("https://[2001:DB8::2]:443"));
        expect("socks5://127.0.0.1:9050", CefriumRoutePolicy.fixedProxy("socks://127.0.0.1:9050"));
        for (String invalid : new String[]{
                null, "", "http://proxy", "https://proxy:65536", "http://proxy:0",
                "http://user@proxy:8080", "http://proxy:8080/", "http://proxy:8080#fragment",
                "http://proxy:8080?query=1", "http://[fe80::1%25wlan0]:8123",
                "http://proxy:1234;direct://", "pac://proxy:8080", "socks5://proxy:8080"
        }) {
            expect(null, CefriumRoutePolicy.fixedProxy(invalid));
        }

        expect(CefriumRoutePolicy.Mode.UNCONFIGURED,
                CefriumRoutePolicy.classify(false, "internal", "", true));
        expect(CefriumRoutePolicy.Mode.INTERNAL,
                CefriumRoutePolicy.classify(true, "internal", "bad", true));
        expect(CefriumRoutePolicy.Mode.DIRECT,
                CefriumRoutePolicy.classify(true, "external", "", false));
        expect(CefriumRoutePolicy.Mode.VPN,
                CefriumRoutePolicy.classify(true, "external", "", true));
        expect(CefriumRoutePolicy.Mode.FIXED_PROXY,
                CefriumRoutePolicy.classify(true, "external", " socks://127.0.0.1:9050 ", true));
        expect(CefriumRoutePolicy.Mode.INVALID_PROXY,
                CefriumRoutePolicy.classify(true, "external", "http://proxy:443/x", false));
        expect(CefriumRoutePolicy.Mode.UNKNOWN,
                CefriumRoutePolicy.classify(true, "automatic", "", false));

        Map<String, Object> explicit = new HashMap<>();
        explicit.put("networkConfigured", true);
        explicit.put("networkMode", "external");
        explicit.put("proxy", "");
        explicit.put("requireExternalVpn", false);
        expect(true, CefriumRoutePolicy.explicitDirect(explicit));
        expect(false, CefriumRoutePolicy.explicitDirect(Collections.emptyMap()));
        for (String key : explicit.keySet()) {
            Map<String, Object> incomplete = new HashMap<>(explicit);
            incomplete.remove(key);
            expect(false, CefriumRoutePolicy.explicitDirect(incomplete));
        }
        explicit.put("requireExternalVpn", "false");
        expect(false, CefriumRoutePolicy.explicitDirect(explicit));
        explicit.put("requireExternalVpn", true);
        expect(false, CefriumRoutePolicy.explicitDirect(explicit));
        explicit.put("requireExternalVpn", false);
        explicit.put("proxy", "https://proxy:443");
        expect(false, CefriumRoutePolicy.explicitDirect(explicit));
        explicit.put("networkMode", "internal");
        explicit.put("proxy", "");
        expect(false, CefriumRoutePolicy.explicitDirect(explicit));

        Map<String, Object> settings = new HashMap<>(explicit);
        settings.put("proxy", "retained legacy setting");
        expect(CefriumRoutePolicy.Mode.INTERNAL, requireRoute(settings).mode);
        settings.put("networkMode", "external");
        expect(null, CefriumRoutePolicy.selection(settings));
        settings.put("proxy", "");
        expect(CefriumRoutePolicy.Mode.DIRECT, requireRoute(settings).mode);
        expect(false, requireRoute(settings).protectedRoute());
        settings.put("requireExternalVpn", true);
        expect(CefriumRoutePolicy.Mode.VPN, requireRoute(settings).mode);
        expect(true, requireRoute(settings).protectedRoute());
        expect(true, requireRoute(settings).requireVpn);
        settings.remove("requireExternalVpn");
        expect(CefriumRoutePolicy.Mode.VPN, requireRoute(settings).mode);
        settings.remove("proxy");
        expect(CefriumRoutePolicy.Mode.VPN, requireRoute(settings).mode);
        settings.put("requireExternalVpn", false);
        expect(false, CefriumRoutePolicy.supportsConfiguredRoute(settings));
        settings.put("requireExternalVpn", true);
        settings.put("proxy", " https://Proxy.example:443 ");
        CefriumRoutePolicy.Selection https = requireRoute(settings);
        expect(CefriumRoutePolicy.Mode.FIXED_PROXY, https.mode);
        expect("https://Proxy.example:443", https.proxyPreference);
        expect("https://proxy.example:443", https.proxyEndpoint);
        expect(true, https.requireVpn);
        expect(https, requireRoute(new HashMap<>(settings)));
        settings.put("requireExternalVpn", false);
        expect(false, https.equals(requireRoute(settings)));
        settings.put("proxy", "socks://127.0.0.1:9050");
        expect("socks5://127.0.0.1:9050", requireRoute(settings).proxyEndpoint);
        settings.put("proxy", "http://proxy.example:8080");
        expect("http://proxy.example:8080", requireRoute(settings).proxyEndpoint);
        settings.remove("requireExternalVpn");
        expect(true, requireRoute(settings).requireVpn);
        settings.put("requireExternalVpn", "false");
        expect(false, CefriumRoutePolicy.supportsConfiguredRoute(settings));
        settings.put("networkConfigured", false);
        expect(null, CefriumRoutePolicy.selection(settings));

        System.out.println("CEF route policy passed");
    }

    private static CefriumRoutePolicy.Selection requireRoute(Map<String, Object> settings) {
        expect(true, CefriumRoutePolicy.supportsConfiguredRoute(settings));
        return CefriumRoutePolicy.selection(settings);
    }

    private static void expect(Object expected, Object actual) {
        if (!Objects.equals(expected, actual)) {
            throw new AssertionError("Expected " + expected + ", got " + actual);
        }
    }
}
