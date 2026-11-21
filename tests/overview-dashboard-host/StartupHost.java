package local.pocketchat;
import java.util.*;

/** Extracted production entry/lifecycle methods, with declared platform/browser doubles. */
public final class StartupHost {
  static int checks;
  static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
  public static void main(String[] args){
    MainActivity cold=new MainActivity(true);cold.onCreate(new Bundle());
    check(cold.content==1&&cold.environmentOverview.shown&&cold.creates==0,"manual launch paints native content before browser creation");
    cold.onResume();check(cold.creates==0,"foreground alone cannot start before first native draw");
    cold.environmentOverview.paint();check(cold.creates==1&&cold.resumes==1,"first native frame starts exactly one foreground browser");
    cold.environmentOverview.paint();cold.onResume();check(cold.creates==1,"repeated frames and resumes retain original browser");
    MainActivity background=new MainActivity(true);background.onCreate(new Bundle());background.onResume();
    background.active=false;background.browserStartup.foreground(false);background.environmentOverview.paint();
    check(background.creates==0,"frame while paused cannot create a background browser");background.onResume();check(background.creates==1,"resume completes deferred startup once");
    MainActivity retired=new MainActivity(true);retired.onCreate(new Bundle());retired.onResume();retired.destroyed=true;retired.browserStartup.close();retired.environmentOverview.paint();check(retired.creates==0,"destroyed Activity cannot be revived by old draw callback");
    MainActivity normal=new MainActivity(false);normal.onCreate(new Bundle());check(normal.creates==1&&!normal.environmentOverview.shown,"notification or normal opening adds no overview delay");
    MainActivity arriving=new MainActivity(true);arriving.onCreate(new Bundle());Intent notification=new Intent(false);arriving.onNewIntent(notification);check(arriving.getIntent()==notification&&!arriving.finished&&arriving.creates==0,"incoming intent is retained during native startup without finishing the Activity");
    MainActivity replaced=new MainActivity(true);replaced.onCreate(new Bundle());replaced.onResume();Runnable oldFrame=replaced.environmentOverview.draw;replaced.onNewIntent(new Intent(true));oldFrame.run();check(replaced.creates==0,"retired overview draw cannot authorize a replacement dashboard");replaced.environmentOverview.paint();check(replaced.creates==1,"replacement dashboard starts only after its own native frame");
    ProfileCatalog.available=false;MainActivity deleted=new MainActivity(true);deleted.onCreate(new Bundle());check(deleted.finished&&deleted.creates==0,"deleted or resetting environment cannot create browser");ProfileCatalog.available=true;

    MainActivity chromium=new MainActivity(true);chromium.chromium=true;chromium.allowLegacyFixture();chromium.onCreate(null);
    check(chromium.finished&&chromium.creates==0&&chromium.browserStarts==1&&chromium.launched.target==BrowserActivity.class&&!chromium.launched.extras.containsKey("url"),"cold Chromium selection resumes the browser without forcing a URL or creating Gecko");
    MainActivity pendingExport=new MainActivity(false);pendingExport.chromium=true;
    Bundle exportState=new Bundle();exportState.pending=new SavedFileActions(pendingExport);exportState.pending.exporting=new Object();
    pendingExport.onCreate(exportState);
    check(!pendingExport.finished&&pendingExport.browserStarts==0&&pendingExport.creates==0
      &&pendingExport.hub.page==AppHub.SETTINGS&&pendingExport.nativeSavedFiles==exportState.pending
      &&pendingExport.restoredSavedFiles==null,"Recreated interrupted export uses the native workspace without opening a browser");
    MainActivity warm=new MainActivity(false);warm.onCreate(null);ChatSession retained=warm.session;warm.sessionUi=new UiFrames();warm.onResume();check(warm.sessionUi.visible,"resumed session requests its presentation frame");
    Intent browserIntent=new Intent(false);warm.chromium=true;warm.allowLegacyFixture();warm.onNewIntent(browserIntent);
    check(warm.finished&&warm.session==retained&&warm.creates==1&&warm.browserStarts==1&&!warm.launched.extras.containsKey("url"),"warm dispatch closes the idle Gecko Activity without replacing its retained session or forcing a URL");
    warm.onResume();check(warm.browserStarts==1,"the finishing Gecko Activity must not launch Chromium again");

    MainActivity busy=new MainActivity(false);busy.onCreate(null);busy.onResume();busy.session.working=true;busy.chromium=true;busy.allowLegacyFixture();
    busy.onNewIntent(new Intent(false).putExtra("url","https://destination.example/work"));
    check(!busy.finished&&busy.browserStarts==0&&busy.feedback==1&&busy.session.browses==0,"an active Gecko operation keeps its page and shows how to reopen under the new binding");
    busy.session.working=false;busy.onResume();
    check(busy.finished&&busy.browserStarts==1&&!busy.launched.extras.containsKey("url"),"later resume uses the binding without replaying an earlier deferred link");

    MainActivity nativePage=new MainActivity(false);nativePage.chromium=true;nativePage.allowLegacyFixture();nativePage.intent.putExtra("openDownload","old-file");nativePage.onCreate(null);nativePage.onResume();
    check("old-file".equals(nativePage.nativeDownload)&&nativePage.hub.page==AppHub.SETTINGS&&nativePage.creates==0&&nativePage.browserStarts==0&&nativePage.hub.refreshes==1,"Chromium-bound download management stays native from cold entry through resume");
    MainActivity ownerSettings=new MainActivity(false);
    ownerSettings.intent.putExtra("openWindowAction","settings").putExtra("fixtureOwnerSettings","true");
    ownerSettings.onCreate(null);
    check(ownerSettings.hub.page==AppHub.SETTINGS&&ownerSettings.creates==0&&ownerSettings.browserStarts==0
      &&ownerSettings.ownerSettingsRequests==1,"owner settings open the native workspace for a Gecko environment");
    MainActivity restoredOwner=new MainActivity(false);
    restoredOwner.setIntent(ownerSettings.getIntent());restoredOwner.onCreate(null);
    check(restoredOwner.hub.page==AppHub.SETTINGS&&restoredOwner.creates==0&&restoredOwner.ownerSettingsRequests==0,
      "recreating owner settings keeps its native route without reissuing the modal");
    MainActivity restoredNative=new MainActivity(false);restoredNative.chromium=true;restoredNative.setIntent(nativePage.getIntent());restoredNative.onCreate(null);
    check(restoredNative.hub.page==AppHub.SETTINGS&&restoredNative.creates==0&&restoredNative.browserStarts==0,"a recreated native Activity keeps its destination without starting an engine or reopening the dialog");
    nativePage.nativeSavedFiles.busy=true;nativePage.onNewIntent(new Intent(false));
    check(nativePage.browserStarts==0&&!nativePage.finished&&nativePage.feedback==1,"Chromium entry cannot interrupt a native file operation");
    nativePage.chromium=false;nativePage.onNewIntent(new Intent(false));
    check(nativePage.creates==0&&nativePage.nativeSavedFiles.busy&&nativePage.feedback==2,"Gecko entry cannot interrupt the same native file operation");
    nativePage.chromium=true;nativePage.nativeSavedFiles.busy=false;
    nativePage.onNewIntent(new Intent(false).putExtra("openWindowAction","network"));
    check(nativePage.hub.page==AppHub.NETWORK&&nativePage.session==null&&nativePage.browserStarts==0,"network management reuses the native route without creating an engine");
    nativePage.onNewIntent(new Intent(false));
    check(nativePage.finished&&nativePage.browserStarts==1&&nativePage.creates==0,"an explicit browser entry from a native page opens the bound Chromium session");

    String link="https://destination.example/path?keep=1#section";
    MainActivity geckoLink=new MainActivity(false);geckoLink.intent.action=Intent.ACTION_VIEW;geckoLink.intent.data=link;geckoLink.onCreate(null);
    check(geckoLink.creates==1&&geckoLink.session.browses==1&&link.equals(geckoLink.session.lastUrl)&&geckoLink.intent.data==null,"a cold Gecko opening consumes the explicit URL once");
    geckoLink.onResume();geckoLink.onNewIntent(new Intent(false));
    check(geckoLink.session.browses==1&&geckoLink.browserStarts==0,"ordinary Gecko resume preserves the current document and consumed link");
    MainActivity chromiumLink=new MainActivity(false);chromiumLink.chromium=true;chromiumLink.allowLegacyFixture();chromiumLink.intent.putExtra("url",link);chromiumLink.onCreate(null);
    check(chromiumLink.finished&&chromiumLink.creates==0&&chromiumLink.browserStarts==1&&link.equals(chromiumLink.launched.extras.get("url")),"a cold Chromium opening forwards the exact page URL instead of selecting the homepage");
    check((chromium.launched.flags&Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)!=0&&(warm.launched.flags&Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)!=0,"cold and warm entry reuse the existing browser task");
    MainActivity installed=new MainActivity(false);installed.chromium=true;installed.managedChromium=true;installed.chromiumReady=true;installed.intent.putExtra("url",link);installed.onCreate(null);
    check(installed.finished&&installed.creates==0&&installed.browserStarts==0&&link.equals(installed.featureUrl),"installed Chromium receives the link without launching the legacy browser or Gecko");
    MainActivity missing=new MainActivity(false);missing.chromium=true;missing.managedChromium=true;missing.onCreate(null);missing.onResume();
    check(!missing.finished&&missing.creates==0&&missing.browserStarts==0&&missing.hub.page==AppHub.SETTINGS&&missing.hub.noticeError&&missing.hub.notice.contains("组件尚未就绪"),"missing Chromium opens native settings with component feedback");
    MainActivity officialNoSplit=new MainActivity(false);officialNoSplit.chromium=true;officialNoSplit.flags.legacyFixture=true;officialNoSplit.onCreate(null);
    check(!officialNoSplit.finished&&officialNoSplit.creates==0&&officialNoSplit.browserStarts==0&&officialNoSplit.hub.page==AppHub.SETTINGS,
      "Production rejects legacy WebView even when the fixture metadata is present");
    MainActivity unflaggedTest=new MainActivity(false);unflaggedTest.chromium=true;unflaggedTest.packageName="local.pocketchat.test";unflaggedTest.onCreate(null);
    check(!unflaggedTest.finished&&unflaggedTest.creates==0&&unflaggedTest.browserStarts==0&&unflaggedTest.hub.page==AppHub.SETTINGS,
      "The test package still requires the exact fixture metadata flag");
    MainActivity corrupt=new MainActivity(false);corrupt.engineUnreadable=true;corrupt.onCreate(null);
    check(!corrupt.finished&&corrupt.creates==0&&corrupt.browserStarts==0&&corrupt.hub.page==AppHub.SETTINGS&&corrupt.hub.notice.contains("无法读取"),
      "Unreadable binding opens neither browser, and root settings indicate the actual cause");
    MainActivity restricted=new MainActivity(false);restricted.chromium=true;restricted.managedChromium=true;restricted.chromiumNetworkIssue="Network configuration required";restricted.onCreate(null);
    check(!restricted.finished&&restricted.creates==0&&restricted.browserStarts==0&&restricted.hub.page==AppHub.SETTINGS&&restricted.hub.noticeError&&restricted.chromiumNetworkIssue.equals(restricted.hub.notice),"managed Chromium reports the specific network problem in native settings");
    MainActivity focused=new MainActivity(true);focused.onCreate(new Bundle(true));check(focused.focusReading&&focused.creates==0,"native focus preference restores before deferred Gecko startup");

    BrowserStartupGate gate=new BrowserStartupGate("A",0,1);check(gate.matches("A",0,1)&&!gate.matches("B",0,1)&&!gate.matches("A",1,1)&&!gate.matches("A",0,2),"startup identity cannot cross environment, slot or generation");check(!gate.take(),"new gate starts nothing");gate.frame();check(!gate.take(),"draw without foreground starts nothing");gate.foreground(true);check(gate.take()&&!gate.take(),"gate issues a single start");
    BrowserStartupGate never=new BrowserStartupGate("A",0,1);never.close();never.foreground(true);never.frame();check(!never.take(),"closed gate stays closed");
    PageLoadingWait wait=new PageLoadingWait();check(!wait.update(true,0),"empty page starts a real monotonic wait");
    for(long now=1000;now<20000;now+=1000)check(!wait.update(true,now),"progress updates never extend wait budget");
    check(wait.update(true,20000)&&wait.update(true,90000),"long wait exposes help and stays honest");check(!wait.update(false,91000),"live page immediately clears empty-page hint");
    check(!wait.update(true,92000)&&!wait.update(true,111999)&&wait.update(true,112000),"new empty document gets its own bounded hint window");
    check(!wait.update(true,1)&&!wait.update(true,20000)&&wait.update(true,20001),"monotonic clock reset is handled without negative delay");
    System.out.println("{\"checks\":"+checks+",\"actualAndroidExecution\":false,\"actualGeckoExecution\":false}");
  }
}

