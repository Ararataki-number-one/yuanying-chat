package local.pocketchat;

import android.net.Uri;
import java.util.*;

/** Exact production focus methods, executed with explicit native-view adapters. */
final class FocusIntegrationHost {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static void layout(String name,MainActivity a,int toolbar,int navigation,int exit){
    check(name+" toolbar",a.toolbar.visibility==toolbar);
    check(name+" navigation",a.hub.bar.visibility==navigation&&a.hub.divider.visibility==navigation);
    check(name+" exit",a.focusExit.visibility==exit);
  }
  static MainActivity fresh(){MainActivity a=new MainActivity();a.hub=new AppHub(a);a.toolbar=new View();a.remote=new Browser();a.session=new Session();a.designChrome=new Chrome(a);a.bindFocusExit();return a;}
  static void noBrowserWork(String name,MainActivity a){
    check(name,a.remote.browserActions==0&&a.remote.historyBack==0&&a.session.browserActions==0&&a.remote.url.equals("https://chatgpt.com/c/retained"));
  }
  public static void main(String[] args){
    MainActivity a=fresh();a.applyFocusLayout();
    layout("Default chat",a,View.VISIBLE,View.VISIBLE,View.GONE);
    a.setFocusReading(true);
    check("Requested visible official document activates focus",a.focusReading&&a.focusActive());
    layout("Focused chat",a,View.GONE,View.GONE,View.VISIBLE);
    check("Focus cancels pending chrome gestures",a.designChrome.cancelled==1);
    check("Actual exit initialization exposes a descriptive accessible control",a.focusExit.description.equals("退出专注阅读，恢复应用工具栏和导航"));
    check("Focus entry announces how to exit",a.focusExit.announcement.contains("返回键或退出专注按钮"));
    noBrowserWork("Entering focus retains document without browser work",a);
    int layouts=a.hub.bar.transitions+a.hub.divider.transitions,visibilityWrites=a.hub.bar.writes+a.hub.divider.writes;
    for(int i=0;i<100;i++){a.updateReadingLayout();a.hub.keyboard();}
    check("100 unchanged layout and hub notifications cause zero navigation transitions",a.hub.bar.transitions+a.hub.divider.transitions==layouts);
    check("100 unchanged layout and hub notifications cause zero visibility writes",a.hub.bar.writes+a.hub.divider.writes==visibilityWrites);
    a.session.reading.updates=0;

    a.keyboardVisible=true;a.updateReadingLayout();
    layout("Focused keyboard",a,View.GONE,View.GONE,View.VISIBLE);
    check("Keyboard layout reaches existing reading owner",a.session.reading.keyboard&&a.session.reading.updates==1);
    a.focusExit.click.run();
    check("Actual exit button binding clears request",!a.focusReading&&!a.focusActive());
    layout("Exit while typing",a,View.VISIBLE,View.GONE,View.GONE);
    check("Exit reveals environment toolbar",a.designChrome.revealed==1);
    check("Exit announces completion",a.focusExit.announcement.equals("已退出专注阅读"));
    a.keyboardVisible=false;a.updateReadingLayout();
    layout("Keyboard dismissed",a,View.VISIBLE,View.VISIBLE,View.GONE);
    noBrowserWork("Typing and exit retain the original document",a);

    a.setFocusReading(true);a.hub.select(AppHub.SETTINGS);
    layout("Settings suspends focus",a,View.GONE,View.VISIBLE,View.GONE);
    check("Native page preserves focus request",a.focusReading&&!a.focusActive());
    check("Native page disables browser keyboard presentation",!a.session.reading.keyboard);
    a.hub.select(AppHub.CHAT);
    layout("Chat return resumes focus",a,View.GONE,View.GONE,View.VISIBLE);
    a.hub.select(AppHub.SETTINGS);int beforeSelect=a.hub.selections;a.setFocusReading(true);
    check("Focus command from settings selects chat",a.hub.page==AppHub.CHAT&&a.hub.selections==beforeSelect+1);
    layout("Focus command reaches chat",a,View.GONE,View.GONE,View.VISIBLE);

    a.remote.visible=false;a.applyFocusLayout();
    check("Empty document suspends requested focus",a.focusReading&&!a.focusActive());
    layout("Empty document keeps recovery chrome",a,View.VISIBLE,View.VISIBLE,View.GONE);
    a.remote.visible=true;a.applyFocusLayout();
    layout("Visible document resumes focus",a,View.GONE,View.GONE,View.VISIBLE);
    String[] blocked={"https://chatgpt.com/auth/login","https://accounts.google.com/","https://auth.openai.com/","https://example.com/","http://chatgpt.com/c/1","https://chatgpt.com.evil.example/c/1","https://chatgpt.com@evil.example/c/1","javascript:alert(1)"};
    for(String url:blocked){a.remote.url=url;a.applyFocusLayout();check("Suspends focus for "+url,!a.focusActive());layout("Recovery controls for "+url,a,View.VISIBLE,View.VISIBLE,View.GONE);}
    a.remote.url="https://chatgpt.com/c/retained";a.session.audit.diagnostic=true;a.applyFocusLayout();
    check("Identity diagnostic suspends focus without clearing preference",a.focusReading&&!a.focusActive());
    layout("Diagnostic return controls remain visible",a,View.VISIBLE,View.VISIBLE,View.GONE);
    a.session.audit.diagnostic=false;a.applyFocusLayout();
    layout("Returning from diagnostic resumes reading",a,View.GONE,View.GONE,View.VISIBLE);
    noBrowserWork("Workspace and recovery transitions never reload or submit",a);

    a.remote.back=true;a.onBackPressed();
    check("Back exits focus before browser history",!a.focusReading&&a.remote.historyBack==0&&a.taskMoves==0);
    layout("Back restores chrome",a,View.VISIBLE,View.VISIBLE,View.GONE);
    a.onBackPressed();check("Unfocused Back retains original browser history behavior",a.remote.historyBack==1&&a.taskMoves==0);
    a.remote.back=false;a.onBackPressed();check("Unfocused root Back moves task behind",a.taskMoves==1);

    a=fresh();a.setFocusReading(true);a.ipOverlay=true;a.onBackPressed();
    check("IP overlay consumes Back before focus",!a.ipOverlay&&a.focusReading&&a.remote.historyBack==0);
    a.environmentOverview=new Overview();a.environmentOverview.open=true;a.onBackPressed();
    check("Environment overview consumes Back before focus",!a.environmentOverview.open&&a.focusReading&&a.remote.historyBack==0);
    a.hub.select(AppHub.SETTINGS);a.onBackPressed();
    check("Native-page Back returns to requested focused chat",a.hub.page==AppHub.CHAT&&a.focusReading&&a.focusActive()&&a.remote.historyBack==0);
    noBrowserWork("Back overlay and workspace handling preserve webpage",a);

    a=fresh();a.focusReading=true;a.session=null;a.applyFocusLayout();
    layout("No session leaves recovery chrome",a,View.VISIBLE,View.VISIBLE,View.GONE);
    a=fresh();a.focusReading=true;a.remote=null;a.applyFocusLayout();
    layout("No browser leaves recovery chrome",a,View.VISIBLE,View.VISIBLE,View.GONE);
    a=new MainActivity();a.setFocusReading(true);a.applyFocusLayout();
    check("Early startup tolerates missing native and browser surfaces",a.focusReading&&!a.focusActive());
    System.out.print("{\"status\":\"passed\",\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"checks\":[");
    for(int i=0;i<checks.size();i++){if(i>0)System.out.print(",");System.out.print("{\"name\":\""+checks.get(i)+"\",\"pass\":true}");}
    System.out.println("]}");
  }
}

