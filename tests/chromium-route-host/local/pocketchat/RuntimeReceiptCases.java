package local.pocketchat;
import org.json.JSONObject;
/** Calls exact production internalCurrent() without constructing Android UI.
 * Unsafe is fixture-only, bypassing Activity/Handler constructors in android.jar. */
public final class RuntimeReceiptCases {
  static int checks;
  static void check(String label,boolean result){checks++;if(!result)throw new AssertionError(label);}
  public static void main(String[] args)throws Exception{
    java.lang.reflect.Field allocator=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");allocator.setAccessible(true);
    sun.misc.Unsafe unsafe=(sun.misc.Unsafe)allocator.get(null);
    ChromiumRuntime runtime=(ChromiumRuntime)unsafe.allocateInstance(ChromiumRuntime.class);
    NativeNetwork n=new NativeNetwork();n.transport=new NetworkTransportClient();n.transport.state=new JSONObject("{\"alive\":true,\"generation\":\"a\",\"pid\":22,\"servicePid\":23,\"configuration\":\"config\",\"controllerPort\":9001,\"proxyPort\":9002}");
    n.ready=true;n.fingerprint="fingerprint";n.token="token";n.currentEntry="entry";n.routeSerial=2;n.controllerPort=9001;n.proxyPort=9002;
    n.admission=NetworkHealthPolicy.Admission.VERIFIED;
    java.lang.reflect.Field network=ChromiumRuntime.class.getDeclaredField("network");network.setAccessible(true);network.set(runtime,n);
    NativeNetwork.ExitRouteReceipt captured=new NativeNetwork.ExitRouteReceipt(n,n.transport.state);n.verifiedRoute=captured;
    check("captured verified receipt admitted",runtime.internalCurrent(captured));
    n.verifiedRoute=new NativeNetwork.ExitRouteReceipt(n,n.transport.state);
    check("normal exit re-verification retains page/download",n.verifiedRoute!=captured&&runtime.internalCurrent(captured));
    n.starting=true;check("replacement start invalidates immediately",!runtime.internalCurrent(captured));n.starting=false;
    n.routeSerial++;check("route serial change invalidates",!runtime.internalCurrent(captured));n.routeSerial--;
    n.currentEntry="replacement";check("entry change invalidates",!runtime.internalCurrent(captured));n.currentEntry="entry";
    n.transport.state.put("generation","replacement");check("service core replacement invalidates",!runtime.internalCurrent(captured));n.transport.state.put("generation","a");
    n.transport.state.put("alive",false);check("dead service invalidates",!runtime.internalCurrent(captured));n.transport.state.put("alive",true);
    n.admission=NetworkHealthPolicy.Admission.BLOCKED;check("blocked health admission invalidates",!runtime.internalCurrent(captured));n.admission=NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION;
    check("same exact route follows existing retained admission",runtime.internalCurrent(captured));n.recoveryBlocked=true;check("recovery block invalidates",!runtime.internalCurrent(captured));n.recoveryBlocked=false;
    n.verifiedRoute=null;check("missing verified receipt blocks",!runtime.internalCurrent(captured));
    System.out.println("Chromium exact runtime receipt adapter: "+checks+" checks passed");
  }
}
