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
    check("Default enhanced route never dispatches automatically",!BrowserPreferences.shouldOpenBrowser(a,new Intent()));
    BrowserPreferences.save(a,true,"example.com/home");
    check("Chromium preference dispatches plain and chat entry intents",BrowserPreferences.shouldOpenBrowser(a,null)&&BrowserPreferences.shouldOpenBrowser(a,new Intent())&&BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("openWindowAction","chat")));
    for(Intent intent:new Intent[]{new Intent().putExtra("legacyChat",true),new Intent().putExtra("openConversation","https://chatgpt.com/c/id"),new Intent().putExtra("openConversation",""),new Intent().putExtra("openDownload","task"),new Intent().putExtra("openEnvironmentEditor",true),new Intent().putExtra("returnToEnvironmentList",true),new Intent().setData(Uri.parse("pocketchat://notification/env0")),new Intent().setData(Uri.parse("pocketchat://download/env0"))})check("Original task/legacy intent bypasses Chromium: "+intent.describe(),!BrowserPreferences.shouldOpenBrowser(a,intent));
    for(String action:new String[]{"edit","network","settings","unknown",""})check("Explicit action stays in original interface: "+action,!BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("openWindowAction",action)));
    check("False legacy flag and unrelated data do not block selected entry",BrowserPreferences.shouldOpenBrowser(a,new Intent().putExtra("legacyChat",false).setData(Uri.parse("pocketchat://unrelated/item"))));
    BrowserActivity.calls=0;boolean dispatched=a.dispatchBrowser(new Intent());
    check("Cold Chromium dispatch opens the selected environment homepage and finishes empty Main",dispatched&&BrowserActivity.calls==1&&BrowserActivity.owner==a&&BrowserActivity.url.equals("https://example.com/home")&&a.finishes==1&&a.session==null);
    a=new MainActivity();BrowserPreferences.save(a,true,"https://example.com/warm");a.session=new ChatSession();ChatSession owner=a.session;BrowserActivity.calls=0;dispatched=a.dispatchBrowser(new Intent().putExtra("openWindowAction","chat"));
    check("Warm Chromium dispatch preserves the exact running Gecko session",dispatched&&BrowserActivity.calls==1&&a.finishes==0&&a.session==owner);
    BrowserActivity.calls=0;int reads=ProfileCatalog.reads;dispatched=a.dispatchBrowser(new Intent().putExtra("legacyChat",true));
    check("Chromium return legacy flag cannot create a redirect loop",!dispatched&&BrowserActivity.calls==0&&a.finishes==0&&a.session==owner&&ProfileCatalog.reads==reads);
    a.available=false;BrowserActivity.calls=0;check("Unavailable environment never dispatches or closes Main",!a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
    a=new MainActivity();BrowserActivity.calls=0;check("Default cold launch remains in original enhanced Main",!a.dispatchBrowser(new Intent())&&BrowserActivity.calls==0&&a.finishes==0);
  }
  public static void main(String[]args){preferences();routing();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(object("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);}
}

final class Store implements SharedPreferences {
  final Map<String,String> values=new HashMap<>();Set<String> lastKeys=new HashSet<>();int commits;boolean commitResult=true;
  public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}
  public Editor edit(){return new Editor(){final Map<String,String> staged=new HashMap<>();public Editor putString(String key,String value){staged.put(key,value);return this;}public boolean commit(){commits++;lastKeys=new HashSet<>(staged.keySet());values.putAll(staged);return commitResult;}};}
}
class MainActivity extends Activity {
  final Store store=new Store();ChatSession session;boolean available=true;int slot;
  @Override public SharedPreferences getSharedPreferences(String name,int mode){if(!name.equals("chat"))throw new AssertionError("Unexpected global preference access");return store;}
  /* DISPATCH_METHOD */
}
class ChatSession {}
class Profiles {static int slot(MainActivity owner){return owner.slot;}}
class ProfileCatalog {static int reads;MainActivity owner;static ProfileCatalog get(MainActivity activity){ProfileCatalog c=new ProfileCatalog();c.owner=activity;return c;}boolean available(int slot){reads++;return owner.available;}}
class BrowserActivity {static int calls;static Activity owner;static String url;static void open(Activity activity,String address){calls++;owner=activity;url=address;}}
