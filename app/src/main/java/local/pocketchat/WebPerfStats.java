package local.pocketchat;

import org.json.JSONObject;

/** Disabled in normal use; the isolated benchmark enables these counters. */
final class WebPerfStats {
  static boolean enabled;
  static long driverCalls, transcriptCalls, entriesTransferred, scriptChars, responseChars;
  static long messageWrites, mainThreadWrites, readerPublishes, evaluateMs;
  static synchronized void reset(){enabled=true;driverCalls=transcriptCalls=entriesTransferred=scriptChars=responseChars=messageWrites=mainThreadWrites=readerPublishes=evaluateMs=0;}
  static synchronized void driver(String action,int chars){if(!enabled)return;driverCalls++;scriptChars+=chars;if(action.equals("transcript")||action.equals("web-transcript"))transcriptCalls++;}
  static synchronized void response(String action,int chars,long ms,JSONObject result){if(!enabled)return;responseChars+=chars;evaluateMs+=ms;if(action.equals("transcript")||action.equals("web-transcript")){org.json.JSONArray items=result.optJSONArray(action.equals("transcript")?"entries":"changes");if(items!=null)entriesTransferred+=items.length();}}
  static synchronized void write(){if(!enabled)return;messageWrites++;if(android.os.Looper.myLooper()==android.os.Looper.getMainLooper())mainThreadWrites++;}
  static synchronized void reader(){if(enabled)readerPublishes++;}
  static synchronized JSONObject snapshot(){return J.obj("driverCalls",driverCalls,"transcriptCalls",transcriptCalls,"entriesTransferred",entriesTransferred,"scriptChars",scriptChars,"responseChars",responseChars,"messageWrites",messageWrites,"mainThreadWrites",mainThreadWrites,"readerPublishes",readerPublishes,"evaluateCallbackMs",evaluateMs);}
}
