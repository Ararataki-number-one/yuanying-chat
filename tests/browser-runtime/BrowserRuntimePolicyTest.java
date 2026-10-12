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
