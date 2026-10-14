package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.util.Log;
import android.view.WindowInsets;
import android.view.inputmethod.*;
import android.webkit.*;
import android.widget.*;
import java.lang.reflect.*;
import org.json.*;

/** Separate observer-free editing acceptance; immutable HTML seeds, original SDK APIs only. */
public final class GeckoCaretCompatibilityIntegrationActivity extends Activity {
  static final String ORIGIN="http://127.0.0.1:8771",TAG="PocketCaretCompat";
  final Handler handler=new Handler(Looper.getMainLooper());final JSONArray checks=new JSONArray(),cases=new JSONArray(),apiCalls=new JSONArray(),checkpoints=new JSONArray(),clipboardCalls=new JSONArray();
  ChatSession session;int scenario,sequence;long deadline,stableSince;String stable="";boolean finished;JSONObject before,observed,initialSnapshot,focusedInitial;JSONArray currentActions,scenarioCheckpoints;
  boolean normalMode,sdkObserverPresent,sdkObserverAbsenceChecked;String sourceCommit,runId,runAttempt;JSONObject embeddedBuildIdentity,commonInstalledIdentity;
  static final String[] SDK_OBSERVERS={"org.mozilla.geckoview.PocketGeckoEditableTrace","org.mozilla.geckoview.PocketGeckoInputTrace","org.mozilla.geckoview.PocketInputWriterTrace"};
  static final String[] IDS={"rapid-taps","selected-replace","arrow-delete","undo","ime-multiword","clipboard-paste","chinese-composition","finish-composition","batch-commit","reversed-selection","rejected-input","soft-single-char","codepoint-delete","noop-composition"};
  static final String[] SEEDS={"abcdefghij","abcdefghij","abcdef","undo draft","left-right","clipboard tail","seed tail","seed tail","batch tail","abcdef","rejected draft","soft tail","A😀B","noop tail"};
  static final int[] CARETS={5,8,3,4,5,9,4,4,5,5,4,4,3,4};
  interface Step{void run()throws Exception;}interface Result{void accept(JSONObject value)throws Exception;}interface Edit{boolean run(InputConnection input)throws Exception;}
  static final class FixtureView extends GeckoWebView {
    FixtureView(Context c,ChatSession owner){super(c,owner);}
    @Override protected boolean allowedUrl(String value){return value!=null&&value.startsWith(ORIGIN+"/");}
    @Override boolean readingPage(String value){return value!=null&&value.startsWith(ORIGIN+"/caret");}
  }
  @Override protected void attachBaseContext(Context c){super.attachBaseContext(new ProfileContext(c,Profiles.processSlot()));}
  void event(String kind,JSONObject value){Log.i(TAG,J.obj("kind",kind,"value",value).toString());}
  void attempt(Step step){if(finished)return;try{step.run();}catch(Exception error){fail(error);}}
  void later(Step step,long delay){handler.postDelayed(()->attempt(step),delay);}
  void check(String name,boolean pass){JSONObject item=J.obj("index",checks.length(),"scenario",IDS[scenario],"name",name,"pass",pass);checks.put(item);event("check",item);if(!pass)throw new IllegalStateException(name);}
  void verifyObserverAbsence()throws Exception{
    for(String name:SDK_OBSERVERS){try{Class.forName(name,false,org.mozilla.geckoview.GeckoSession.class.getClassLoader());sdkObserverPresent=true;}catch(ClassNotFoundException absent){}}
    sdkObserverAbsenceChecked=true;
    if(normalMode&&sdkObserverPresent)throw new IllegalStateException("Normal acceptance APK contains an SDK diagnostic observer");
  }
  void report(String status,String error){if(finished)return;finished=true;event("report",J.obj("schema",1,"mode",normalMode?"normal":"diagnostic","status",status,"error",error,"diagnosticOnly",!normalMode,"releaseAcceptance",false,"actualAndroidExecution",true,"actualGeckoExecution",true,"sdkObserverEnabled",sdkObserverPresent,"sdkObserverAbsenceChecked",sdkObserverAbsenceChecked,"sdkObserverClassNamesChecked",new JSONArray(java.util.Arrays.asList(SDK_OBSERVERS)),"sourceCommit",sourceCommit,"runId",runId,"runAttempt",runAttempt,"embeddedBuildIdentity",embeddedBuildIdentity,"commonInstalledIdentity",commonInstalledIdentity,"domTextWrites",0,"scenarioCount",cases.length(),"checkCount",checks.length(),"apiCount",apiCalls.length(),"checkpointCount",checkpoints.length(),"clipboardCount",clipboardCalls.length(),"controlledCaretCompatibilityAcceptance",normalMode&&"passed".equals(status),"physicalPhoneAcceptance",false,"vendorKeyboardUiAcceptance",false,"scope","Controlled original SDK InputConnection APIs and real adb keyboard/touch after immutable initial HTML seeds. Chinese composition means SDK protocol coverage; vendor Baidu/Chinese keyboard UI and physical ARM phone remain unexercised."));}
  void fail(Exception error){if(observed!=null)event("failureSnapshot",compact(observed));report("failed",error.toString());}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);attempt(()->{
    if(!getPackageName().endsWith(".test"))throw new SecurityException("Only the isolated integration package may run this fixture");
    normalMode=getIntent().getBooleanExtra("normalAcceptance",false);sourceCommit=getIntent().getStringExtra("sourceCommit");runId=getIntent().getStringExtra("runId");runAttempt=getIntent().getStringExtra("runAttempt");
    if(sourceCommit==null||!sourceCommit.matches("[0-9a-f]{40}")||runId==null||!runId.matches("[0-9]+")||runAttempt==null||!runAttempt.matches("[0-9]+"))throw new IllegalStateException("Exact source/run/attempt identity required");
    embeddedBuildIdentity=CaretCompatibilityBuildIdentity.read(this);
    commonInstalledIdentity=IntegrationBuildIdentity.read(this);
    if(!sourceCommit.equals(commonInstalledIdentity.optString("sourceCommit")))throw new IllegalStateException("Common installed source identity differs");
    JSONObject commonSdkIdentity=commonInstalledIdentity.optJSONObject("sdkBuildIdentity");if(commonSdkIdentity==null)throw new IllegalStateException("Common installed SDK identity is absent");
    for(String key:new String[]{"runId","runAttempt"})if(!embeddedBuildIdentity.optString(key).equals(commonSdkIdentity.optString(key)))throw new IllegalStateException("Common installed SDK run identity differs: "+key);
    if(!sourceCommit.equals(commonInstalledIdentity.optString("sdkBuildSource")))throw new IllegalStateException("Common installed SDK belongs to another source");
    for(String[] keys:new String[][]{{"sdkAarSha256","sdkAarSha256"},{"sdkClassJarSha256","sdkClassesJarSha256"},{"sdkEditableClassSha256","sdkGeckoEditableClassSha256"},{"sdkManifestSha256","sdkManifestSha256"},{"sdkReceiptSha256","sdkBuildReceiptSha256"}})if(!embeddedBuildIdentity.optString(keys[0]).equals(commonInstalledIdentity.optString(keys[1])))throw new IllegalStateException("Common installed SDK identity differs: "+keys[1]);
    if(!sourceCommit.equals(embeddedBuildIdentity.optString("sourceCommit"))||!runId.equals(embeddedBuildIdentity.optString("runId"))||!runAttempt.equals(embeddedBuildIdentity.optString("runAttempt")))throw new IllegalStateException("Runner identity differs from actual embedded APK identity");
    verifyObserverAbsence();
    getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external").putString("proxy","socks://127.0.0.1:1088").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false).putBoolean("pageMode",true).putBoolean("desktopMode",true).putInt("privacyLevel",1).putBoolean("backgroundWait",false).putBoolean("replyNotice",false).commit();
    ProfileCatalog.get(this).created(Profiles.slot(this));ChatSession.browserFactory=FixtureView::new;session=ChatSession.get(this);session.handler.removeCallbacks(session.tick);session.networkReady=true;session.guard.setBlocked(false);session.uiVisible=true;
    session.web.setWebViewClient(new WebViewClient(){@Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap icon){session.handler.removeCallbacks(session.tick);}@Override public void onPageFinished(WebView v,String url){session.navigating=false;session.navigationFailed=false;session.handler.removeCallbacks(session.tick);}});
    LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setFitsSystemWindows(true);TextView title=new TextView(this);title.setText("原始 Gecko 输入语义 · 14 项验收");root.addView(title);session.web.setHost(this);root.addView(session.web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);deadline=SystemClock.elapsedRealtime()+45000;waitRuntime();
  });}
  void waitRuntime(){attempt(()->{if(session.web.failed)throw new IllegalStateException("Gecko runtime failed");if(!session.web.ready||!session.web.privacyReady){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Runtime timeout");later(this::waitRuntime,100);return;}session.web.configure(true,session.privacy.level());load();});}
  void load(){attempt(()->{currentActions=new JSONArray();scenarioCheckpoints=new JSONArray();initialSnapshot=focusedInitial=null;stable="";stableSince=0;before=null;session.web.loadUrl(ORIGIN+"/caret?case="+scenario);deadline=SystemClock.elapsedRealtime()+25000;later(this::waitDocument,100);});}
  void read(Result result){if(finished)return;session.web.evaluateJavascript("window.__caretSnapshot?window.__caretSnapshot():({ready:false})",raw->attempt(()->{observed=J.parse(raw);result.accept(observed);}));}
  void waitDocument(){read(value->{if(!value.optBoolean("ready")||value.optInt("case",-1)!=scenario){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Document timeout");later(this::waitDocument,100);return;}check("Controlled initial draft is intact",value.optString("draft").equals(SEEDS[scenario]));initialSnapshot=compact(value);before=value;hardware("focus",J.arr(tap(value,CARETS[scenario])));deadline=SystemClock.elapsedRealtime()+20000;waitFocus();});}
  JSONObject tap(JSONObject value,int index)throws Exception{JSONArray points=value.getJSONArray("points");JSONObject point=points.getJSONObject(index);int[] position=new int[2];session.web.getLocationOnScreen(position);return J.obj("op","tap","x",position[0]+Math.round((float)point.getDouble("x")*session.web.getWidth()/value.getInt("width")),"y",position[1]+Math.round((float)point.getDouble("y")*session.web.getHeight()/value.getInt("height")),"expectedCaret",index);}
  void hardware(String name,JSONArray commands){String id=IDS[scenario]+"-"+name+"-"+(sequence++);JSONObject action=J.obj("id",id,"scenario",IDS[scenario],"origin","adb-input-keyboard-and-touch","commands",commands);currentActions.put(action);event("stepNeeded",action);}
  void waitFocus(){read(value->{
    InputMethodManager manager=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);WindowInsets insets=session.web.getRootWindowInsets();boolean ime=Build.VERSION.SDK_INT>=30&&insets!=null&&insets.isVisible(WindowInsets.Type.ime());
    boolean ready=value.optBoolean("focused")&&session.web.hasFocus()&&manager!=null&&manager.isAcceptingText()&&ime&&value.optInt("start",-1)==CARETS[scenario]&&value.optInt("end",-1)==CARETS[scenario];
    String key=value.optInt("start")+"|"+value.optInt("end")+"|"+value.optJSONObject("bounds")+"|"+value.optInt("width")+"|"+value.optInt("height");long now=SystemClock.elapsedRealtime();if(!ready){stable="";stableSince=0;}else if(!key.equals(stable)){stable=key;stableSince=now;}
    if(ready&&now-stableSince>=600){before=value;focusedInitial=compact(value);check("Real tap establishes the exact caret and visible IME",true);execute();return;}if(now>deadline)throw new IllegalStateException("Real focus/caret failed: "+value);later(this::waitFocus,100);
  });}
  void input(String api,JSONArray arguments,Edit edit,Step next)throws Exception{inputBatch(new String[]{api},new JSONArray[]{arguments},new Edit[]{edit},next);}
  void inputBatch(String[] names,JSONArray[] arguments,Edit[] edits,Step next)throws Exception{
    Object sdk=((FixtureView)session.web).current.getTextInput();Field connectionField=sdk.getClass().getDeclaredField("mInputConnection");connectionField.setAccessible(true);Object existing=connectionField.get(sdk);if(!(existing instanceof InputConnection))throw new IllegalStateException("Original SDK input connection unavailable");InputConnection input=(InputConnection)existing;
    Field editableField=sdk.getClass().getDeclaredField("mEditable");editableField.setAccessible(true);Object editable=editableField.get(sdk);Method post=editable.getClass().getDeclaredMethod("postToInputConnection",Runnable.class);post.setAccessible(true);
    final int originalScenario=scenario,connectionIdentity=System.identityHashCode(existing);
    post.invoke(editable,(Runnable)()->{try{
      boolean[] accepted=new boolean[edits.length];for(int i=0;i<edits.length;i++)accepted[i]=edits[i].run(input);long thread=Thread.currentThread().getId();
      handler.post(()->attempt(()->{if(scenario!=originalScenario)throw new IllegalStateException("Original API result belongs to another case");for(int i=0;i<edits.length;i++){
        JSONObject call=J.obj("index",apiCalls.length(),"scenario",IDS[scenario],"api",names[i],"arguments",arguments[i],"origin","original-sdk-inputconnection","accepted",accepted[i],"thread",thread,"connectionIdentity",connectionIdentity);
        apiCalls.put(call);currentActions.put(call);event("api",call);check("Original InputConnection accepts "+names[i]+" #"+call.optInt("index"),accepted[i]);
      }next.run();}));
    }catch(Exception error){handler.post(()->fail(error));}});
  }
  void expect(String draft,int start,int end,int minimumKeys,int minimumInputs,int minimumBefore,Step next){stable="";stableSince=0;long expires=SystemClock.elapsedRealtime()+12000;poll(draft,start,end,minimumKeys,minimumInputs,minimumBefore,expires,next);}
  void poll(String draft,int start,int end,int keys,int inputs,int beforeInputs,long expires,Step next){read(value->{
    boolean correct=value.optString("draft").equals(draft)&&value.optInt("start",-1)==start&&value.optInt("end",-1)==end&&value.optInt("keyCount")>=keys&&value.optInt("inputCount")>=inputs&&value.optInt("beforeCount")>=beforeInputs;
    String key=value.optString("draft")+"|"+value.optInt("start")+"|"+value.optInt("end")+"|"+value.optInt("eventCount");long now=SystemClock.elapsedRealtime();if(!correct){stable="";stableSince=0;}else if(!key.equals(stable)){stable=key;stableSince=now;}
    if(correct&&now-stableSince>=350){JSONObject checkpoint=J.obj("index",checkpoints.length(),"scenario",IDS[scenario],"expected",J.obj("draft",draft,"start",start,"end",end,"minimumKeys",keys,"minimumInputs",inputs,"minimumBefore",beforeInputs),"actual",compact(value));checkpoints.put(checkpoint);scenarioCheckpoints.put(checkpoint);event("checkpoint",checkpoint);check("Exact draft and selection after original input #"+checkpoint.optInt("index"),true);check("Preserved other draft, synthetic cookie and no send",value.optString("otherDraft").equals("untouched independent draft")&&value.optString("cookie").contains("session=synthetic-caret")&&value.optInt("sendCount")==0);check("Input events are trusted and bounded",value.optBoolean("allTrusted")&&!value.optBoolean("overflow"));before=value;next.run();return;}
    if(now>expires)throw new IllegalStateException("Expected draft="+draft+" selection="+start+":"+end+"; actual="+compact(value));later(()->poll(draft,start,end,keys,inputs,beforeInputs,expires,next),80);
  });}
  JSONObject compact(JSONObject value){JSONObject copy=J.parse(value.toString());copy.remove("events");copy.remove("points");return copy;}
  void complete(){attempt(()->{JSONArray events=before.optJSONArray("events");if(events!=null)for(int offset=0;offset<events.length();offset+=4){JSONArray batch=new JSONArray();for(int i=offset;i<Math.min(events.length(),offset+4);i++)batch.put(events.optJSONObject(i));event("trustedEvents",J.obj("id",IDS[scenario],"offset",offset,"events",batch));}JSONObject item=J.obj("id",IDS[scenario],"initialDraft",SEEDS[scenario],"initialSnapshot",initialSnapshot,"focusedInitial",focusedInitial,"actual",compact(before),"actions",currentActions,"checkpoints",scenarioCheckpoints);cases.put(item);event("scenario",item);if(++scenario==IDS.length){report("passed","");return;}load();});}
  void execute()throws Exception{
    switch(scenario){
      case 0:hardware("two-rapid-taps-and-type",J.arr(tap(before,2),tap(before,9),J.obj("op","text","text","Q")));expect("abcdefghiQj",10,10,1,1,1,this::complete);break;
      case 1:input("setSelection",J.arr(2,5),c->c.setSelection(2,5),()->expect(SEEDS[scenario],2,5,0,0,0,()->{hardware("replace-selection",J.arr(J.obj("op","text","text","Z")));expect("abZfghij",3,3,1,1,1,this::complete);}));break;
      case 2:hardware("arrow-backspace-delete",J.arr(J.obj("op","key","code",21),J.obj("op","key","code",67),J.obj("op","key","code",112)));expect("adef",1,1,3,2,2,this::complete);break;
      case 3:hardware("insert-for-undo",J.arr(J.obj("op","text","text","X")));expect("undoX draft",5,5,1,1,1,()->{hardware("ctrl-z",J.arr(J.obj("op","combination","codes",J.arr(113,54))));expect(SEEDS[scenario],4,4,2,2,1,this::complete);});break;
      case 4:input("commitText",J.arr("many words",1),c->c.commitText("many words",1),()->expect("left-many wordsright",15,15,0,1,1,this::complete));break;
      case 5:clipboardPaste(" paste",()->expect("clipboard paste tail",15,15,0,1,1,()->clipboardPaste("Q",()->expect("clipboard pasteQ tail",16,16,0,2,2,()->clipboardPaste("😀",()->expect("clipboard pasteQ😀 tail",18,18,0,3,3,this::complete))))));break;
      case 6:chineseStart();break;
      case 7:input("setComposingText",J.arr("中",1),c->c.setComposingText("中",1),()->expect("seed中 tail",5,5,0,1,1,()->input("finishComposingText",J.arr(),InputConnection::finishComposingText,()->expect("seed中 tail",5,5,0,1,1,()->{check("Finish composition delivers a real composition end",before.optInt("compositionEndCount")>0);complete();}))));break;
      case 8:inputBatch(new String[]{"beginBatchEdit","commitText","commitText","endBatchEdit"},new JSONArray[]{J.arr(),J.arr(" one",1),J.arr(" two",1),J.arr()},new Edit[]{InputConnection::beginBatchEdit,c->c.commitText(" one",1),c->c.commitText(" two",1),InputConnection::endBatchEdit},()->expect("batch one two tail",13,13,0,1,1,this::complete));break;
      case 9:input("setSelection",J.arr(5,2),c->c.setSelection(5,2),()->expect(SEEDS[scenario],2,5,0,0,0,()->{check("Reversed selection preserves backward direction",before.optString("direction").equals("backward"));input("commitText",J.arr("QQ",1),c->c.commitText("QQ",1),()->expect("abQQf",4,4,0,1,1,this::complete));}));break;
      case 10:hardware("rejected-one-key",J.arr(J.obj("op","text","text","Q")));expect(SEEDS[scenario],4,4,1,0,1,()->{check("Rejected beforeinput does not modify the draft",before.optInt("inputCount")==0);check("Rejected key is sent exactly once",before.optInt("qKeyCount")==1&&before.optInt("characterKeyCount")==1&&before.optInt("beforeCount")==1);complete();});break;
      case 11:input("commitText",J.arr("Q",1),c->c.commitText("Q",1),()->expect("softQ tail",5,5,0,1,1,this::complete));break;
      case 12:input("deleteSurroundingTextInCodePoints",J.arr(1,0),c->c.deleteSurroundingTextInCodePoints(1,0),()->expect("AB",1,1,0,1,1,this::complete));break;
      case 13:inputBatch(new String[]{"beginBatchEdit","setComposingText","finishComposingText","endBatchEdit"},new JSONArray[]{J.arr(),J.arr("",1),J.arr(),J.arr()},new Edit[]{InputConnection::beginBatchEdit,c->c.setComposingText("",1),InputConnection::finishComposingText,InputConnection::endBatchEdit},()->expect(SEEDS[scenario],4,4,0,0,0,()->{check("No-op composition preserves text without fabricated input",before.optInt("inputCount")==0);hardware("progress-after-noop",J.arr(J.obj("op","text","text","Q")));expect("noopQ tail",5,5,1,1,1,this::complete);}));break;
      default:throw new IllegalStateException("Unknown scenario");
    }
  }
  void clipboardPaste(String text,Step next)throws Exception{
    ((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("synthetic caret paste",text));
    JSONObject call=J.obj("index",clipboardCalls.length(),"scenario",IDS[scenario],"origin","original-android-clipboardmanager","api","setPrimaryClip","text",text);clipboardCalls.put(call);currentActions.put(call);event("clipboard",call);
    input("performContextMenuAction",J.arr(android.R.id.paste),c->c.performContextMenuAction(android.R.id.paste),next);
  }
  void chineseStart()throws Exception{input("setComposingText",J.arr("ni",1),c->c.setComposingText("ni",1),()->expect("seedni tail",6,6,0,1,1,this::chineseUpdate));}
  void chineseUpdate()throws Exception{input("setComposingText",J.arr("你",1),c->c.setComposingText("你",1),()->expect("seed你 tail",5,5,0,2,2,this::chineseCommit));}
  void chineseCommit()throws Exception{input("commitText",J.arr("你好",1),c->c.commitText("你好",1),()->expect("seed你好 tail",6,6,0,3,3,this::chineseFinish));}
  void chineseFinish()throws Exception{check("Chinese composition produced real composition events",before.optInt("compositionCount")>0);input("finishComposingText",J.arr(),InputConnection::finishComposingText,()->expect("seed你好 tail",6,6,0,3,3,this::complete));}
  @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);if(session!=null)session.handler.removeCallbacks(session.tick);super.onDestroy();}
}
