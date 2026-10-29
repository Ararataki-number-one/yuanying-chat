package android.net;
public final class NetworkCapabilities {public static final int NET_CAPABILITY_INTERNET=12,TRANSPORT_VPN=4;public boolean internet=true,vpn;public boolean hasCapability(int ignored){return internet;}public boolean hasTransport(int ignored){return vpn;}}
