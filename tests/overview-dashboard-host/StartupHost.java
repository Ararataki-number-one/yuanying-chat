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
    ProfileCatalog.available=false;MainActivity deleted=new MainActivity(true);deleted.onCreate(new Bundle());check(deleted.finished&&deleted.creates==0,"deleted or resetting environment cannot create browser");ProfileCatalog.available=true;

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
  static final int MODE_PRIVATE=0;boolean pageMode,active,destroyed,finished;int creates,resumes,content;BrowserStartupGate browserStartup;ChatSession session;EnvironmentOverviewUi environmentOverview;Intent intent;Prefs prefs;
  MainActivity(boolean manual){intent=new Intent(manual);}
  Intent getIntent(){return intent;}void setIntent(Intent value){intent=value;}boolean isFinishing(){return finished;}void finish(){finished=true;}void setContentView(LinearLayout v){content++;}Prefs getSharedPreferences(String name,int mode){return new Prefs();}Window getWindow(){return new Window();}void startActivity(Intent value){}
  void createChatUi(){creates++;session=new ChatSession();if(active)resumeChatUi();}void resumeChatUi(){resumes++;}void openNotification(Intent i){}
  /*ACTUAL_ENTRY_METHODS*/
}
class Activity {public void onCreate(Bundle b){}protected void onResume(){}protected void onNewIntent(Intent i){}}
class Bundle{}class ChatSession{}class WindowHomeActivity{}class Window{void setDecorFitsSystemWindows(boolean b){}}
class Build{static class VERSION{static int SDK_INT=35;}}
class LinearLayout{LinearLayout(MainActivity a){}void setBackgroundColor(int color){}}
class ReferenceUi{static int CHAT_BG;}
class Prefs{boolean getBoolean(String k,boolean v){return v;}Prefs edit(){return this;}Prefs putBoolean(String k,boolean v){return this;}void apply(){}}
class Intent{static int FLAG_ACTIVITY_NEW_TASK=1;final boolean manual;Intent(boolean v){manual=v;}Intent(MainActivity a,Class<?> c){manual=false;}Intent addFlags(int f){return this;}}
class Profiles{static int slot(MainActivity a){return 0;}}
class ProfileCatalog{static boolean available=true;static ProfileCatalog get(MainActivity a){return new ProfileCatalog();}boolean available(int slot){return available;}}
class ExitIpPageUi{static void close(MainActivity a){}}
class EnvironmentOverviewUi {
  OverviewIdentity state=new OverviewIdentity();boolean shown;Runnable draw;EnvironmentOverviewUi(MainActivity a){}
  boolean consume(Intent i){shown=i.manual;return shown;}void afterFirstFrame(Runnable r){draw=r;}void paint(){if(draw!=null)draw.run();}
}

class OverviewIdentity{String environmentId="A";int slot=0,generation=1;}
