package local.pocketchat;

import android.Manifest;
import android.app.*;
import android.net.Uri;
import android.webkit.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

/** Complete production helper with explicit Android lifecycle, dialogs and grants. */
public final class BrowserPermissionsHost {
  static final String CAMERA=Manifest.permission.CAMERA,AUDIO=Manifest.permission.RECORD_AUDIO,COARSE=Manifest.permission.ACCESS_COARSE_LOCATION;
  static final String VIDEO=PermissionRequest.RESOURCE_VIDEO_CAPTURE,MIC=PermissionRequest.RESOURCE_AUDIO_CAPTURE;
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static final class Request extends PermissionRequest {
    final String origin;final String[] resources;int grants,denials;String[] selected;Runnable denied;
    Request(String origin,String... resources){this.origin=origin;this.resources=resources;}
    public Uri getOrigin(){return Uri.parse(origin);}public String[] getResources(){return resources;}
    public void grant(String[] values){grants++;selected=values;}
    public void deny(){denials++;if(denied!=null)denied.run();}
  }
  static final class Location implements GeolocationPermissions.Callback {int calls;String origin;boolean granted,remember;public void invoke(String origin,boolean granted,boolean remember){calls++;this.origin=origin;this.granted=granted;this.remember=remember;}}
  static final class Fixture implements AutoCloseable {
    final Activity a=new Activity();final WebView view=new WebView("https://example.com/page?version=1");final AtomicReference<WebView> active=new AtomicReference<>(view);final List<String> messages=new ArrayList<>();final BrowserPermissions permissions=new BrowserPermissions(a,active::get,messages::add);
    Request camera(){return new Request("https://example.com/",VIDEO);}
    void request(Request request){permissions.request(view,request);}void allow(){permissions.pending.dialog.positive();}void reject(){permissions.pending.dialog.negative();}
    int code(){return permissions.pending.requestCode;}public void close(){permissions.close();}
  }
  public static void main(String[] args){
    try(Fixture f=new Fixture()){
      f.a.granted.add(CAMERA);Request request=f.camera();f.request(request);
      check("Native site consent is mandatory despite existing Android grant",request.grants==0&&f.permissions.pending!=null&&f.a.requests==0);
      check("Consent identifies exact HTTPS origin",f.permissions.pending.dialog.message.contains("https://example.com"));
      f.allow();check("User consent grants only requested camera",request.grants==1&&request.denials==0&&Arrays.equals(request.selected,new String[]{VIDEO})&&f.permissions.pending==null);
      Request second=f.camera();f.request(second);check("New request needs new site consent",second.grants==0&&f.permissions.pending!=null);f.reject();check("Site rejection denies once",second.denials==1&&second.grants==0);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);f.allow();int code=f.code();
      check("Only missing camera Android permission is requested",f.a.requests==1&&Arrays.equals(f.a.lastPermissions,new String[]{CAMERA})&&request.grants==0);
      f.a.granted.add(CAMERA);check("Matching runtime callback handled",f.permissions.result(code,new String[]{CAMERA},new int[]{0}));
      check("Runtime grant completes native request once",request.grants==1&&request.denials==0&&f.permissions.pending==null);
      f.permissions.result(code,new String[]{CAMERA},new int[]{0});check("Duplicate runtime callback cannot grant twice",request.grants==1);
      check("Unrelated request code is not consumed",!f.permissions.result(73,new String[0],new int[0]));
    }
    try(Fixture f=new Fixture()){
      f.a.granted.add(CAMERA);Request request=new Request("https://example.com",VIDEO,MIC,VIDEO,"android.webkit.resource.PROTECTED_MEDIA_ID");f.request(request);f.allow();
      check("Only missing microphone requested from Android",Arrays.equals(f.a.lastPermissions,new String[]{AUDIO}));
      int code=f.code();f.a.granted.add(AUDIO);f.permissions.result(code,new String[]{AUDIO},new int[]{0});
      check("Unsupported and duplicate resources are never granted",Arrays.equals(request.selected,new String[]{VIDEO,MIC})&&request.grants==1);
      Request unsupported=new Request("https://example.com","android.webkit.resource.PROTECTED_MEDIA_ID");f.request(unsupported);check("Unsupported-only request immediately denied",unsupported.denials==1&&f.permissions.pending==null);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);f.allow();int code=f.code();f.permissions.result(code,new String[]{CAMERA},new int[]{-1});
      check("Android denial immediately denies native request",request.denials==1&&request.grants==0&&!f.messages.isEmpty());
      Request fake=f.camera();f.request(fake);f.allow();f.permissions.result(f.code(),new String[]{CAMERA},new int[]{0});
      check("Result array cannot replace actual Android permission state",fake.denials==1&&fake.grants==0);
    }
    try(Fixture f=new Fixture()){
      Request request=new Request("https://example.com",VIDEO,MIC);f.request(request);f.allow();int code=f.code();f.a.granted.add(CAMERA);f.a.granted.add(AUDIO);f.permissions.result(code,new String[]{CAMERA},new int[]{0});
      check("Partial runtime result cannot satisfy larger requested list",request.denials==1&&request.grants==0);
      Request spoof=new Request("https://example.com",VIDEO,MIC);f.a.granted.clear();f.request(spoof);f.allow();code=f.code();f.a.granted.add(CAMERA);f.a.granted.add(AUDIO);f.permissions.result(code,new String[]{CAMERA,CAMERA},new int[]{0,0});
      check("Duplicate runtime names cannot satisfy missing microphone result",spoof.denials==1&&spoof.grants==0);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);f.allow();int code=f.code();f.permissions.onNavigation(f.view);f.a.granted.add(CAMERA);f.permissions.result(code,new String[]{CAMERA},new int[]{0});
      check("Same-URL navigation cancels old request generation",request.denials==1&&request.grants==0&&f.permissions.pending==null);
      Request changed=f.camera();f.a.granted.clear();f.request(changed);f.allow();code=f.code();f.view.url="https://example.com/page?version=2";f.a.granted.add(CAMERA);f.permissions.result(code,new String[]{CAMERA},new int[]{0});
      check("URL change rejects stale result even without navigation hook",changed.denials==1&&changed.grants==0);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);f.allow();int code=f.code();f.active.set(new WebView(f.view.url));f.a.granted.add(CAMERA);f.permissions.result(code,new String[]{CAMERA},new int[]{0});
      check("Active tab identity invalidates permission result",request.denials==1&&request.grants==0);
      Request background=f.camera();f.request(background);check("Background tab cannot open a consent dialog",background.denials==1&&f.permissions.pending==null);
    }
    try(Fixture f=new Fixture()){
      Request cross=new Request("https://other.example",VIDEO);f.request(cross);check("Cross-origin iframe request refused",cross.denials==1&&f.permissions.pending==null);
      f.view.url="http://example.com/page";Request plain=new Request("http://example.com",VIDEO);f.request(plain);check("HTTP document cannot request sensitive permissions",plain.denials==1);
      f.view.url="https://127.0.0.1/page";Request local=new Request("https://127.0.0.1",VIDEO);f.request(local);check("Private-origin permission request refused",local.denials==1);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);AlertDialog dialog=f.permissions.pending.dialog;f.a.application.pause(f.a);
      check("Backgrounding native consent denies and dismisses",request.denials==1&&f.permissions.pending==null&&!dialog.showing);
      f.a.application.resume(f.a);Request next=f.camera();f.request(next);check("Resume permits a fresh request",f.permissions.pending!=null&&next.denials==0);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);f.allow();int code=f.code();f.a.application.pause(f.a);
      check("System permission pause preserves scoped pending request",f.permissions.pending!=null&&request.denials==0&&!f.permissions.foreground);
      f.a.granted.add(CAMERA);f.permissions.result(code,new String[]{CAMERA},new int[]{0});
      check("Paused runtime result never grants before resume",request.grants==0&&f.permissions.pending.resultReady);
      f.a.application.resume(f.a);check("Resume revalidates then grants current document",request.grants==1&&request.denials==0&&f.permissions.pending==null);
    }
    try(Fixture f=new Fixture()){
      Request request=f.camera();f.request(request);f.allow();int code=f.code();f.a.application.pause(f.a);f.a.application.stop(f.a);f.a.granted.add(CAMERA);f.permissions.result(code,new String[]{CAMERA},new int[]{0});f.a.application.resume(f.a);
      check("Actual stopped activity cannot recover abandoned grant",request.denials==1&&request.grants==0&&f.permissions.pending==null);
    }
    try(Fixture f=new Fixture()){
      Location location=new Location();f.permissions.geolocation(f.view,"https://example.com/",location);f.allow();int code=f.code();
      check("Geolocation requests coarse location only",Arrays.equals(f.a.lastPermissions,new String[]{COARSE}));
      f.a.granted.add(COARSE);f.permissions.result(code,new String[]{COARSE},new int[]{0});check("Geolocation grants current origin without persistence",location.calls==1&&location.granted&&!location.remember&&location.origin.equals("https://example.com/"));
      Location later=new Location();f.permissions.geolocation(f.view,"https://example.com/",later);f.permissions.hideGeolocation();check("Hidden geolocation prompt cancels once without persistence",later.calls==1&&!later.granted&&!later.remember);
      Location mismatch=new Location();f.permissions.geolocation(f.view,"https://other.example",mismatch);check("Geolocation cannot cross origin",mismatch.calls==1&&!mismatch.granted&&!mismatch.remember);
    }
    try(Fixture f=new Fixture()){
      Request first=f.camera();f.request(first);Request second=f.camera();f.request(second);
      check("New site request retires older prompt once",first.denials==1&&second.denials==0&&f.permissions.pending.request==second);
      f.permissions.cancel(first);check("Cancellation for old request does not cancel new one",f.permissions.pending.request==second);
      f.permissions.cancel(second);f.permissions.cancel(second);check("Native cancellation delivers one denial",second.denials==1&&f.permissions.pending==null);
      Request reentrant=f.camera(),incoming=f.camera(),third=f.camera();f.request(reentrant);reentrant.denied=()->f.request(third);f.request(incoming);
      check("Denial callback reentrancy preserves newer request",reentrant.denials==1&&incoming.denials==1&&third.denials==0&&f.permissions.pending.request==third);
    }
    try(Fixture f=new Fixture()){
      f.a.throwRequest=true;Request request=f.camera();f.request(request);f.allow();check("Failed Android permission launch denies and releases pending",request.denials==1&&f.permissions.pending==null&&!f.messages.isEmpty());
      Request closing=f.camera();f.request(closing);f.permissions.close();f.permissions.close();check("Close denies once and unregisters lifecycle",closing.denials==1&&f.a.application.callbacks.isEmpty()&&f.permissions.closed);
      Request late=f.camera();f.request(late);check("Closed owner rejects new request",late.denials==1&&late.grants==0);
    }
    check("Default HTTPS port canonicalizes origin only",BrowserPermissions.origin("https://EXAMPLE.COM:443/a").equals("https://example.com"));
    check("Nondefault HTTPS port remains origin scoped",!BrowserPermissions.origin("https://example.com:8443/a").equals(BrowserPermissions.origin("https://example.com/a")));
    System.out.println("{\"status\":\"passed\",\"passed\":"+checks.size()+",\"total\":"+checks.size()+",\"actualAndroidExecution\":false,\"actualWebViewExecution\":false}");
  }
}
