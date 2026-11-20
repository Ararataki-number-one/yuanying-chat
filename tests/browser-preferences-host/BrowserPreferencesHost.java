package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.net.Uri;
import java.util.*;
import org.json.*;

/** Production preferences and dispatch, with explicit Android persistence/navigation adapters. */
public final class BrowserPreferencesHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean passed){checks.put(object("name",name,"pass",passed));}
  static JSONObject object(Object...pairs){JSONObject value=new JSONObject();try{for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);}catch(JSONException e){throw new AssertionError(e);}return value;}
  static void invalid(String name,String value){boolean rejected=false;try{BrowserPreferences.normalizeHome(value);}catch(IllegalArgumentException expected){rejected=true;}check(name,rejected);}
  static void preferences(){
    MainActivity a=new MainActivity();
    check("Existing installations retain ChatGPT enhanced by default",!BrowserPreferences.startBrowser(a));
    check("Both empty storage and blank input retain the official default website",BrowserPreferences.home(a).equals("https://chatgpt.com/")&&BrowserPreferences.normalizeHome("  ").equals(BrowserPreferences.DEFAULT_URL));
    check("Preference reads never write storage",a.store.commits==0);
    check("Bare public domain becomes HTTPS",BrowserPreferences.normalizeHome(" Example.COM/path?x=1#part ").equals("https://example.com/path?x=1#part"));
    check("Protocol-relative public URL becomes HTTPS",BrowserPreferences.normalizeHome("//example.com").equals("https://example.com/"));
    check("Explicit public HTTP remains explicit",BrowserPreferences.normalizeHome("http://example.com/page").equals("http://example.com/page"));
    check("Explicit search result URL is a website",BrowserPreferences.normalizeHome("https://www.google.com/search?q=android").equals("https://www.google.com/search?q=android"));
    check("Internationalized domain uses the actual address policy",BrowserPreferences.normalizeHome("https://例子.com/").equals(BrowserAddressPolicy.normalizeInput("https://例子.com/")));
    for(String value:new String[]{"chatgpt","some search words","what is example.com","javascript:alert(1)","file:///tmp/index.html","content://app/item","https://user:password@example.com/","https://127.0.0.1/","localhost","https://192.168.1.1/","https://example.com\\bad","https://example.com/a b","https://example.com/\nnext"})invalid("Rejects homepage input: "+value.replace('\n',' '),value);
    boolean saved=BrowserPreferences.save(a,true,"example.com/start");
    check("Browser preference and normalized homepage save in one commit",saved&&a.store.commits==1&&a.store.lastKeys.equals(new HashSet<>(Arrays.asList(BrowserPreferences.KEY_START,BrowserPreferences.KEY_HOME))));
    check("Saved Chromium choice and homepage are recalled",BrowserPreferences.startBrowser(a)&&BrowserPreferences.home(a).equals("https://example.com/start"));
    BrowserPreferences.save(a,false,"");
    check("Switching back to enhanced retains explicit old default behavior",!BrowserPreferences.startBrowser(a)&&BrowserPreferences.home(a).equals(BrowserPreferences.DEFAULT_URL));
    a.store.values.put(BrowserPreferences.KEY_START,"unknown-future-choice");a.store.values.put(BrowserPreferences.KEY_HOME,"javascript:alert(1)");
    check("Unknown stored start choices retain the enhanced default",!BrowserPreferences.startBrowser(a));
    check("Invalid old homepage falls back without changing stored bytes",BrowserPreferences.home(a).equals(BrowserPreferences.DEFAULT_URL)&&a.store.values.get(BrowserPreferences.KEY_HOME).equals("javascript:alert(1)"));
    int before=a.store.commits;boolean failed=false;try{BrowserPreferences.save(a,true,"search words");}catch(IllegalArgumentException expected){failed=true;}
    check("Invalid input cannot enter the preference write transaction",failed&&a.store.commits==before);
    a.store.commitResult=false;check("A persistence failure is propagated to the UI caller",!BrowserPreferences.save(a,true,"https://example.com/"));
    MainActivity other=new MainActivity();
    check("The supplied environment context owns all preference access",!BrowserPreferences.startBrowser(other)&&BrowserPreferences.home(other).equals(BrowserPreferences.DEFAULT_URL)&&other.store.commits==0);
  }
  static void routing(){
    MainActivity a=new MainActivity();
    check("Default Gecko route stays in the target environment",!BrowserPreferences.shouldOpenBrowser(a,new Intent()));
    BrowserPreferences.save(a,true,"example.com/home");
    check("Chromium preference dispatches plain and chat entry intents",BrowserPreferences.shouldOpenBrowser(a,null)&&BrowserPreferences.shouldOpenBrowser(a,new Intent())&&BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("openWindowAction","chat")));
    for(Intent intent:new Intent[]{new Intent().putExtra("openDownload","task"),new Intent().putExtra("openEnvironmentEditor",true),new Intent().putExtra("returnToEnvironmentList",true),new Intent().setData(Uri.parse("pocketchat://download/env0"))})check("Native task routes stay in their owning environment: "+intent.describe(),!BrowserPreferences.shouldOpenBrowser(a,intent));
    for(String action:new String[]{"edit","overview","network","settings"})check("Native action stays in its owning environment: "+action,!BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("openWindowAction",action)));
    check("A legacy Gecko override cannot change the environment binding",BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("legacyChat",true)));
    check("Reading keeps the browser engine binding",BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("openWindowAction","reading")));
    check("Unrelated data does not block selected entry",BrowserPreferences.shouldOpenBrowser(a,new Intent().setData(Uri.parse("pocketchat://unrelated/item"))));
    BrowserActivity.calls=0;boolean dispatched=a.dispatchBrowser(new Intent());
    check("Cold Chromium dispatch resumes the bound environment and finishes empty Main",dispatched&&BrowserActivity.calls==1&&BrowserActivity.owner==a&&!a.launched.hasExtra("url")&&BrowserActivity.url.isEmpty()&&a.finishes==1&&a.session==null);
    a=new MainActivity();BrowserPreferences.save(a,true,"https://example.com/warm");a.session=new ChatSession();ChatSession owner=a.session;BrowserActivity.calls=0;dispatched=a.dispatchBrowser(new Intent().putExtra("openWindowAction","chat"));
    check("Warm Chromium dispatch releases the idle Gecko Activity without resetting its session",dispatched&&BrowserActivity.calls==1&&a.finishes==1&&a.session==owner);
    a=new MainActivity();BrowserPreferences.save(a,true,"https://example.com/warm");a.session=new ChatSession();a.session.replyActive=true;a.active=true;
    BrowserActivity.calls=0;dispatched=a.dispatchBrowser(new Intent().putExtra("legacyChat",true));
    check("A running Gecko reply defers engine change even for a stale shortcut request",dispatched&&BrowserActivity.calls==0&&a.finishes==0&&a.lastMessage!=null);
    a.session.replyActive=false;a.downloads=new FileDownloads();a.downloads.awaitingPicker=true;
    check("A pending Gecko picker keeps its activity and prevents Chromium launch",a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
    a.downloads.awaitingPicker=false;a.downloads.savedActions.busy=true;
    check("Gecko saved-file work retains its owning activity",a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
    a.downloads.savedActions.busy=false;a.nativeSavedFiles=new SavedFileActions();a.nativeSavedFiles.exporting=new Object();
    check("A native file export keeps its activity and prevents Chromium launch",a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
    a.available=false;BrowserActivity.calls=0;check("Unavailable environment never dispatches or closes Main",!a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
    a=new MainActivity();BrowserActivity.calls=0;check("Default cold launch remains in original Gecko Main",!a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
  }
  static void managedChromiumRouting(){
    ChromiumEntry.delivery=true;
    try{
      MainActivity fresh=new MainActivity(6,new HashMap<>());
      check("Managed delivery still defaults fresh environments to Gecko",!fresh.dispatchBrowser(new Intent())&&fresh.launched==null);
      BrowserPreferences.save(fresh,true,"example.com/home");
      boolean handled=fresh.dispatchBrowser(new Intent().putExtra("url","https://example.com/pending"));
      check("Managed delivery with Chromium absent opens native settings without WebView",handled&&fresh.launched==null&&fresh.finishes==0&&fresh.hub!=null&&fresh.hub.feedback!=null&&"settings".equals(fresh.intent.getStringExtra("openWindowAction")));
      check("A missing module preserves the existing environment choice and homepage",BrowserPreferences.startBrowser(fresh)&&"https://example.com/home".equals(BrowserPreferences.home(fresh)));
      ChromiumEntry.moduleReady=true;
      String address="https://example.com/deep?view=1";
      handled=fresh.dispatchBrowser(new Intent().setAction(Intent.ACTION_VIEW).setData(Uri.parse(address)));
      check("Managed Chromium forwards a permitted deep link to the feature",handled&&fresh.finishes==1&&fresh.launched.target==ChromiumEntry.Feature.class&&address.equals(fresh.launched.getStringExtra("url")));
      BrowserActivity alias=new BrowserActivity();alias.slot=6;
      alias.onNewIntent(new Intent().setAction(Intent.ACTION_VIEW).setData(Uri.parse(address)));
      check("The legacy exported browser redirects to the bound native entry",alias.finishes==1&&alias.launched.target==Profiles.activity(6)&&address.equals(alias.launched.getStringExtra("url"))&&alias.newTabs==0);
      check("A native destination preserves its settings route when the module is installed",!fresh.dispatchBrowser(new Intent().putExtra("openWindowAction","settings")));
    }finally{ChromiumEntry.delivery=false;ChromiumEntry.moduleReady=false;}
  }
  static void ownerStorage(){
    Map<String,Store> storage=new HashMap<>();
    MainActivity first=new MainActivity(0,storage),second=new MainActivity(6,storage);
    first.store.values.put("persistedMarker","first-browser-data");second.store.values.put("persistedMarker","second-browser-data");
    BrowserPreferences.save(first,true,"https://example.com/first");
    check("An unset different environment still uses Gecko",!BrowserPreferences.startBrowser(second));
    check("Opening the Gecko target does not use the Chromium source binding",!second.dispatchBrowser(new Intent().putExtra("openWindowAction","chat"))&&second.launched==null);
    check("Opening the Chromium target uses its own slot and binding",first.dispatchBrowser(new Intent().putExtra("openWindowAction","chat"))&&first.launched.target==BrowserActivity.class);
    BrowserPreferences.save(second,true,"https://example.com/second");
    MainActivity restartedFirst=new MainActivity(0,storage),restartedSecond=new MainActivity(6,storage);
    check("A fresh activity reads the existing binding and homepage in each environment",BrowserPreferences.startBrowser(restartedFirst)&&BrowserPreferences.startBrowser(restartedSecond)&&BrowserPreferences.home(restartedFirst).equals("https://example.com/first")&&BrowserPreferences.home(restartedSecond).equals("https://example.com/second"));
    check("Environments using Chromium still launch different owner activities",restartedFirst.dispatchBrowser(new Intent())&&restartedSecond.dispatchBrowser(new Intent())&&restartedFirst.launched.target==BrowserActivity.class&&restartedSecond.launched.target==BrowserActivity.Profile6.class);
    BrowserPreferences.save(restartedSecond,false,"https://example.com/second");
    check("Changing one saved engine preserves both profile preference records",BrowserPreferences.startBrowser(restartedFirst)&&!BrowserPreferences.startBrowser(restartedSecond)&&restartedFirst.store.values.get("persistedMarker").equals("first-browser-data")&&restartedSecond.store.values.get("persistedMarker").equals("second-browser-data")&&storage.keySet().equals(new HashSet<>(Arrays.asList("chat","env6_chat"))));
  }
  static void deepLinks(){
    MainActivity a=new MainActivity(6,new HashMap<>());BrowserPreferences.save(a,true,"https://example.com/home");
    String requested="https://example.com/requested?x=1#section";
    Intent view=new Intent().setAction(Intent.ACTION_VIEW).setData(Uri.parse(requested));
    check("Android VIEW preserves the exact public web destination for Chromium",a.dispatchBrowser(view)&&a.launched.target==BrowserActivity.Profile6.class&&requested.equals(a.launched.getStringExtra("url")));
    String conversation="https://chatgpt.com/c/id";
    Intent notified=new Intent().putExtra("openConversation",conversation);
    check("A valid conversation destination uses the environment binding",a.dispatchBrowser(notified)&&conversation.equals(a.launched.getStringExtra("url")));
    for(String unsafe:new String[]{"javascript:alert(1)","file:///tmp/page","https://user:password@example.com/","http://127.0.0.1/private"}){
      String destination=BrowserPreferences.openingAddress(new Intent().setAction(Intent.ACTION_VIEW).setData(Uri.parse(unsafe)));
      check("Invalid VIEW data cannot be forwarded as a browser address: "+unsafe,destination==null||destination.isEmpty());
    }
    Intent management=new Intent().putExtra("openDownload","task").putExtra("url",requested);
    check("Download routing retains its owning native entry even with a URL",!a.dispatchBrowser(management));
    check("A public Android VIEW ignores unrelated management extras",requested.equals(BrowserPreferences.openingAddress(view.putExtra("openDownload","foreign"))));
    BrowserActivity incoming=new BrowserActivity();incoming.slot=6;incoming.store.values.remove(BrowserPreferences.KEY_START);incoming.runtime=null;
    incoming.onNewIntent(view);
    check("The Chromium launcher hands the validated destination to the bound Gecko profile",incoming.launches==1&&incoming.launched.target==Profiles.activity(6)&&requested.equals(incoming.launched.getStringExtra("url"))&&incoming.finishes==1&&incoming.newTabs==0);
    MainActivity gecko=new MainActivity(6,new HashMap<>());gecko.session=new ChatSession();
    check("The Gecko owner accepts the handoff without a Chromium redirect loop",!gecko.dispatchBrowser(incoming.launched));
    check("The Gecko destination reaches its existing browse handler exactly once",gecko.openWebsite(incoming.launched)&&requested.equals(gecko.session.browsed)&&gecko.pageReveals==1&&!incoming.launched.hasExtra("url")&&!gecko.openWebsite(incoming.launched));
    gecko.remote.url=requested;
    check("Sending the same website to the visible document does not reload it",gecko.openWebsite(new Intent().putExtra("url",requested))&&gecko.session.browseCalls==1&&gecko.pageReveals==1);
    BrowserActivity interrupted=new BrowserActivity();interrupted.store.values.remove(BrowserPreferences.KEY_START);interrupted.files=new BrowserFiles();interrupted.files.pending=new Object();
    interrupted.onNewIntent(view);
    check("An open file operation survives a Gecko transition request",interrupted.launches==0&&interrupted.finishes==0&&interrupted.lastMessage!=null&&interrupted.newTabs==0);
    interrupted.files.pending=null;interrupted.files.activeDownload=true;
    check("A Chromium download delays the engine transition",interrupted.dispatchBoundEngine(null)&&interrupted.launches==0&&interrupted.finishes==0);
    interrupted.files.activeDownload=false;interrupted.dispatchBoundEngine(null);
    check("A later return enters bound Gecko without forcing a URL",interrupted.launches==1&&interrupted.finishes==1&&interrupted.launched.target==MainActivity.class&&!interrupted.launched.hasExtra("url"));
    BrowserActivity removed=new BrowserActivity();removed.available=false;removed.store.values.remove(BrowserPreferences.KEY_START);removed.onNewIntent(view);
    check("An unavailable Gecko profile cannot receive a deep link",removed.launches==0&&removed.finishes==1);
  }
  static void settingsDuringFileWork(){
    MainActivity nativeHost=new MainActivity();
    check("An idle native settings host can save its engine binding",!BrowserSettingsUi.browserWorkPending(nativeHost));
    BrowserActivity chromium=new BrowserActivity();chromium.files=new BrowserFiles();
    ChromiumRuntime.owner=new ChromiumRuntime(chromium);
    chromium.files.pending=new Object();
    check("Native engine settings respect the retained Chromium document picker",BrowserSettingsUi.browserWorkPending(nativeHost));
    chromium.files.pending=null;chromium.files.activeDownload=true;
    check("Native engine settings respect the retained Chromium download",BrowserSettingsUi.browserWorkPending(nativeHost));
    ChromiumRuntime.owner.closed=true;
    check("A closed Chromium runtime does not block native engine settings",!BrowserSettingsUi.browserWorkPending(nativeHost));
    ChromiumRuntime.owner=null;ChromiumRouteLease.downloads=1;
    check("The existing Chromium download lease independently blocks an engine change",BrowserSettingsUi.browserWorkPending(nativeHost));
    ChromiumRouteLease.downloads=0;
    nativeHost.nativeSavedFiles=new SavedFileActions();nativeHost.nativeSavedFiles.exporting=new Object();
    check("An active native file export prevents changing the saved engine",BrowserSettingsUi.browserWorkPending(nativeHost));
    nativeHost.nativeSavedFiles.exporting=null;
    ChatSession.retained=new ChatSession();ChatSession.retained.replyActive=true;
    check("A retained Gecko reply still blocks an engine change",BrowserSettingsUi.browserWorkPending(nativeHost));
    ChatSession.retained.deleted=true;
    check("A retired Gecko session does not block engine settings",!BrowserSettingsUi.browserWorkPending(nativeHost));
    ChatSession.retained=null;
  }
  static void standaloneSettingsOwner(){
    Map<String,Store> stores=new HashMap<>();
    AppSettingsActivity standalone=new AppSettingsActivity(stores);
    MainActivity owner=new MainActivity(6,stores);
    EnvironmentSpec.Identity defaultOwner=new EnvironmentSpec.Identity(0,1,"default");
    EnvironmentSpec.Identity recentOwner=new EnvironmentSpec.Identity(6,2,"recent");
    ProfileCatalog.identities.put(0,defaultOwner);
    ProfileCatalog.identities.put(6,recentOwner);
    try{
      AppSettings.recent=6;
      EnvironmentSpec.Identity row=BrowserSettingsUi.workspaceIdentity(standalone);
      check("Standalone settings resolves the recent environment, away from slot zero",recentOwner.equals(row));
      AppSettings.recent=0;
      check("An owned settings page still targets its own environment",recentOwner.equals(BrowserSettingsUi.workspaceIdentity(owner)));
      BrowserSettingsUi.openWorkspace(standalone,row,()->{});
      Intent request=standalone.launched;
      check("Tapping a rendered settings row keeps its exact environment after recency changes",
          request!=null&&request.target==Profiles.activity(6)&&"settings".equals(request.getStringExtra("openWindowAction"))
          &&request.getFlags()==(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
      request.putExtra("browserSettingsOwnerSlot",0);
      check("A matching forged slot-zero extra cannot enter the private owner route on the exported activity",
          !BrowserSettingsUi.ownerOpening(new MainActivity(0,stores),request));
      request.putExtra("browserSettingsOwnerSlot",5);
      check("An owner action with a different slot cannot select the private route",
          !BrowserSettingsUi.ownerOpening(owner,request));
      request.putExtra("browserSettingsOwnerSlot",6).setAction(Intent.ACTION_VIEW);
      check("A VIEW intent cannot divert its environment into the private settings route",
          !BrowserSettingsUi.ownerOpening(owner,request));
      request.setAction(null);
      owner.setIntent(request);
      owner.handleOpening(request);
      check("A cold Gecko owner opens the pinned settings natively without creating a browser",
          owner.hub!=null&&owner.browserStarts==0&&recentOwner.equals(BrowserSettingsUi.shownOwner)&&BrowserSettingsUi.fromStandalone);
      int modalOpenings=BrowserSettingsUi.modalOpenings;
      MainActivity restored=new MainActivity(6,stores);
      restored.setIntent(request);
      restored.handleOpening(request);
      check("A restored native settings request does not replay its modal or fall back to Gecko",
          restored.hub!=null&&restored.browserStarts==0&&BrowserSettingsUi.modalOpenings==modalOpenings);

      BrowserPreferences.save(standalone,false,"https://example.com/default");
      BrowserPreferences.save(owner,true,"https://example.com/recent");
      BrowserSettingsUi.openWorkspace(owner,row,()->{});
      check("Reopening settings after dismissal keeps the standalone Chromium guard",
          BrowserSettingsUi.fromStandalone&&recentOwner.equals(BrowserSettingsUi.shownOwner));
      BrowserSettingsUi.openWorkspace(restored,row,()->{});
      check("Reopening settings after Activity recreation keeps the standalone Chromium guard",
          BrowserSettingsUi.fromStandalone&&recentOwner.equals(BrowserSettingsUi.shownOwner));

      MainActivity chromiumMenu=new MainActivity(6,stores);
      Intent menu=new Intent().putExtra("openWindowAction","settings");
      chromiumMenu.setIntent(menu);
      chromiumMenu.handleOpening(menu);
      BrowserSettingsUi.openWorkspace(chromiumMenu,row,()->{});
      check("Chromium's own settings route retains the existing engine-editing behavior",
          chromiumMenu.hub!=null&&!BrowserSettingsUi.fromStandalone&&recentOwner.equals(BrowserSettingsUi.shownOwner));

      BrowserPreferences.saveHome(owner,"https://example.com/updated");
      check("A homepage-only save retains Chromium and the default environment's homepage",
          owner.store.lastKeys.equals(Collections.singleton(BrowserPreferences.KEY_HOME))&&BrowserPreferences.startBrowser(owner)
          &&BrowserPreferences.home(owner).equals("https://example.com/updated")&&BrowserPreferences.home(standalone).equals("https://example.com/default"));

      modalOpenings=BrowserSettingsUi.modalOpenings;
      BrowserSettingsUi.openWorkspace(standalone,row,()->{});
      Intent stale=standalone.launched;
      ProfileCatalog.identities.put(6,new EnvironmentSpec.Identity(6,3,"replacement"));
      standalone.launched=null;BrowserSettingsUi.openWorkspace(standalone,row,()->{});
      check("A stale settings row cannot open the replacement environment",
          standalone.launched==null&&standalone.lastMessage!=null);
      MainActivity replaced=new MainActivity(6,stores);replaced.handleOpening(stale);
      check("A replacement environment cannot receive a previously dispatched settings modal",
          replaced.browserStarts==0&&BrowserSettingsUi.modalOpenings==modalOpenings&&replaced.lastMessage!=null);
      BrowserSettingsUi.openWorkspace(restored,BrowserSettingsUi.workspaceIdentity(restored),()->{});
      check("A retained standalone intent cannot retarget its reopened editor to a replacement environment",
          BrowserSettingsUi.modalOpenings==modalOpenings&&restored.lastMessage!=null);

      BrowserSettingsUi.openWorkspace(standalone,defaultOwner,()->{});
      check("The matching slot-zero settings entry still opens its local editor directly",
          standalone.launched==null&&defaultOwner.equals(BrowserSettingsUi.shownOwner)&&!BrowserSettingsUi.fromStandalone);
    }finally{ProfileCatalog.identities.clear();AppSettings.recent=-1;}
  }
  static void resumedDocument(){
    MainActivity owner=new MainActivity(6,new HashMap<>());BrowserPreferences.save(owner,true,"https://example.com/home");
    owner.dispatchBrowser(new Intent());Intent request=owner.launched;
    check("Resume targets the selected environment using the actual class mapping",request.owner==owner&&request.target==BrowserActivity.Profile6.class);
    check("Resume retains exactly the actual new-task and reorder flags",request.getFlags()==(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
    check("Environment re-entry has no URL or VIEW request that could force the homepage",!request.hasExtra("url")&&request.getData()==null&&request.getAction()==null);
    BrowserActivity browser=new BrowserActivity();BrowserActivity.Tab current=new BrowserActivity.Tab("https://example.com/current"),other=new BrowserActivity.Tab("https://example.com/other");
    browser.tabs.add(current);browser.tabs.add(other);browser.selected=current;List<BrowserActivity.Tab> originalTabs=new ArrayList<>(browser.tabs);
    browser.onNewIntent(request);
    check("Actual intent receiver keeps the exact selected page and all tabs on resume",browser.selected==current&&browser.tabs.equals(originalTabs)&&browser.newTabs==0&&browser.selections==0&&current.url.equals("https://example.com/current"));
    browser.onNewIntent(request);
    check("Repeated environment resume does not create or reselect a tab",browser.selected==current&&browser.tabs.equals(originalTabs)&&browser.newTabs==0&&browser.selections==0);
    browser.onNewIntent(new Intent().putExtra("url",other.url));
    check("Explicit existing-page requests still select their original tab",browser.selected==other&&browser.tabs.equals(originalTabs)&&browser.newTabs==0&&browser.selections==1);
    browser.onNewIntent(new Intent().setAction(Intent.ACTION_VIEW).setData(Uri.parse("https://example.com/requested")));
    check("Explicit VIEW destinations still reach actual new-tab dispatch",browser.selected.url.equals("https://example.com/requested")&&browser.tabs.size()==3&&browser.newTabs==1);
  }
  static BrowserActivity openedSitePermissions(){
    BrowserActivity browser=new BrowserActivity();
    browser.newTab("https://example.com/first");
    browser.selected.saved=new Object();
    browser.sitePermissions();
    return browser;
  }
  static void sitePermissionConfirmation(){
    BrowserActivity current=openedSitePermissions();
    BrowserActivity.Tab confirmed=current.selected;
    check("Permission dialog identifies the page being confirmed",current.permissionDialog.message.startsWith(confirmed.url));
    current.permissionDialog.confirm();
    check("An unchanged permission dialog reloads its original page once",
        current.retired.equals(Collections.singletonList(confirmed))&&confirmed.saved==null&&current.shown==1);

    BrowserActivity switched=openedSitePermissions();
    switched.onNewIntent(new Intent().setAction(Intent.ACTION_VIEW).setData(Uri.parse("https://example.com/second")));
    BrowserActivity.Tab next=switched.selected;
    Object saved=new Object();next.saved=saved;
    switched.permissionDialog.confirm();
    check("A permission dialog from another tab cannot reload the new selection",
        switched.selected==next&&next.saved==saved&&switched.retired.isEmpty()&&switched.shown==0);

    BrowserActivity navigated=openedSitePermissions();
    navigated.selected.generation++;
    navigated.selected.url="https://example.com/new-document";
    navigated.permissionDialog.confirm();
    check("Navigation in the same tab invalidates the old permission confirmation",navigated.retired.isEmpty()&&navigated.shown==0);

    BrowserActivity recreated=openedSitePermissions();
    recreated.selected.web=new WebView();
    recreated.permissionDialog.confirm();
    check("An old permission dialog cannot retire a replacement WebView",recreated.retired.isEmpty()&&recreated.shown==0);

    BrowserActivity reentered=openedSitePermissions();
    reentered.customViewClosed=()->reentered.onNewIntent(new Intent().putExtra("url","https://example.com/reentered"));
    reentered.permissionDialog.confirm();
    check("A page change during full-screen dismissal invalidates confirmation",
        reentered.selected.url.equals("https://example.com/reentered")&&reentered.retired.isEmpty()&&reentered.shown==0);
  }
  public static void main(String[]args){preferences();routing();managedChromiumRouting();ownerStorage();deepLinks();settingsDuringFileWork();standaloneSettingsOwner();resumedDocument();sitePermissionConfirmation();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(object("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);}
}

final class Store implements SharedPreferences {
  final Map<String,String> values=new HashMap<>();Set<String> lastKeys=new HashSet<>();int commits;boolean commitResult=true;
  public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}
  public Editor edit(){return new Editor(){final Map<String,String> staged=new HashMap<>();public Editor putString(String key,String value){staged.put(key,value);return this;}public boolean commit(){commits++;lastKeys=new HashSet<>(staged.keySet());values.putAll(staged);return commitResult;}};}
}
final class ProfileContext {
  final int slot;
  ProfileContext(int slot){this.slot=slot;}
  /* PROFILE_STORAGE_NAME */
}
class MainActivity extends Activity {
  final Store store;ChatSession session;boolean available=true,active;final int slot;Intent launched;
  FileDownloads downloads;
  SavedFileActions nativeSavedFiles;
  String lastMessage;
  int pageReveals;
  EnvironmentOverviewUi environmentOverview;
  AppHub hub;
  int browserStarts;
  Object browserStartup;
  void openNativeWorkspace(Intent settings){hub=new AppHub();BrowserSettingsUi.showRequestedOwner(this,settings);}
  void closeNativeWorkspace(){}
  void prepareBrowserAfterOverview(){}
  void openNotification(Intent intent){}
  void createChatUi(){browserStarts++;}
  final GeckoWeb remote=new GeckoWeb();
  void showPage(boolean ignored){pageReveals++;}
  void fileFeedback(String value){lastMessage=value;}
  MainActivity(){this(0,new HashMap<>());}
  MainActivity(int slot,Map<String,Store> storage){this.slot=slot;store=storage.computeIfAbsent(new ProfileContext(slot).name("chat"),key->new Store());}
  @Override public SharedPreferences getSharedPreferences(String name,int mode){if(!name.equals("chat"))throw new AssertionError("Unexpected global preference access");return store;}
  @Override public void startActivity(Intent intent){launched=intent;BrowserActivity.calls++;BrowserActivity.owner=this;BrowserActivity.url=intent.hasExtra("url")?intent.getStringExtra("url"):"";}
  /* HANDLE_OPENING */
  /* DISPATCH_METHOD */
  /* NATIVE_PENDING */
  /* GECKO_PENDING */
  /* GECKO_OPEN_WEBSITE */
  /* CHAT_URL */
}
class ChatSession {
  static ChatSession retained;
  static ChatSession peek(){return retained;}
  boolean replyActive,navigationFailed,deleted;
  String browsed;
  int browseCalls;
  boolean currentReplyActive(){return replyActive;}
  boolean browse(String url,String notice){browsed=url;browseCalls++;return true;}
}
class GeckoWeb {String url;String getUrl(){return url;}}
class ProfileUi {static boolean working(ChatSession session){return false;}}
class FileDownloads {boolean awaitingPicker,retiringPartial;final SavedFileActions savedActions=new SavedFileActions();}
class SavedFileActions {Object exporting;boolean busy;}
class BrowserFiles {Object pending;boolean activeDownload;boolean hasActiveDownload(){return activeDownload;}}
class EnvironmentOverviewUi {EnvironmentOverviewUi(MainActivity owner){}boolean consume(Intent intent){return false;}}
class AppHub {
  String feedback;
  void feedback(String message,boolean warning){feedback=message;}
  void settings(){}
}
class ChromiumEntry {
  static class Feature {}
  static boolean delivery,moduleReady;
  static String networkIssue(Activity owner){return "Chromium environment network needs configuration";}
  static boolean managed(Activity owner){return delivery;}
  static boolean open(Activity owner,String url){
    if(!moduleReady)return false;
    MainActivity main=(MainActivity)owner;
    main.launched=new Intent(owner,Feature.class).putExtra("url",url);
    return true;
  }
}
class BrowserSettingsUi {
  static EnvironmentSpec.Identity shownOwner;
  static boolean fromStandalone;
  static int modalOpenings;
  private static void show(Activity owner,EnvironmentSpec.Identity expected,Runnable refresh,boolean standalone){
    if(!current(owner,expected)||Profiles.slot(owner)!=expected.slot){unavailable(owner);return;}
    shownOwner=expected;fromStandalone=standalone;modalOpenings++;
  }
  /* SETTINGS_OWNERSHIP */
  /* SETTINGS_WORK_PENDING */
}
class AppSettingsActivity extends Activity {
  final Store store;
  Intent launched;
  String lastMessage;
  AppSettingsActivity(Map<String,Store> storage){store=storage.computeIfAbsent("chat",unused->new Store());}
  @Override public SharedPreferences getSharedPreferences(String name,int mode){return store;}
  @Override public void startActivity(Intent intent){launched=intent;}
}
class AppSettings {
  static int recent=-1;
  static int recentSlot(Activity owner){return recent;}
}
class EnvironmentSpec {
  static final class Identity {
    final int slot,generation;
    final String environmentId;
    Identity(int slot,int generation,String environmentId){
      this.slot=slot;this.generation=generation;this.environmentId=environmentId;
    }
    @Override public boolean equals(Object other){
      return other instanceof Identity value&&slot==value.slot&&generation==value.generation&&environmentId.equals(value.environmentId);
    }
    @Override public int hashCode(){return Objects.hash(slot,generation,environmentId);}
  }
}
class DesignUi {
  static void message(Activity owner,String title,String detail){
    if(owner instanceof MainActivity)((MainActivity)owner).lastMessage=detail;
    else if(owner instanceof AppSettingsActivity)((AppSettingsActivity)owner).lastMessage=detail;
  }
}
class ChromiumRuntime {
  static ChromiumRuntime owner;
  final Activity activity;
  boolean closed;
  ChromiumRuntime(Activity activity){this.activity=activity;}
}
class ChromiumRouteLease {
  static int downloads;
  static Snapshot snapshot(){return new Snapshot(downloads);}
  static final class Snapshot {
    final int downloads;
    Snapshot(int downloads){this.downloads=downloads;}
  }
}
class Profiles {
  static int slot(Activity owner){return owner instanceof MainActivity?((MainActivity)owner).slot:owner instanceof BrowserActivity?((BrowserActivity)owner).slot:0;}
  static Class<?> activity(int slot){if(slot==0)return MainActivity.class;if(slot==6)return Profile6.class;throw new AssertionError("Unexpected environment slot "+slot);}
  static final class Profile6 extends MainActivity {}
}
class ProfileCatalog {
  static final Map<Integer,EnvironmentSpec.Identity> identities=new HashMap<>();
  Activity owner;
  EnvironmentSpec.Identity identity(int slot)throws java.io.IOException{
    EnvironmentSpec.Identity identity=identities.get(slot);
    if(identity==null)throw new java.io.IOException("Unavailable fixture environment");
    return identity;
  }
  static ProfileCatalog get(Activity activity){ProfileCatalog c=new ProfileCatalog();c.owner=activity;return c;}
  boolean available(int slot){if(slot!=Profiles.slot(owner))throw new AssertionError("Wrong profile availability lookup");return owner instanceof MainActivity?((MainActivity)owner).available:((BrowserActivity)owner).available;}
}
class BrowserActivity extends Activity {
  static int calls;static Activity owner;static String url;
  static class Profile1 extends BrowserActivity {}static class Profile2 extends BrowserActivity {}
  static class Profile3 extends BrowserActivity {}static class Profile4 extends BrowserActivity {}
  static class Profile5 extends BrowserActivity {}static class Profile6 extends BrowserActivity {}
  static class Profile7 extends BrowserActivity {}
  static class Tab {String url;long generation;WebView web=new WebView();Object saved;Tab(String value){url=value;}}
  final List<Tab> tabs=new ArrayList<>();Tab selected;int newTabs,selections,slot;final Store store=new Store();
  BrowserActivity(){store.values.put(BrowserPreferences.KEY_START,BrowserPreferences.START_BROWSER);}
  @Override public SharedPreferences getSharedPreferences(String name,int mode){return store;}
  void select(Tab tab){selections++;selected=tab;}
  void newTab(String url){newTabs++;selected=new Tab(url);tabs.add(selected);}
  boolean destroyed,available=true;
  Object runtime=new Object(),fingerprintFileResult;
  BrowserFiles files;
  Intent launched;
  int launches;
  String lastMessage;
  @Override public void startActivity(Intent value){launched=value;launches++;}
  TestDialog permissionDialog;
  Runnable customViewClosed=()->{};
  final List<Tab> retired=new ArrayList<>();
  int shown;
  void hideCustomView(){customViewClosed.run();}
  void retire(Tab tab){retired.add(tab);}
  void showSelected(){shown++;}
  void updateChrome(){}
  void message(String value){lastMessage=value;}
  /* BROWSER_LIVE */
  /* BROWSER_NAVIGATION_CURRENT */
  /* BROWSER_SITE_PERMISSIONS */
  /* BROWSER_ACTIVITY */
  /* BROWSER_RESUME */
  /* BROWSER_OPEN */
  /* BROWSER_INTENT_ADDRESS */
  /* BROWSER_PENDING_FILE */
  /* BROWSER_ENGINE_DISPATCH */
  /* BROWSER_OPEN_ADDRESS */
  /* BROWSER_NEW_INTENT */
}

final class WebView {}
final class AppAppearance {
  static TestDialog dialog(BrowserActivity activity){return activity.permissionDialog=new TestDialog();}
}
final class TestDialog {
  interface ClickListener {void click(TestDialog dialog,int which);}
  String message;
  ClickListener positive;
  TestDialog setTitle(String text){return this;}
  TestDialog setMessage(String text){message=text;return this;}
  TestDialog setNegativeButton(String text,ClickListener click){return this;}
  TestDialog setPositiveButton(String text,ClickListener click){positive=click;return this;}
  void show(){}
  void confirm(){positive.click(this,-1);}
}
