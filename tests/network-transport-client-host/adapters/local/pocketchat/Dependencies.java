package local.pocketchat;
import android.content.*;import java.util.*;
/* BEGIN_LIFECYCLE_IDENTITY_BOUNDARY
final class EnvironmentSpec {
 static final class Identity {
  final int slot=-1;
  private Identity(){throw new AssertionError("Bound owner identity is outside the original lifecycle host");}
  org.json.JSONObject json(){throw new AssertionError("No synthetic successful owner identity in the original lifecycle host");}
 }
}
END_LIFECYCLE_IDENTITY_BOUNDARY */
// run.py extracts the declaration above only for the original 92 lifecycle
// cases. The separate bound-client host compiles the actual production model,
// so this file must not declare another executable EnvironmentSpec class.
final class Profiles {static int slot(Context ignored){return 1;}}
final class NetworkTransportService {static final int COMMAND=1,REPLY=2,EVENT=3;}
final class NetworkDiagnostics {
 static final String UNKNOWN="unknown";enum Source{CONTROL}enum Stage{BIND,IPC,START,SEND,REPLY}
 enum Reason{UNKNOWN,CANCELLED,CONTROL_UNAVAILABLE}
 enum Event{IPC_CONNECTED,IPC_DETACH,IPC_BIND_INTERRUPTED,IPC_REPLY_INTERRUPTED,IPC_DISCONNECTED,IPC_BINDING_DIED,IPC_NULL_BINDING,IPC_BIND_REJECTED,IPC_BIND_EXCEPTION,IPC_BIND_TIMEOUT,IPC_FOREGROUND_REJECTED,IPC_SEND_FAILED,IPC_REPLY_TIMEOUT,IPC_REPLY_FAILED,IPC_REMOTE_REJECTED}
 final List<Event> events=Collections.synchronizedList(new ArrayList<>());void record(Event event,String generation,Reason reason,Stage stage,long value){events.add(event);}
}
final class NetworkDiagnosticStore {static NetworkDiagnostics forContext(Context ignored,NetworkDiagnostics.Source source){return new NetworkDiagnostics();}static void bind(NetworkDiagnostics ignored,Context c){}}