class MainActivity extends Activity {
  static final int MODE_PRIVATE=0;boolean pageMode,active,destroyed,finished,focusReading,chromium;Bundle downloadUiState;UiFrames sessionUi;int creates,resumes,content,feedback,ownerSettingsRequests;String nativeDownload;BrowserStartupGate browserStartup;ChatSession session;EnvironmentOverviewUi environmentOverview;Intent intent;Prefs prefs;
  AppHub hub;FileDownloads downloads;SavedFileActions nativeSavedFiles,restoredSavedFiles;Remote remote;final Handler handler=new Handler();
  boolean managedChromium,chromiumReady,engineUnreadable;String featureUrl,chromiumNetworkIssue="";
  void allowLegacyFixture(){packageName="local.pocketchat.test";flags.legacyFixture=true;}
  MainActivity(boolean manual){intent=new Intent(manual);}
  Intent getIntent(){return intent;}void setIntent(Intent value){intent=value;}boolean isFinishing(){return finished;}void finish(){finished=true;}void setContentView(LinearLayout v){content++;}Prefs getSharedPreferences(String name,int mode){return new Prefs();}Window getWindow(){return new Window();}
  void createChatUi(){creates++;session=new ChatSession();remote=new Remote();openWebsite(getIntent());if(active)resumeChatUi();}
  void resumeChatUi(){resumes++;}void openNotification(Intent i){openWebsite(i);}
  void showNativeDownload(String id){nativeDownload=id;}
  void fileFeedback(String value){feedback++;}void showPage(boolean value){}
  /*ACTUAL_ENTRY_METHODS*/
}
class Context {String packageName="local.pocketchat";final Bundle flags=new Bundle();String getPackageName(){return packageName;}}
class AppVersion {static Bundle metadata(Context context){return context.flags;}}
class Activity extends Context {Intent launched;int browserStarts;void startActivity(Intent value){launched=value;if(value.target==BrowserActivity.class)browserStarts++;}public void onCreate(Bundle b){}protected void onResume(){}protected void onNewIntent(Intent i){}}
class Bundle{SavedFileActions pending;boolean focused,legacyFixture;boolean getBoolean(String name){return "local.pocketchat.LEGACY_WEBVIEW_FIXTURE".equals(name)&&legacyFixture;}Bundle(){}Bundle(boolean focused){this.focused=focused;}boolean getBoolean(String name,boolean fallback){return "focusReading".equals(name)?focused:fallback;}Bundle getBundle(String name){return null;}}
class ChatSession{boolean working,navigationFailed,reply;int browses;String lastUrl;boolean currentReplyActive(){return reply;}boolean browse(String url,String label){browses++;lastUrl=url;return true;}}
class ProfileUi{static boolean working(ChatSession session){return session.working;}}
class Remote{String getUrl(){return "https://retained.example/";}}
class FileDownloads{boolean awaitingPicker,retiringPartial;final SavedFileActions savedActions=new SavedFileActions(null);}
class SavedFileActions{Object exporting;boolean busy;SavedFileActions(MainActivity a){}void close(){}static SavedFileActions restore(MainActivity a,Bundle state){return state==null?null:state.pending;}}
/** Controlled native owner-settings boundary. The real owner and identity checks are covered separately. */
class BrowserSettingsUi {
  static final String OWNER_ROUTE="fixtureOwnerSettings", OWNER_MODAL="fixtureOwnerSettingsConsumed";
  static boolean ownerOpening(Activity activity,Intent intent){
    return intent!=null&&"settings".equals(intent.getStringExtra("openWindowAction"))&&intent.getBooleanExtra(OWNER_ROUTE,false);
  }
  static void showRequestedOwner(MainActivity activity,Intent intent){
    if(!ownerOpening(activity,intent)||intent.getBooleanExtra(OWNER_MODAL,false))return;
    intent.putExtra(OWNER_MODAL,"true");activity.ownerSettingsRequests++;
  }
}
class EnvironmentEditorUi{static void show(MainActivity a){}}
class AppHub{
  static final int CHAT=0,SETTINGS=3,NETWORK=4;int page,refreshes;
  final Runnable tick=()->{};final NetworkWorkspace networkWorkspace=new NetworkWorkspace();final Visibility bar=new Visibility();
  String notice="";boolean noticeError;
  AppHub(MainActivity a,LinearLayout root,Object chat){}
  void downloadsVisible(boolean value){}void refresh(){refreshes++;}void show(int value){page=value;}
  void feedback(String message,boolean error){if(page!=CHAT){notice=message;noticeError=error;}}
}
class NetworkWorkspace{int slot=-1;void focus(int value){slot=value;}void close(){}}
class Visibility{void setVisibility(int value){}}
class View{static final int GONE=8,VISIBLE=0;}
class DesignUi{static LinearLayout screen(MainActivity a){return new LinearLayout(a);}static void chrome(MainActivity a){}}