class BaseActivity {
  int taskMoves;
  public void onBackPressed(){}
  boolean moveTaskToBack(boolean nonRoot){taskMoves++;return true;}
}
final class MainActivity extends BaseActivity {
  boolean focusReading,keyboardVisible,ipOverlay;
  AppHub hub;View toolbar;Button focusExit;Browser remote;Session session;Chrome designChrome;Overview environmentOverview;
  int dp(int n){return n;}
  void bindFocusExit(){/* EXIT_INITIALIZATION */}
  /* PRODUCTION_METHODS */
}
class View {
  static final int VISIBLE=0,GONE=8;
  int visibility=VISIBLE,transitions,writes;String description="",announcement="";
  int getVisibility(){return visibility;}
  void setVisibility(int value){writes++;if(value!=visibility)transitions++;visibility=value;}
  void setContentDescription(String value){description=value;}
  void announceForAccessibility(String value){announcement=value;}
}
final class Button extends View {
  Runnable click;
  void setTextSize(int value){}
  void setElevation(int value){}
  void setBackground(Object value){}
}
final class DesignUi {
  static final int CARD=1,LINE=2;
  static Button button(MainActivity a,String label,boolean primary,Runnable click){Button button=new Button();button.click=click;return button;}
  static Object surface(MainActivity a,int color,int radius,int border){return new Object();}
}
final class AppHub {
  static final int CHAT=0,SETTINGS=3;
  final MainActivity a;final View bar=new View(),divider=new View();int page=CHAT,selections;
  AppHub(MainActivity a){this.a=a;}
  void select(int value){selections++;page=value;a.updateReadingLayout();}
  /* HUB_KEYBOARD */
}
final class Browser {
  boolean visible=true,back;String url="https://chatgpt.com/c/retained";int browserActions,historyBack;
  boolean hasVisibleDocument(){return visible;}
  String getUrl(){return url;}
  boolean canGoBack(){return back;}
  void goBack(){historyBack++;}
  void reload(){browserActions++;}
  void loadUrl(String value){browserActions++;url=value;}
}
final class Session {
  final Audit audit=new Audit();final Reading reading=new Reading();int browserActions;
  void reconnect(){browserActions++;}
  void navigate(String value){browserActions++;}
}
final class Audit {boolean diagnostic;boolean canReturnRequestIdentity(){return diagnostic;}}
final class Reading {boolean keyboard;int updates;void keyboard(boolean value){keyboard=value;updates++;}}
final class Chrome {
  final MainActivity a;int cancelled,revealed;
  Chrome(MainActivity a){this.a=a;}
  void cancelWebGesture(){cancelled++;}
  void reveal(){revealed++;a.toolbar.setVisibility(View.VISIBLE);a.applyFocusLayout();}
}
final class Overview {boolean open;boolean back(){boolean result=open;open=false;return result;}}
final class ExitIpPageUi {static boolean back(MainActivity a){boolean result=a.ipOverlay;a.ipOverlay=false;return result;}}
