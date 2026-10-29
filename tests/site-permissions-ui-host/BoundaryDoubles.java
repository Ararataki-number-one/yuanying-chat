package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.Handler;
import android.widget.*;
import java.util.*;
import org.mozilla.geckoview.*;

/** Declared app edges only; production adapters compile against the real Android framework. */
class MainActivity extends Activity {
  ChatSession session;GeckoWebView remote;boolean active;
  int dp(int value){return value;}
  TextView label(String text,int size,int color){return null;}
}
class ChatSession {
  static ChatSession peek(){return null;}
  boolean deleted,navigating,uiVisible;int environmentGeneration;long navigationEpoch;
  String environmentId,lastDocumentId;Context context;Handler handler;GeckoWebView web;
}
class GeckoWebView {
  ChatSession owner;GeckoSession current;GeckoRuntime runtime;boolean destroyed,ready;
  MutableContextWrapper displayContext;long identityPolicyRevision;
  Set<GeckoSession> crashed,pendingLoads;
  Map<GeckoSession,String> locations;Map<GeckoSession,Object> ports;
  Map<GeckoSession,Long> appearanceLoads;
  boolean hasVisibleDocument(){return false;}
  boolean isShown(){return false;}
}
class EnvironmentSpec {static class Identity {int generation;String environmentId;Identity(int slot,int generation,String id){}}}
class ProfileCatalog {
  static ProfileCatalog get(Context context){return null;}
  EnvironmentSpec.Identity identity(int slot)throws java.io.IOException{return null;}
  interface IdentityAction<T>{T run()throws Exception;}
  <T>T withIdentity(EnvironmentSpec.Identity identity,IdentityAction<T> action)throws Exception{return action.run();}
}
class Profiles {static int slot(Context context){return 0;}static String display(Context context,int slot){return "";}}
class EnvironmentIdentityUi {static boolean current(MainActivity activity,ChatSession owner){return false;}}
class EnvironmentAuditUi {static Button button(MainActivity activity,LinearLayout body,String text){return null;}}
class AppAppearance {static AlertDialog.Builder dialog(MainActivity activity){return null;}}
class Ui {static int INK,MUTED;}