class Handler{void removeCallbacks(Runnable value){}void post(Runnable value){}}
class WindowHomeActivity{}class Window{void setDecorFitsSystemWindows(boolean b){}}
class Build{static class VERSION{static int SDK_INT=35;}}
class LinearLayout{LinearLayout(MainActivity a){}void setBackgroundColor(int color){}}
class ReferenceUi{static int CHAT_BG;static void insets(MainActivity a,LinearLayout root,java.util.function.Consumer<Boolean> keyboard){}}
class Prefs{boolean getBoolean(String k,boolean v){return v;}Prefs edit(){return this;}Prefs putBoolean(String k,boolean v){return this;}void apply(){}}
class Intent{
  static final int FLAG_ACTIVITY_NEW_TASK=1,FLAG_ACTIVITY_REORDER_TO_FRONT=2;static final String ACTION_VIEW="android.intent.action.VIEW";
  final boolean manual;Class<?> target;int flags;String action,data;final Map<String,String> extras=new HashMap<>();
  Intent(){this(false);}Intent(boolean v){manual=v;}Intent(Activity a,Class<?> c){manual=false;target=c;}
  Intent addFlags(int f){flags|=f;return this;}Intent putExtra(String key,String value){extras.put(key,value);return this;}
  String getAction(){return action;}String getStringExtra(String name){return extras.get(name);}boolean getBooleanExtra(String name,boolean fallback){return extras.containsKey(name)?Boolean.parseBoolean(extras.get(name)):fallback;}boolean hasExtra(String key){return extras.containsKey(key);}void removeExtra(String key){extras.remove(key);}void setData(String value){data=value;}
}
class Profiles{static int slot(Activity a){return 0;}}
class ProfileCatalog{static boolean available=true;static ProfileCatalog get(MainActivity a){return new ProfileCatalog();}boolean available(int slot){return available;}}
class ExitIpPageUi{static void close(MainActivity a){}}
class EnvironmentOverviewUi {
  OverviewIdentity state=new OverviewIdentity();ChatSession owner;boolean shown;Runnable draw;EnvironmentOverviewUi(MainActivity a){}
  boolean consume(Intent i){shown=i.manual;return shown;}void afterFirstFrame(Runnable r){draw=r;}void paint(){if(draw!=null)draw.run();}void resume(){}void close(){}
}

