package local.pocketchat;
import android.app.*;import android.content.*;import android.net.Uri;import android.webkit.*;import java.util.*;import org.json.*;

public final class ChooserHost {
  static final JSONArray checks=new JSONArray();static final Uri OLD=Uri.parse("content://documents/old"),NEW=Uri.parse("content://documents/new");
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static Throwable attempt(Runnable action){try{action.run();return null;}catch(Throwable error){return error;}}
  static final class Probe implements ValueCallback<Uri[]> {final List<Uri[]> calls=new ArrayList<>();Runnable cancelled,received;boolean throwsCallback;public void onReceiveValue(Uri[] value){calls.add(value);if(value==null&&cancelled!=null){Runnable action=cancelled;cancelled=null;action.run();}if(value!=null&&received!=null){Runnable action=received;received=null;action.run();}if(throwsCallback)throw new IllegalStateException("Controlled callback failure");}boolean onlyNull(){return calls.size()==1&&calls.get(0)==null;}boolean only(Uri uri){return calls.size()==1&&calls.get(0)!=null&&calls.get(0).length==1&&uri.equals(calls.get(0)[0]);}}
  static final class Params extends WebChromeClient.FileChooserParams {int mode=MODE_OPEN;String[] types={".pdf"};Runnable onTypes;public int getMode(){return mode;}public String[] getAcceptTypes(){Runnable action=onTypes;onTypes=null;if(action!=null)action.run();return types;}}
  static void open(MainActivity host,Probe callback){host.attachments.chrome().onShowFileChooser(null,callback,new Params());}
  static int latest(MainActivity host){return host.requests.isEmpty()?-1:host.requests.get(host.requests.size()-1);}
  static void deliver(MainActivity host,int request,Uri uri){host.onActivityResult(request,Activity.RESULT_OK,new Intent().setData(uri));}
  static void normal(){
    MainActivity a=new MainActivity();Probe p=new Probe();Params params=new Params();params.mode=Params.MODE_OPEN_MULTIPLE;params.types=new String[]{"image/png, image/jpeg"};a.attachments.chrome().onShowFileChooser(null,p,params);int request=latest(a);Intent launched=a.intents.get(0);
    check("Normal native chooser retains MIME, multiple selection and document permissions","image/*".equals(launched.type)&&Boolean.TRUE.equals(launched.extras.get(Intent.EXTRA_ALLOW_MULTIPLE))&&launched.flags==(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION));
    a.onActivityResult(request,Activity.RESULT_OK,new Intent().setClipData(new ClipData(OLD,OLD,NEW)));a.onActivityResult(request,Activity.RESULT_OK,new Intent().setData(OLD));
    check("Normal native result deduplicates in order and completes once",p.calls.size()==1&&Arrays.equals(p.calls.get(0),new Uri[]{OLD,NEW})&&!a.attachments.blocked());
    check("Normal selection retains its existing persistable-grant attempts",a.resolver.persisted.equals(Arrays.asList(OLD,NEW)));
    MainActivity cancel=new MainActivity();Probe rejected=new Probe();open(cancel,rejected);cancel.onActivityResult(latest(cancel),Activity.RESULT_CANCELED,null);check("User cancellation settles the native callback once",rejected.onlyNull()&&!cancel.attachments.blocked());
    MainActivity grants=new MainActivity();Probe accepted=new Probe();grants.resolver.deny=true;open(grants,accepted);deliver(grants,latest(grants),NEW);check("Nonpersistent document grant still delivers the selected URI",accepted.only(NEW));
    MainActivity own=new MainActivity();Probe app=new Probe();Uri ownUri=Uri.parse("content://local.pocketchat.saved-downloads/own");open(own,app);deliver(own,latest(own),ownUri);check("Native chooser keeps existing support for the app's exported download provider",app.only(ownUri));
  }
  static void admission(){
    for(String reason:new String[]{"not-ready","foreign-page","destroyed","retiring-host"}){
      MainActivity a=new MainActivity();Probe p=new Probe();if(reason.equals("not-ready"))a.remote.ready=false;if(reason.equals("foreign-page"))a.remote.url="https://example.test/file";if(reason.equals("destroyed"))a.attachments.destroy();if(reason.equals("retiring-host"))a.destroyed=true;open(a,p);
      check("Admission rejects "+reason+" without launching a picker",p.onlyNull()&&a.requests.isEmpty()&&!a.attachments.blocked());
    }
    MainActivity a=new MainActivity();Probe p=new Probe();open(a,p);a.session.navigationEpoch++;deliver(a,latest(a),NEW);check("A same-URL document replacement rejects the old result",p.onlyNull()&&a.resolver.persisted.isEmpty());
    MainActivity wrong=new MainActivity();Probe p2=new Probe();open(wrong,p2);deliver(wrong,latest(wrong),Uri.parse("file:///private/file"));check("Native chooser continues rejecting non-document result schemes",p2.onlyNull()&&wrong.resolver.persisted.isEmpty());
  }
  static void replaceDuringCancellation(){
    MainActivity a=new MainActivity();Probe first=new Probe(),outer=new Probe(),inner=new Probe();open(a,first);first.cancelled=()->open(a,inner);open(a,outer);
    check("Cancellation reentry preserves the newest chooser and rejects the outer request",first.onlyNull()&&outer.onlyNull()&&inner.calls.isEmpty()&&a.requests.size()==2);
    deliver(a,latest(a),NEW);check("Cancellation reentry delivers only to the nested current chooser",inner.only(NEW)&&outer.onlyNull()&&!a.attachments.blocked());
  }
  static void cancellationChangesOwner(){
    for(String change:new String[]{"epoch","attachment-destroy","activity-retire","activity-replaced"}){
      MainActivity a=new MainActivity();Probe first=new Probe(),outer=new Probe();open(a,first);first.cancelled=()->{if(change.equals("epoch"))a.session.navigationEpoch++;else if(change.equals("attachment-destroy"))a.attachments.destroy();else if(change.equals("activity-retire"))a.destroyed=true;else new MainActivity(a.session,a.remote);};open(a,outer);
      check("Cancellation reentry "+change+" cannot reopen the obsolete outer picker",first.onlyNull()&&outer.onlyNull()&&a.requests.size()==1&&!a.attachments.blocked());
    }
  }
  static void synchronousBoundaries(){
    for(String boundary:new String[]{"loading","parameters","launch-failure"}){
      MainActivity a=new MainActivity();Probe outer=new Probe(),inner=new Probe();Params params=new Params();Runnable replace=()->open(a,inner);
      if(boundary.equals("loading"))a.loading.onDismiss=replace;else if(boundary.equals("parameters"))params.onTypes=replace;else{a.onLaunch=replace;a.launchFailure=new ActivityNotFoundException();}
      a.attachments.chrome().onShowFileChooser(null,outer,params);int expected=boundary.equals("launch-failure")?2:1;
      check("Synchronous "+boundary+" reentry cannot launch or cancel a newer request",outer.onlyNull()&&inner.calls.isEmpty()&&a.requests.size()==expected);
      deliver(a,latest(a),NEW);check("Synchronous "+boundary+" preserves the inner callback for its own result",inner.only(NEW)&&outer.onlyNull());
    }
  }
  static void dismissReentry(){
    MainActivity a=new MainActivity();Probe first=new Probe(),inner=new Probe();Attachments.Chrome chrome=(Attachments.Chrome)a.attachments.chrome();open(a,first);int old=latest(a);boolean[] released={false};first.cancelled=()->{released[0]=a.finished.contains(old);open(a,inner);};chrome.dismissFilePrompt(first);int current=latest(a);
    check("Native prompt dismissal closes only the retired picker request",first.onlyNull()&&a.finished.contains(old)&&!a.finished.contains(current)&&inner.calls.isEmpty());
    check("Native prompt releases its Android picker before invoking cancellation",released[0]);
    chrome.dismissFilePrompt(first);deliver(a,current,NEW);check("Repeated stale native dismissal cannot cancel the current picker",first.onlyNull()&&inner.only(NEW));
  }
  static void staleResults(){
    MainActivity a=new MainActivity();Probe first=new Probe(),second=new Probe();open(a,first);int old=latest(a);open(a,second);int current=latest(a);deliver(a,old,OLD);
    check("Successor chooser never reuses the old Android request identifier",old!=current);
    check("Late previous picker result cannot reach a newer same-page callback",first.onlyNull()&&second.calls.isEmpty()&&a.attachments.blocked()&&a.resolver.persisted.isEmpty());
    deliver(a,current,NEW);check("Current request still receives its selected file after a stale result",second.only(NEW)&&!a.attachments.blocked());
    MainActivity next=new MainActivity(a.session,a.remote);Probe replacement=new Probe();a.attachments.destroy();a.destroyed=true;open(next,replacement);int nextRequest=latest(next);deliver(next,current,OLD);
    check("A new Activity for the same Gecko session cannot reuse a prior host's request",nextRequest!=current&&replacement.calls.isEmpty()&&next.attachments.blocked());
    deliver(next,nextRequest,NEW);check("New Activity chooser delivers only its own Android result",replacement.only(NEW));
  }
  static void callbacksAndResultReentry(){
    MainActivity a=new MainActivity();Probe first=new Probe(),second=new Probe();open(a,first);first.throwsCallback=true;Throwable escaped=attempt(()->open(a,second));check("Throwing old cancellation callback cannot strand the admitted replacement",escaped==null&&first.onlyNull()&&second.calls.isEmpty()&&a.requests.size()==2);deliver(a,latest(a),NEW);check("Replacement remains usable after a throwing old callback",second.only(NEW));
    MainActivity close=new MainActivity();Probe dying=new Probe();open(close,dying);dying.throwsCallback=true;Throwable destroy=attempt(close.attachments::destroy);check("Throwing native callback cannot abort attachment teardown",destroy==null&&dying.onlyNull()&&!close.attachments.blocked());
    MainActivity success=new MainActivity();Probe delivered=new Probe();open(success,delivered);delivered.throwsCallback=true;Throwable result=attempt(()->deliver(success,latest(success),NEW));check("Throwing result callback cannot retain local picker ownership",result==null&&delivered.only(NEW)&&!success.attachments.blocked());
    MainActivity provider=new MainActivity();Probe old=new Probe(),fresh=new Probe();open(provider,old);int request=latest(provider);provider.resolver.onPersist=()->open(provider,fresh);deliver(provider,request,OLD);
    check("Provider callback reentry cannot clear the new chooser or deliver the retired file",old.onlyNull()&&fresh.calls.isEmpty()&&provider.attachments.blocked());deliver(provider,latest(provider),NEW);check("Provider callback reentry retains the new chooser result",fresh.only(NEW));
    MainActivity navigating=new MainActivity();Probe changed=new Probe();open(navigating,changed);navigating.resolver.onPersist=()->navigating.session.navigationEpoch++;deliver(navigating,latest(navigating),OLD);check("Document change during final URI grant rejects the obsolete file",changed.onlyNull()&&!navigating.attachments.blocked());
    MainActivity nativeCallback=new MainActivity();Probe completed=new Probe(),next=new Probe();open(nativeCallback,completed);completed.received=()->open(nativeCallback,next);deliver(nativeCallback,latest(nativeCallback),OLD);check("Successful native callback is detached before it can open another chooser",completed.only(OLD)&&next.calls.isEmpty()&&nativeCallback.attachments.blocked());deliver(nativeCallback,latest(nativeCallback),NEW);check("Native success reentry keeps the next chooser's own result",next.only(NEW));
    MainActivity malformed=new MainActivity();Probe invalid=new Probe();open(malformed,invalid);Intent broken=new Intent();broken.malformed=new IllegalArgumentException("Controlled malformed result");Throwable malformedError=attempt(()->malformed.onActivityResult(latest(malformed),Activity.RESULT_OK,broken));check("Malformed native result is settled without leaking callback or throwing",malformedError==null&&invalid.onlyNull()&&!malformed.attachments.blocked());
  }
  static void hostHandoff(){
    MainActivity old=new MainActivity();Probe previous=new Probe(),fresh=new Probe();open(old,previous);int oldRequest=latest(old);MainActivity next=new MainActivity(old.session,old.remote);open(next,fresh);deliver(old,oldRequest,OLD);
    check("A replaced but not yet destroyed Activity cannot consume its old picker result",previous.onlyNull()&&old.resolver.persisted.isEmpty()&&!old.attachments.blocked()&&fresh.calls.isEmpty());
    Probe retired=new Probe();open(old,retired);check("A replaced Activity cannot reopen its chooser before onDestroy",retired.onlyNull()&&old.requests.size()==1);deliver(next,latest(next),NEW);check("Host handoff preserves the new Activity's native chooser",fresh.only(NEW));
  }
  static void retirementAndLimit(){
    MainActivity finish=new MainActivity();Probe old=new Probe(),outer=new Probe(),fresh=new Probe();open(finish,old);int original=latest(finish);finish.onFinish=()->open(finish,fresh);open(finish,outer);check("Synchronous finishActivity reentry preserves the last admitted chooser",old.onlyNull()&&outer.onlyNull()&&fresh.calls.isEmpty()&&finish.requests.size()==2&&finish.finished.contains(original));deliver(finish,latest(finish),NEW);check("Retirement reentry leaves the new picker usable",fresh.only(NEW));
    MainActivity throwsFinish=new MainActivity();Probe callback=new Probe();open(throwsFinish,callback);throwsFinish.finishFailure=new IllegalStateException("Controlled picker close failure");Throwable failure=attempt(throwsFinish.attachments::cancelChooser);check("Failed platform picker close still settles its callback once",failure==null&&callback.onlyNull()&&!throwsFinish.attachments.blocked());
    MainActivity routing=new MainActivity();Probe pending=new Probe();open(routing,pending);int own=latest(routing);deliver(routing,83,OLD);deliver(routing,85,OLD);deliver(routing,0x2800,OLD);deliver(routing,0x3000,OLD);deliver(routing,0x5000,OLD);check("Unrelated download, export, role and browser request ranges cannot consume attachments",pending.calls.isEmpty()&&routing.attachments.blocked()&&routing.resolver.persisted.isEmpty());deliver(routing,own,NEW);
    try{java.lang.reflect.Field counter=Attachments.class.getDeclaredField("nextRequest");counter.setAccessible(true);counter.setInt(null,0x27ff);}catch(ReflectiveOperationException error){throw new AssertionError(error);}
    MainActivity last=new MainActivity();Probe accepted=new Probe(),rejected=new Probe(),again=new Probe();open(last,accepted);int code=latest(last);open(last,rejected);open(last,again);check("Exhausted request range refuses reuse and preserves its last active chooser",code==0x27ff&&last.requests.size()==1&&accepted.calls.isEmpty()&&rejected.onlyNull()&&again.onlyNull());deliver(last,code,NEW);check("Last valid request still completes after allocation is exhausted",accepted.only(NEW));
    try{java.lang.reflect.Field counter=Attachments.class.getDeclaredField("nextRequest");counter.setAccessible(true);check("Rejected allocations leave the exhausted counter saturated",counter.getInt(null)==0x2800);}catch(ReflectiveOperationException error){throw new AssertionError(error);}
  }
  public static void main(String[] args){normal();admission();replaceDuringCancellation();cancellationChangesOwner();synchronousBoundaries();dismissReentry();staleResults();callbacksAndResultReentry();hostHandoff();retirementAndLimit();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);}
}
class MainActivity extends Activity {
  static final String ORIGIN="https://chatgpt.com/";boolean destroyed;final Session session;final Page remote;final Loading loading=new Loading();final List<String> messages=new ArrayList<>();final SharedPreferences prefs=new SharedPreferences();String conversation="";Attachments attachments;FileDownloads downloads;
  MainActivity(){this(new Session(),new Page());}MainActivity(Session session,Page page){this.session=session;remote=page;remote.displayContext.setBaseContext(this);attachments=new Attachments(this);}void status(String message){messages.add(message);}void showPage(boolean value){throw new AssertionError("Legacy preview outside picker host");}
  /* ACTUAL_ACTIVITY */
}
class Session {long navigationEpoch=3;final JSONArray attachments=new JSONArray();}
class Page {final MutableContextWrapper displayContext=new MutableContextWrapper(new Context());String url="https://chatgpt.com/c/current";boolean ready=true;String getUrl(){return url;}boolean canChooseFiles(){return ready;}}
class Loading {Runnable onDismiss;void dismissTask(){Runnable action=onDismiss;onDismiss=null;if(action!=null)action.run();}}
class FileDownloads {static final int SAVE=83;final SavedFileActions savedActions=new SavedFileActions();void result(int result,Intent data){throw new AssertionError("Unrelated download callback received native picker result");}}
class SavedFileActions {static final int EXPORT=85;void result(int result,Intent data){throw new AssertionError("Unrelated export callback received native picker result");}}
class Profiles {static Class<?> preview(Context context){throw new AssertionError("Legacy preview outside picker host");}}
class BrowserRuntimePolicy {static String websiteActionMessage(){throw new AssertionError("Legacy native attachment controls outside picker host");}}
