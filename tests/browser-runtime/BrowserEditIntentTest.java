package local.pocketchat;
import org.json.*;
public final class BrowserEditIntentTest {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  public static void main(String[] args)throws Exception{
    JSONObject b=J.obj("privacyLevel",1,"desktopSite",true);
    JSONObject metadata=J.obj("privacyLevel",1,"desktopSite",true,"name","new name",BrowserEditIntent.EDITED,BrowserEditIntent.fieldsChanged(b,1,true));
    check("B controls unchanged after failed C are metadata only",!metadata.optBoolean(BrowserEditIntent.EDITED));
    check("Metadata save preserves retained failed C",BrowserEditIntent.preserveFailedCandidate(true,metadata));
    check("Metadata B differing from running A still does not overwrite failed C",!BrowserEditIntent.browserIntent(true,metadata,true,false));
    check("Unfailed configuration does not need the preservation path",!BrowserEditIntent.preserveFailedCandidate(false,metadata));
    JSONObject explicit=J.obj("privacyLevel",0,"desktopSite",false,BrowserEditIntent.EDITED,BrowserEditIntent.fieldsChanged(b,0,false));
    check("Explicit user changes from B to C are recognized",explicit.optBoolean(BrowserEditIntent.EDITED));
    check("Explicit retry may replace the failed target",!BrowserEditIntent.preserveFailedCandidate(true,explicit));
    JSONObject backToActual=J.obj("privacyLevel",1,"desktopSite",false,BrowserEditIntent.EDITED,BrowserEditIntent.fieldsChanged(b,1,false));
    check("Explicit B-to-running-A override is still an intent",BrowserEditIntent.browserIntent(true,backToActual,false,false));
    check("Explicit failed override stays eligible for safe deferred mirroring",BrowserEditIntent.explicitFailedOverride(true,backToActual));
    check("A matching unfailed configuration does not create work",!BrowserEditIntent.browserIntent(false,backToActual,false,false));
    check("Display-only user change is explicit",BrowserEditIntent.fieldsChanged(b,1,false));
    check("Privacy-only user change is explicit",BrowserEditIntent.fieldsChanged(b,2,true));
    check("Opening an editor establishes a baseline without an edit",!BrowserEditIntent.fieldsChanged(null,1,true));
    check("Legacy callers without a captured baseline remain explicit",!BrowserEditIntent.preserveFailedCandidate(true,J.obj("privacyLevel",0,"desktopSite",false)));
    check("A string false marker is never mistaken for trusted metadata-only classification",!BrowserEditIntent.preserveFailedCandidate(true,J.obj(BrowserEditIntent.EDITED,"false")));
    System.out.println(J.obj("schema",1,"status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"scope","Production editor intent policy on JVM: accepted B, failed C, metadata preservation and explicit user override; no Android UI execution").toString());
  }
}
