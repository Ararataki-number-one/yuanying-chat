package local.pocketchat;
import android.app.Application;
import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import org.json.*;
import java.util.*;

/** Explicit fake authority. Production AppSettings behavior is checked separately. */
final class AppSettings {
  static BackgroundReplyPolicy.Snapshot authority=BackgroundReplyPolicy.Snapshot.unknown();
  static boolean failReads,failInitialization,failSet,failInitializationLocked;static int reads,initializations,sets;
  static final List<Integer> acknowledged=new ArrayList<>();
  static BackgroundReplyPolicy.Snapshot readBackgroundReplyPolicy(Context ignored){reads++;if(failReads)throw new IllegalStateException("Synthetic authority read unavailable");return authority;}
  static BackgroundReplyPolicy.Snapshot readBackgroundReplyPolicy(SQLiteDatabase ignored){return readBackgroundReplyPolicy((Context)null);}
  static BackgroundReplyPolicy.Snapshot initializeBackgroundReplyPolicy(Context ignored){initializations++;if(failInitializationLocked)throw new android.database.sqlite.SQLiteDatabaseLockedException("Synthetic initialization locked");if(failInitialization)throw new IllegalStateException("Synthetic initialization unavailable");return authority;}
  static BackgroundReplyPolicy.Snapshot setBackgroundReplyPolicy(Context ignored,boolean enabled){sets++;if(failSet||!authority.known)throw new IllegalStateException("Synthetic authority save unavailable");authority=new BackgroundReplyPolicy.Snapshot(true,enabled,authority.revision+(authority.enabled==enabled?0:1),authority.legacyPendingMask);return authority;}
  static void backgroundReplyLegacyCommitted(Context ignored,int slot){acknowledged.add(slot);authority=new BackgroundReplyPolicy.Snapshot(authority.known,authority.enabled,authority.revision,authority.legacyPendingMask&~(1<<slot));}
  static void reset(){authority=BackgroundReplyPolicy.Snapshot.unknown();failReads=failInitialization=failSet=failInitializationLocked=false;reads=initializations=sets=0;acknowledged.clear();}
}
final class ProfileCatalog {static final ProfileCatalog instance=new ProfileCatalog();static SQLiteDatabase db;static ProfileCatalog get(Context ignored){return instance;}SQLiteDatabase getWritableDatabase(){return db;}}
final class Profiles {
  static final int MAX=8;
  static int processSlot(){String name=Application.getProcessName();for(int slot=1;slot<MAX;slot++)if(name!=null&&name.endsWith(":profile"+slot))return slot;return 0;}
  static Context global(Context context){return context.getApplicationContext();}
  static Context context(Context context,int slot){return global(context).profiles[slot];}
  static Class<?> service(Context context){return SERVICES[context.slot];}
  static final Class<?>[] SERVICES={ChatService.class,ProfileChatService1.class,ProfileChatService2.class,ProfileChatService3.class,ProfileChatService4.class,ProfileChatService5.class,ProfileChatService6.class,ProfileChatService7.class};
}
final class ChatService {
  static final List<Call> calls=new ArrayList<>();static boolean wakeHeld,running;static int releases;
  static void policyChanged(Context profile,BackgroundReplyPolicy.Snapshot value){calls.add(new Call(profile.slot,value));if(!value.enabled){if(wakeHeld)releases++;wakeHeld=false;running=false;}}
  static final class Call {final int slot;final BackgroundReplyPolicy.Snapshot value;Call(int slot,BackgroundReplyPolicy.Snapshot value){this.slot=slot;this.value=value;}}
  static void reset(){calls.clear();wakeHeld=running=true;releases=0;}
}
final class ProfileChatService1 {}final class ProfileChatService2 {}final class ProfileChatService3 {}final class ProfileChatService4 {}final class ProfileChatService5 {}final class ProfileChatService6 {}final class ProfileChatService7 {}
final class NetworkTransportService {}
final class ChatSession {
  static ChatSession instance;static int gets,peeks,browserCreations;
  boolean deleted;final List<BackgroundReplyPolicy.Snapshot> changes=new ArrayList<>();
  static ChatSession peek(){peeks++;return instance;}
  static ChatSession get(Context ignored){gets++;browserCreations++;throw new AssertionError("Runtime policy must not create a browser");}
  void backgroundReplyPolicyChanged(BackgroundReplyPolicy.Snapshot value){changes.add(value);}
  static void reset(){instance=null;gets=peeks=browserCreations=0;}
}
final class QuietNotifications {static int clears;static void clearReplyDetection(Context ignored){clears++;}}
final class J {static JSONObject obj(Object... values){JSONObject result=new JSONObject();try{for(int i=0;i<values.length;i+=2)result.put((String)values[i],values[i+1]);}catch(JSONException failure){throw new IllegalStateException(failure);}return result;}}
