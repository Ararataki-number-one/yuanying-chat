package local.pocketchat;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONObject;

/** Synthetic persistence failures through the actual environment editor save methods. */
public final class EnvironmentEditorSaveHost {
  private static int checks, failures;

  public static void main(String[] args) throws Exception {
    MainActivity nativeEditor=new MainActivity();
    nativeEditor.prefs.failKey="wifiDownloads";
    boolean nativeSaved=EnvironmentEditorUi.applyNative(nativeEditor,nativeEditor.catalog.identity(1),input(),new EditText());
    check("Native preference failure is reported and catalog writes roll back",
        !nativeSaved&&nativeEditor.catalog.name.equals("Original")&&nativeEditor.catalog.notes.isEmpty()
        &&nativeEditor.catalog.draft.equals("pending editor draft")&&!nativeEditor.status.contains("已保存"));
    nativeEditor.prefs.failKey="";
    check("Retry saves the same native editor values and retains its previous Gecko draft",
        EnvironmentEditorUi.applyNative(nativeEditor,nativeEditor.catalog.identity(1),input(),new EditText())
        &&nativeEditor.prefs.getBoolean("wifiDownloads",false)&&nativeEditor.catalog.name.equals("Edited")
        &&nativeEditor.catalog.notes.equals("Edited note")&&nativeEditor.catalog.draft.equals("pending editor draft"));

    MainActivity gecko=new MainActivity();
    gecko.session=new ChatSession(gecko);
    gecko.prefs.failKey="wifiDownloads";
    boolean geckoSaved=EnvironmentEditorUi.apply(gecko,input(),new EditText());
    check("Gecko preference failure keeps the editor draft and does not apply a browser policy",
        !geckoSaved&&gecko.catalog.draft.equals("pending editor draft")&&gecko.catalog.name.equals("Original")
        &&gecko.session.applied==0&&gecko.session.identitySaves==0&&!gecko.status.contains("已保存"));
    check("Gecko preference failure attempts one commit without persisting a partial browser edit",
        gecko.prefs.writeAttempts==1&&!gecko.prefs.values.containsKey("privacyLevel"));
    gecko.prefs.failKey="";
    check("A successful retry saves prefs and browser policy together, then clears the draft",
        EnvironmentEditorUi.apply(gecko,input(),new EditText())&&gecko.prefs.writeAttempts==2
        &&Integer.valueOf(2).equals(gecko.prefs.values.get("privacyLevel"))&&gecko.catalog.desktop
        &&gecko.catalog.draft.isEmpty()&&gecko.session.applied==1&&gecko.session.identitySaves==1);

    MainActivity deferred=new MainActivity();
    deferred.session=new ChatSession(deferred);
    deferred.session.browserBusy=true;
    deferred.prefs.values.put("nextPrivacyLevel",0);
    deferred.prefs.failKey="wifiDownloads";
    check("A failed preference commit preserves a previously deferred browser edit",
        !EnvironmentEditorUi.apply(deferred,input(),new EditText())
        &&Integer.valueOf(0).equals(deferred.prefs.values.get("nextPrivacyLevel"))
        &&deferred.catalog.draft.equals("pending editor draft")&&deferred.session.identitySaves==0);
    deferred.prefs.failKey="";
    check("Retry stages browser settings without touching the live Gecko policy",
        EnvironmentEditorUi.apply(deferred,input(),new EditText())
        &&Integer.valueOf(2).equals(deferred.prefs.values.get("nextPrivacyLevel"))
        &&Boolean.TRUE.equals(deferred.prefs.values.get("nextDesktopSite"))&&deferred.session.applied==0
        &&deferred.session.identitySaves==1&&!deferred.catalog.desktop&&deferred.catalog.draft.isEmpty());

    MainActivity preserved=new MainActivity();
    preserved.session=new ChatSession(preserved);
    preserved.session.identity.queueUnavailable=true;
    preserved.prefs.values.put("nextPrivacyLevel",0);
    JSONObject metadata=input().put(BrowserEditIntent.EDITED,false);
    check("Metadata-only save leaves an inaccessible queued template available for retry",
        EnvironmentEditorUi.apply(preserved,metadata,new EditText())
        &&Integer.valueOf(0).equals(preserved.prefs.values.get("nextPrivacyLevel"))
        &&preserved.session.applied==0&&preserved.session.identitySaves==0);

    MainActivity obsolete=new MainActivity();
    obsolete.session=new ChatSession(obsolete);
    obsolete.catalog.generation++;
    boolean staleSaved=EnvironmentEditorUi.apply(obsolete,input(),new EditText());
    check("A stale Gecko session cannot write the catalog, preferences, or draft of a replacement",
        !staleSaved&&obsolete.catalog.name.equals("Original")&&obsolete.catalog.draft.equals("pending editor draft")
        &&obsolete.prefs.writeAttempts==0&&obsolete.session.applied==0);
    check("Stale Gecko recovery cannot archive its page draft into a new generation",
        !EnvironmentEditorUi.archiveEditorDraft(obsolete.session,"https://example.com/","old draft",1)
        &&obsolete.catalog.archivedDrafts==0);

    MainActivity late=new MainActivity();
    late.session=new ChatSession(late);
    late.catalog.failDetails=true;
    boolean detailsSaved;
    try{detailsSaved=EnvironmentEditorUi.apply(late,input(),new EditText());}
    catch(RuntimeException rejected){detailsSaved=true;}
    check("A catalog write error is reported without erasing the edit draft or writing preferences",
        !detailsSaved&&late.catalog.name.equals("Original")&&late.catalog.draft.equals("pending editor draft")
        &&late.prefs.writeAttempts==0);

    MainActivity unconfirmed=new MainActivity();
    unconfirmed.session=new ChatSession(unconfirmed);
    unconfirmed.catalog.failCommit=true;
    check("A SQLite acknowledgement failure is reported even after the preference store has committed",
        !EnvironmentEditorUi.apply(unconfirmed,input(),new EditText())
        &&unconfirmed.prefs.getBoolean("wifiDownloads",false)
        &&unconfirmed.catalog.name.equals("Original")&&unconfirmed.catalog.draft.equals("pending editor draft")
        &&unconfirmed.session.applied==0);
    unconfirmed.catalog.failCommit=false;
    check("Retry after an uncertain save restores a consistent catalog and preference result",
        EnvironmentEditorUi.apply(unconfirmed,input(),new EditText())
        &&unconfirmed.catalog.name.equals("Edited")&&unconfirmed.catalog.draft.isEmpty()
        &&unconfirmed.session.applied==1);

    System.out.println(J.obj("passed",checks-failures,"total",checks,"actualAndroidExecution",false));
    if(failures>0)System.exit(1);
  }

