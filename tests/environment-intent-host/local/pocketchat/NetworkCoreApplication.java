package local.pocketchat;
import org.json.JSONObject;
/** Compile boundary only. Original intent cases never admit a live core proof. */
final class NetworkCoreApplication {
  boolean current(NativeNetwork ignored){throw new AssertionError("Core application must use its separate production configuration host suite");}
  NetworkApplicationReceipt.CoreProof receipt(){throw new AssertionError("No synthetic successful core receipt in the intent suite");}
  JSONObject json(){throw new AssertionError("No synthetic core application record in the intent suite");}
}
