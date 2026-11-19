package local.pocketchat;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

/** Classifies the environment's configured route without starting a transport or resolving DNS. */
final class CefriumRoutePolicy {
    enum Mode { UNCONFIGURED, INTERNAL, FIXED_PROXY, VPN, DIRECT, INVALID_PROXY, UNKNOWN }

    static final class Selection {
        final Mode mode;
        final String proxyPreference;
        final String proxyEndpoint;
        final boolean requireVpn;

        Selection(Mode mode, String proxyPreference, String proxyEndpoint, boolean requireVpn) {
            this.mode = mode;
            this.proxyPreference = proxyPreference;
            this.proxyEndpoint = proxyEndpoint;
            this.requireVpn = requireVpn;
        }

        boolean protectedRoute() { return mode != Mode.DIRECT; }

        @Override public boolean equals(Object value) {
            if (!(value instanceof Selection)) return false;
            Selection other = (Selection) value;
            return mode == other.mode && requireVpn == other.requireVpn
                    && proxyPreference.equals(other.proxyPreference)
                    && Objects.equals(proxyEndpoint, other.proxyEndpoint);
        }

        @Override public int hashCode() {
            return Objects.hash(mode, proxyPreference, proxyEndpoint, requireVpn);
        }
    }

    private CefriumRoutePolicy() {}

    static Mode classify(boolean configured, String mode, String configuredProxy, boolean requireVpn) {
        if (!configured) return Mode.UNCONFIGURED;
        if ("internal".equals(mode)) return Mode.INTERNAL;
        if (!"external".equals(mode)) return Mode.UNKNOWN;
        String proxy = configuredProxy == null ? "" : configuredProxy.trim();
        if (proxy.isEmpty()) return requireVpn ? Mode.VPN : Mode.DIRECT;
        return fixedProxy(proxy) == null ? Mode.INVALID_PROXY : Mode.FIXED_PROXY;
    }

    static boolean supportsConfiguredRoute(Map<String, ?> preferences) {
        return selection(preferences) != null;
    }

    /** Immutable selection of the configured route. A malformed setting cannot become direct. */
    static Selection selection(Map<String, ?> preferences) {
        if (!Boolean.TRUE.equals(preferences.get("networkConfigured"))) return null;
        Object networkMode = preferences.get("networkMode");
        if ("internal".equals(networkMode)) return new Selection(Mode.INTERNAL, "", null, false);
        if (!"external".equals(networkMode)) return null;

        Object proxy = preferences.get("proxy");
        Object requireVpn = preferences.get("requireExternalVpn");
        if (proxy != null && !(proxy instanceof String)
                || requireVpn != null && !(requireVpn instanceof Boolean)) return null;
        String configuredProxy = proxy == null ? "" : ((String) proxy).trim();
        // Legacy environments default to protected networking. Direct still needs explicit consent.
        boolean required = !Boolean.FALSE.equals(requireVpn);
        if (configuredProxy.isEmpty()) {
            if (required) return new Selection(Mode.VPN, "", null, true);
            return explicitDirect(preferences) ? new Selection(Mode.DIRECT, "", null, false) : null;
        }
        String endpoint = fixedProxy(configuredProxy);
        return endpoint == null ? null : new Selection(Mode.FIXED_PROXY, configuredProxy, endpoint, required);
    }

    /** Direct mode must be stored explicitly. Absent legacy flags never imply consent. */
    static boolean explicitDirect(Map<String, ?> preferences) {
        Object proxy = preferences.get("proxy");
        return Boolean.TRUE.equals(preferences.get("networkConfigured"))
                && "external".equals(preferences.get("networkMode"))
                && Boolean.FALSE.equals(preferences.get("requireExternalVpn"))
                && proxy instanceof String && ((String) proxy).trim().isEmpty();
    }

    /** Only one explicit endpoint is accepted. PAC, proxy fallback, and credentials are excluded. */
    static String fixedProxy(String input) {
        if (input == null || input.length() > 4096) return null;
        final URI uri;
        try {
            uri = new URI(input);
        } catch (URISyntaxException invalid) {
            return null;
        }
        String scheme = uri.getScheme();
        if (!"http".equals(scheme) && !"https".equals(scheme) && !"socks".equals(scheme)) return null;
        String host = uri.getHost();
        int port = uri.getPort();
        if (host == null || port < 1 || port > 65535 || uri.getRawUserInfo() != null
                || uri.getRawQuery() != null || uri.getRawFragment() != null
                || !"".equals(uri.getRawPath()) || uri.getRawAuthority().contains("%")) return null;
        if ("socks".equals(scheme)) scheme = "socks5";
        return scheme + "://" + host.toLowerCase(Locale.ROOT) + ":" + port;
    }
}