  private static JSONObject input(){
    return J.obj("name","Edited","group","Work","notes","Edited note","wifiDownloads",true,
        "privacyLevel",2,"desktopSite",true);
  }

  private static void check(String name,boolean passed){
    checks++;
    if(!passed){failures++;System.err.println("FAIL "+name);}
  }
}

class Context {
  final SharedPreferences prefs=new SharedPreferences();
  SharedPreferences getSharedPreferences(String name,int mode){return prefs;}
}
class MainActivity extends Context {
  final ProfileCatalog catalog=new ProfileCatalog();
  ChatSession session;
  AppHub hub=new AppHub();
  DesignChrome designChrome=new DesignChrome();
  String status="";
  boolean isDestroyed(){return false;}
  boolean isFinishing(){return false;}
  void status(String message){status=message;}
}
class EditText {
  void setError(String message){}
}
class AppHub {void refresh(){}}
class DesignChrome {void update(){}}
class Profiles {
  static int slot(Context context){return 1;}
  static Context context(Context owner,int slot){
    if(slot!=1)throw new AssertionError("The fixture's Activity owns slot 1");
    return owner;
  }
  static void rename(MainActivity activity,int slot,String name){activity.catalog.name=name;}
}
class EnvironmentSpec {
  static final class Identity {
    final int slot,generation;
    final String environmentId;
    Identity(int slot,int generation,String environmentId){
      this.slot=slot;this.generation=generation;this.environmentId=environmentId;
    }
    @Override public boolean equals(Object value){
      return value instanceof Identity other&&slot==other.slot&&generation==other.generation&&environmentId.equals(other.environmentId);
    }
    @Override public int hashCode(){return java.util.Objects.hash(slot,generation,environmentId);}
  }
}
class ProfileCatalog {
  interface IdentityAction<T>{T run()throws Exception;}
  int generation,archivedDrafts;
  String name="Original",group="",notes="",draft="pending editor draft";
  boolean desktop,failDetails,failCommit;
  static ProfileCatalog get(Context context){return ((MainActivity)context).catalog;}
  EnvironmentSpec.Identity identity(int slot)throws IOException{
    if(slot!=1)throw new IOException("Unavailable slot");
    return new EnvironmentSpec.Identity(slot,generation,"verified-environment");
  }
  <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{
    if(!expected.equals(identity(expected.slot)))throw new IOException("Stale environment");
    String oldName=name,oldGroup=group,oldNotes=notes,oldDraft=draft;boolean oldDesktop=desktop;
    try{
      T result=action.run();
      if(failCommit)throw new IOException("Synthetic SQLite commit failure");
      return result;
    }catch(Exception failure){name=oldName;group=oldGroup;notes=oldNotes;draft=oldDraft;desktop=oldDesktop;throw failure;}
  }
  void rename(int slot,String value){name=value;}
  void details(int slot,String group,String notes){
    if(failDetails)throw new IllegalStateException("Synthetic SQLite write failure");
    this.group=group;this.notes=notes;
  }
  void browserDisplay(int slot,boolean desktop){this.desktop=desktop;}
  void draft(int slot,JSONObject value){draft=value==null?"":value.toString();}
  void heartbeat(ChatSession session,boolean fresh){}
}
class SharedPreferences {
  final Map<String,Object> values=new HashMap<>();
  String failKey="";
  int writeAttempts;
  boolean getBoolean(String key,boolean fallback){
    return values.get(key) instanceof Boolean bool?bool:fallback;
  }
  long getLong(String key,long fallback){
    return values.get(key) instanceof Long number?number:fallback;
  }
  Editor edit(){return new Editor();}
  class Editor {
    final Map<String,Object> updates=new HashMap<>();
    Editor putInt(String key,int value){updates.put(key,value);return this;}
    Editor putLong(String key,long value){updates.put(key,value);return this;}
    Editor putBoolean(String key,boolean value){updates.put(key,value);return this;}
    Editor remove(String key){updates.put(key,null);return this;}
    boolean commit(){
      writeAttempts++;
      if(updates.containsKey(failKey))return false;
      updates.forEach((key,value)->{if(value==null)values.remove(key);else values.put(key,value);});
      return true;
    }
  }
}
class ChatSession {
  final MainActivity context;
  final int environmentGeneration;
  final String environmentId="verified-environment";
  final SharedPreferences prefs;
  final Privacy privacy=new Privacy();
  final Audit audit=new Audit();
  final IdentityStatus identity=new IdentityStatus();
  boolean identityApplicationPending,networkReady=true,deleted,browserBusy;
  int applied,identitySaves;
  ChatSession(MainActivity owner){context=owner;prefs=owner.prefs;environmentGeneration=owner.catalog.generation;}
  void browserIdentitySaved(int level,boolean desktop){identitySaves++;}
  void applyBrowserSettings(boolean protectionChanged){applied++;}
}
class Privacy {
  int level(){return 1;}
  boolean wantsDesktop(){return false;}
}
class IdentityStatus {boolean queueUnavailable;}
class Audit {void refresh(boolean fresh){}}
class DraftArchive {
  final MainActivity owner;
  DraftArchive(MainActivity owner){this.owner=owner;}
  static DraftArchive get(MainActivity owner){return new DraftArchive(owner);}
  boolean save(String url,String body,String source,long revision){owner.catalog.archivedDrafts++;return true;}
}
class DeferredBrowserSettings {
  static final String NEXT_PRIVACY_LEVEL="nextPrivacyLevel",NEXT_DESKTOP_SITE="nextDesktopSite";
  static boolean save(ChatSession session,int level,boolean desktop){
    return session.prefs.edit().putInt("nextPrivacyLevel",level).putBoolean("nextDesktopSite",desktop).commit();
  }
  static void cancel(ChatSession session){
    session.prefs.edit().remove("nextPrivacyLevel").remove("nextDesktopSite").commit();
  }
}
class EnvironmentEditorUi {
  static boolean browserBusy(ChatSession session){return session.browserBusy;}
  /* EDITOR_MEMBERS */
}
class AppPrefs {
  /* PREFS_MEMBERS */
}
class J {
  static JSONObject obj(Object... data){
    JSONObject result=new JSONObject();
    try{for(int i=0;i<data.length;i+=2)result.put((String)data[i],data[i+1]);}
    catch(Exception error){throw new IllegalArgumentException(error);}
    return result;
  }
}
