package local.pocketchat;
import android.content.*;import java.io.*;import java.util.*;import org.json.*;

/** Host boundaries only: these doubles do not claim SQLite/Keystore execution. */
final class TestContext extends Context {
  final int slot;final TestPrefs prefs=new TestPrefs();final Map<String,byte[]> vault=new LinkedHashMap<>();boolean browserData;
  TestContext(int slot){this.slot=slot;}public SharedPreferences getSharedPreferences(String ignored,int mode){return prefs;}
}
final class TestPrefs implements SharedPreferences {
  Map<String,Object> values=new LinkedHashMap<>();int commits,failAt=-1;
  public String getString(String k,String fallback){Object v=values.get(k);return v instanceof String?(String)v:fallback;}public int getInt(String k,int fallback){Object v=values.get(k);return v instanceof Integer?(Integer)v:fallback;}
  public Editor edit(){return new Editor(){final Map<String,Object> next=new LinkedHashMap<>(values);public Editor clear(){next.clear();return this;}public Editor putBoolean(String k,boolean v){next.put(k,v);return this;}public Editor putString(String k,String v){next.put(k,v);return this;}public Editor putInt(String k,int v){next.put(k,v);return this;}public boolean commit(){commits++;if(commits==failAt)return false;values=next;return true;}};}
}
final class EnvironmentSpec {
  final Identity identity;final JSONObject browser;EnvironmentSpec(Identity i,JSONObject b){identity=i;browser=b;}
  static final class Identity{final int slot,generation;final String environmentId;Identity(int s,String id){slot=s;generation=0;environmentId=id;}public boolean equals(Object v){return v instanceof Identity&&((Identity)v).slot==slot&&((Identity)v).environmentId.equals(environmentId);}}
  Configuration desired(){return new Configuration(browser);}static final class Configuration{final JSONObject b;Configuration(JSONObject b){this.b=b;}JSONObject browser(){return b;}}
}
final class ProfileCatalog {
  interface IdentityAction<T>{T run()throws Exception;}
  static final ProfileCatalog INSTANCE=new ProfileCatalog();final boolean[] created=new boolean[8],desktop=new boolean[8];final String[] names=new String[8],ids=new String[8];int writes;boolean replaceOnItem,failAfterAction,failAfterCommit;String replaceAfterActionField;Runnable afterAction;
  static ProfileCatalog get(Context c){return INSTANCE;}
  EnvironmentSpec.Identity identity(int slot)throws IOException{if(!created[slot])throw new IOException();return new EnvironmentSpec.Identity(slot,ids[slot]);}
  JSONObject item(int slot){if(replaceOnItem){replaceOnItem=false;ids[slot]="replacement-identity";}return J.obj("name",names[slot]);}
  void rename(int slot,String name){names[slot]=name;writes++;}void browserDisplay(int slot,boolean value){desktop[slot]=value;writes++;}
  <T>T createNew(int slot,IdentityAction<T> action)throws Exception{
    if(created[slot])throw new IOException("occupied");String oldName=names[slot],oldId=ids[slot];boolean oldDesktop=desktop[slot];created[slot]=true;ids[slot]=UUID.randomUUID().toString();
    T result;try{result=action.run();if(afterAction!=null){Runnable callback=afterAction;afterAction=null;callback.run();}if(replaceAfterActionField!=null){String field=replaceAfterActionField;replaceAfterActionField=null;Profiles.contexts[slot].prefs.values.put(field,field.equals("configRestoreGeneration")?1:"another-identity-or-batch");Profiles.contexts[slot].vault.put("foreign-pending",new byte[]{7});throw new IOException("injected failed writer superseded batch");}if(failAfterAction){failAfterAction=false;throw new IOException("injected precommit failure");}}catch(Exception error){created[slot]=false;ids[slot]=oldId;names[slot]=oldName;desktop[slot]=oldDesktop;throw error;}
    if(failAfterCommit){failAfterCommit=false;throw new IOException("injected committed but acknowledgement failed");}return result;
  }
}
final class Profiles {
  static final int MAX=8;static TestContext[] contexts=new TestContext[8];
  static Context context(Context root,int slot){return contexts[slot];}
  static void clearConfiguration(SecretStore vault){vault.context.vault.clear();}
  static final class FileCheck{static void requireUnusedBrowser(Context c)throws IOException{if(((TestContext)c).browserData)throw new IOException();}}
}
final class SecretStore {final TestContext context;SecretStore(Context c){context=(TestContext)c;}}
final class EnvironmentSpecRepository {
  static final Object[] GATES=new Object[8];static{for(int i=0;i<8;i++)GATES[i]=new Object();}static boolean failInitialize,wrongLoadedIdentity;final TestContext c;
  EnvironmentSpecRepository(Context c){this.c=(TestContext)c;}
  EnvironmentSpec load()throws Exception{return new EnvironmentSpec(wrongLoadedIdentity?new EnvironmentSpec.Identity(c.slot,"wrong"):ProfileCatalog.INSTANCE.identity(c.slot),BrowserIdentitySpec.preset(BrowserIdentitySpec.MOBILE).json());}
  void initializeCopy(EnvironmentSpec.Identity identity,JSONObject browser)throws Exception{c.vault.put("environment-spec",browser.toString().getBytes("UTF-8"));if(failInitialize)throw new IOException("injected vault failure");}
}
final class EnvironmentSpecRuntime {
  static <T>T withIntent(Context c,ProfileCatalog.IdentityAction<T> action)throws Exception{return action.run();}
  static void requireIdentity(Context c,EnvironmentSpec.Identity expected)throws Exception{if(!ProfileCatalog.INSTANCE.identity(((TestContext)c).slot).equals(expected))throw new IOException();}
}
final class EnvironmentResetActivity {static boolean rootsValid=true;static void verifyRoots(Context root,int slot)throws IOException{if(!rootsValid)throw new IOException();}}
final class AppPrefs {static JSONObject values(Context c){JSONObject out=new JSONObject();for(String key:EnvironmentConfigBackup.PREFERENCES)try{out.put(key,true);}catch(Exception e){throw new IllegalStateException(e);}return out;}}
