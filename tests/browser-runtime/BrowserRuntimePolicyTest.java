package local.pocketchat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Host migration/admission checks plus preservation of the production storage paths. */
public final class BrowserRuntimePolicyTest {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  public static void main(String[] args)throws Exception{
    check("Legacy preferences cannot choose a system engine",BrowserRuntimePolicy.usesGecko());
    check("Legacy simple display preference cannot choose a native conversation UI",BrowserRuntimePolicy.originalWebsite());
    for(String action:new String[]{"fill","submit","model-open","model-select","slider-set","history-sync","history-rename","history-delete","page-navigate","message-regenerate-submit","attachment-open","attachment-remove"})
      check("Native mutation is rejected: "+action,!BrowserRuntimePolicy.allows(action));
    for(String action:new String[]{"web-inspect","web-transcript","poll","page-state","page-restore","page-recover","attachment-state","file-prepare","file-point","file-followup"})
      check("Existing browser observation/recovery/file hook is retained: "+action,BrowserRuntimePolicy.allows(action));
    check("Existing Gecko website observations can resume",BrowserRuntimePolicy.restoresPending("gecko","","web"));
    check("A new explicit Gecko observation resumes even when an old system preference remains",BrowserRuntimePolicy.restoresPending("system","gecko","web"));
    check("A system website task cannot bind to a different browser profile",!BrowserRuntimePolicy.restoresPending("system","","web"));
    check("Unknown historical website tasks remain unresolved",!BrowserRuntimePolicy.restoresPending("","","web"));
    check("Native send and regeneration tasks are never replayed",!BrowserRuntimePolicy.restoresPending("gecko","","send")&&!BrowserRuntimePolicy.restoresPending("gecko","","regenerate"));
    String a="https://chatgpt.com/c/A";
    check("An unchanged login document can be explicitly reloaded",BrowserRuntimePolicy.sameDocument("https://accounts.google.com/signin","https://accounts.google.com/signin"));
    check("A login redirect invalidates its old reload confirmation",!BrowserRuntimePolicy.sameDocument("https://accounts.google.com/signin","https://accounts.google.com/challenge"));
    check("A changed query invalidates a captured reload document",!BrowserRuntimePolicy.sameDocument(a+"?step=1",a+"?step=2"));
    check("An unknown document cannot authorize a reload",!BrowserRuntimePolicy.sameDocument(null,null));
    check("An empty initial browser document can use normal retry",BrowserRuntimePolicy.sameDocument("",""));
    check("An unchanged blank document retains its captured identity",BrowserRuntimePolicy.sameDocument("about:blank","about:blank"));
    String fixture="http://127.0.0.1:8765/fixture?context=2";
    check("An unchanged nonofficial document retains its exact captured identity",BrowserRuntimePolicy.sameDocument(fixture,fixture));
    check("An empty captured URL rejects a newly initialized blank document",!BrowserRuntimePolicy.sameDocument("","about:blank"));
    check("An empty captured URL rejects a newly loaded document",!BrowserRuntimePolicy.sameDocument("",fixture));
    check("A blank captured document rejects a newly loaded page",!BrowserRuntimePolicy.sameDocument("about:blank",fixture));
    check("A changed nonofficial fragment invalidates its captured document",!BrowserRuntimePolicy.sameDocument(fixture+"#one",fixture+"#two"));
    check("Verified different official conversation ends the old observation",BrowserRuntimePolicy.leftConversation(a,"https://chatgpt.com/c/B",false,false));
    check("The same conversation query does not end observation",!BrowserRuntimePolicy.leftConversation(a,a+"?view=1#reply",true,true));
    check("GPT wrapper aliases retain the same conversation identity",!BrowserRuntimePolicy.leftConversation(a,"https://chatgpt.com/g/example/c/A",true,true));
    check("Homepage conversation allocation retains its original observation",!BrowserRuntimePolicy.leftConversation("https://chatgpt.com/","https://chatgpt.com/c/A",true,true));
    check("An empty homepage hydration shell retains the observation",!BrowserRuntimePolicy.leftConversation(a,"https://chatgpt.com/",false,false));
    check("An interactive empty homepage ends the old observation",BrowserRuntimePolicy.leftConversation(a,"https://chatgpt.com/",true,false));
    check("Old homepage messages do not prove a new empty conversation",!BrowserRuntimePolicy.leftConversation(a,"https://chatgpt.com/",true,true));
    for(String url:new String[]{"https://chatgpt.com/auth/login","https://example.org/c/B","http://chatgpt.com/c/B","https://user@chatgpt.com/c/B","https://chatgpt.com:444/c/B","not a URL"})
      check("Unverified destination does not discard observation: "+url,!BrowserRuntimePolicy.leftConversation(a,url,true,false));
    if(args.length>0){
      Path java=Path.of(args[0],"app/src/main/java/local/pocketchat");
      String view=Files.readString(java.resolve("GeckoWebView.java")),session=Files.readString(java.resolve("ChatSession.java"));
      check("Gecko retains the existing persistent environment profile directory",view.contains("getNoBackupFilesDir(),\"gecko-browser\"")&&view.contains("\"-profile\",directory.getAbsolutePath()"));
      check("Gecko wrapper cannot allocate or forward to a system WebView",!view.contains("new WebView(")&&!view.contains("system()")&&!view.contains("WebView legacy"));
      check("Migration keeps an archived legacy pending record without erasing its original",session.contains("putString(\"legacyPending\",pending.toString())")&&!session.substring(session.indexOf("if(pending!=null&&!BrowserRuntimePolicy.restoresPending"),session.indexOf("if(pending!=null)activeDeliveryId")).contains("remove(\"pending\")"));
      check("Passive website completion does not clear legacy native drafts",!session.contains("putString(\"draft\",\"\")"));
      check("Safe browser recovery keeps account/network scope and draft conflict protection",Files.readString(java.resolve("PageMemory.java")).contains("namespace.equals(scope())")&&Files.readString(java.resolve("PageMemory.java")).contains("result.optBoolean(\"conflict\")"));
      String files=Files.readString(java.resolve("Attachments.java"));
      check("Official picker allocates no native attachment strip or old file queue",!files.contains("new HorizontalScrollView(")&&!files.contains("new LinearLayout(")&&!files.contains("getString(\"files:")&&!files.contains("putString(\"files:"));
      check("Official picker keeps route ownership and exactly-once cancellation",files.contains("pickerEpoch==a.session.navigationEpoch")&&files.contains("callback=null;recipient.onReceiveValue")&&files.contains("callback=null;if(old!=null)old.onReceiveValue(null)"));
    }
    StringBuilder result=new StringBuilder("{\"status\":\"passed\",\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"checks\":[");
    for(int i=0;i<checks.size();i++){if(i>0)result.append(',');result.append("{\"name\":\"").append(checks.get(i)).append("\",\"pass\":true}");}
    System.out.println(result.append("]}"));
  }
}