class OverviewIdentity{String environmentId="A";int slot=0,generation=1;}

/** Controlled preference and intent inputs; engine routing and browser task launches are production methods. */
enum EnvironmentEngine {GECKO,CHROMIUM,UNAVAILABLE}
class BrowserPreferences{
  static EnvironmentEngine engine(MainActivity activity){return activity.engineUnreadable?EnvironmentEngine.UNAVAILABLE:activity.chromium?EnvironmentEngine.CHROMIUM:EnvironmentEngine.GECKO;}
  static boolean startBrowser(MainActivity activity){return engine(activity)==EnvironmentEngine.CHROMIUM;}
  static boolean nativeOpening(Intent intent){if(intent==null)return false;String action=intent.getStringExtra("openWindowAction");return intent.hasExtra("openDownload")||"network".equals(action)||"settings".equals(action)||"downloads".equals(action);}
  static boolean shouldOpenBrowser(MainActivity activity,Intent intent){return startBrowser(activity)&&!nativeOpening(intent);}
  static String openingAddress(Intent intent){return intent==null||nativeOpening(intent)?null:Intent.ACTION_VIEW.equals(intent.getAction())?intent.data:intent.extras.get("url");}
}
/** The Android split availability and launch result are controlled in this host. */
class ChromiumEntry{
  static boolean managed(MainActivity activity){return activity.managedChromium;}
  static boolean open(Activity host,String url){
    MainActivity activity=(MainActivity)host;
    if(!activity.chromiumReady)return false;
    activity.featureUrl=url;
    return true;
  }
  static String networkIssue(MainActivity activity){return activity.chromiumNetworkIssue;}
}
class BrowserActivity{static Class<?> activity(int slot){return BrowserActivity.class;}/*ACTUAL_BROWSER_LAUNCHES*/}
class UiFrames{boolean visible;void visible(boolean value){visible=value;}}
