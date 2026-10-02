package local.pocketchat;
import android.widget.LinearLayout;

/** Compatibility entry points; the network UI has a single presentation implementation. */
final class DesignNetworkUi {
  static boolean busy(MainActivity a){return ProfileUi.working(a.session)||a.loading.taskRunning;}
  static String mode(MainActivity a){return a.session.internalNetwork()?"内置网络":!a.prefs.getString("proxy","").isEmpty()?"应用专用代理":a.prefs.getBoolean("requireExternalVpn",true)?"手机 VPN":"手机网络";}
  static void render(MainActivity a,LinearLayout box,int tab){a.hub.networkWorkspace.show(tab);}
  static void modes(MainActivity a){a.hub.networkWorkspace.reload();a.hub.networkFor(Profiles.slot(a));a.hub.networkWorkspace.networkMode(Profiles.slot(a));}
}
