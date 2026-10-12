package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.util.Log;
import android.view.WindowInsets;
import android.view.inputmethod.*;
import android.webkit.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.*;
import java.security.MessageDigest;
import org.json.*;

/** Additional candidate-only editing semantics; no SDK observer and no DOM text writes. */
public final class GeckoCaretCompatibilityIntegrationActivity extends Activity {
  static final String ORIGIN="http://127.0.0.1:8771",TAG="PocketCaretCompat";
  final Handler handler=new Handler(Looper.getMainLooper());final JSONArray checks=new JSONArray(),cases=new JSONArray(),apiCalls=new JSONArray(),checkpoints=new JSONArray();
  ChatSession session;int scenario,sequence;long deadline,stableSince;String stable="";boolean finished;JSONObject before,observed;JSONArray currentActions;
  JSONObject installedApk;boolean sdkObserverPresent,observerAbsenceVerified,identityReady;
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
  void report(String status,String error){if(finished)return;finished=true;event("report",J.obj("status",status,"error",error,"diagnosticOnly",true,"releaseAcceptance",false,"actualAndroidExecution",true,"actualGeckoExecution",true,"sdkObserverEnabled",sdkObserverPresent,"sdkObserverAbsenceVerified",observerAbsenceVerified,"sdkObserverClass","org.mozilla.geckoview.PocketGeckoEditableTrace","installedApk",installedApk,"domTextWrites",0,"scenarioCount",cases.length(),"checkCount",checks.length(),"apiCount",apiCalls.length(),"checkpointCount",checkpoints.length(),"scope","Controlled fixture initial HTML seeds; subsequent edits use original SDK InputConnection and real adb keyboard/touch. No real account, vendor touch-keyboard UI, hardware device or production acceptance claim."));}
  void fail(Exception error){if(observed!=null)event("failureSnapshot",compact(observed));report("failed",error.toString());}
  @Override public void onCreate(Bundle saved){super.onCreate(saved);attempt(()->{
    if(!getPackageName().endsWith(".test"))throw new SecurityException("Only the isolated integration package may run this fixture");
    verifyInstalledIdentity();
    getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external").putString("proxy","socks://127.0.0.1:1088").putBoolean("requireExternalVpn",false).putBoolean("networkConfigured",false).putBoolean("pageMode",true).putBoolean("desktopMode",true).putInt("privacyLevel",1).putBoolean("backgroundWait",false).putBoolean("replyNotice",false).commit();
    ProfileCatalog.get(this).created(Profiles.slot(this));ChatSession.browserFactory=FixtureView::new;session=ChatSession.get(this);session.handler.removeCallbacks(session.tick);session.networkReady=true;session.guard.setBlocked(false);session.uiVisible=true;
    session.web.setWebViewClient(new WebViewClient(){@Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap icon){session.handler.removeCallbacks(session.tick);}@Override public void onPageFinished(WebView v,String url){session.navigating=false;session.navigationFailed=false;session.handler.removeCallbacks(session.tick);}});
    LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setFitsSystemWindows(true);TextView title=new TextView(this);title.setText("原始 Gecko 输入语义 · 隔离候选验收");root.addView(title);session.web.setHost(this);root.addView(session.web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);deadline=SystemClock.elapsedRealtime()+45000;waitRuntime();
  });}
  void verifyInstalledIdentity()throws Exception{
    try{Class.forName("org.mozilla.geckoview.PocketGeckoEditableTrace",false,getClassLoader());sdkObserverPresent=true;}catch(ClassNotFoundException absent){sdkObserverPresent=false;observerAbsenceVerified=true;}
    if(sdkObserverPresent)throw new IllegalStateException("Observed SDK cannot run the observer-free compatibility gate");
    final String source=getApplicationInfo().sourceDir,packageName=getPackageName();
    final android.content.pm.PackageInfo info=getPackageManager().getPackageInfo(packageName,0);
    final boolean debuggable=(getApplicationInfo().flags&android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0;
    new Thread(()->{try{
      MessageDigest digest=MessageDigest.getInstance("SHA-256");long bytes=0;byte[] buffer=new byte[65536];
      try(InputStream stream=new FileInputStream(source)){int count;while((count=stream.read(buffer))!=-1){digest.update(buffer,0,count);bytes+=count;}}
      if(bytes<=0)throw new IOException("Installed package is empty");
      StringBuilder sha=new StringBuilder();for(byte value:digest.digest())sha.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
      final JSONObject identity=J.obj("packageName",packageName,"sha256",sha.toString(),"bytes",bytes,"versionName",info.versionName,"versionCode",info.getLongVersionCode(),"debuggable",debuggable,"source","applicationInfo.sourceDir","actualInstalledPackageRead",true);
      handler.post(()->attempt(()->{installedApk=identity;identityReady=true;event("installedIdentity",identity);}));
    }catch(Exception error){handler.post(()->fail(error));}},"caret-installed-apk-sha256").start();
  }
  void waitRuntime(){attempt(()->{if(session.web.failed)throw new IllegalStateException("Gecko runtime failed");if(!identityReady||!session.web.ready||!session.web.privacyReady){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Runtime or installed identity timeout");later(this::waitRuntime,100);return;}session.web.configure(true,session.privacy.level());load();});}
  void load(){attempt(()->{currentActions=new JSONArray();stable="";stableSince=0;before=null;session.web.loadUrl(ORIGIN+"/caret?case="+scenario);deadline=SystemClock.elapsedRealtime()+25000;later(this::waitDocument,100);});}
  String snapshotScript(){return "(()=>{const address=new URL(location.href),composer=document.getElementById('prompt-textarea'),other=document.getElementById('other-draft'),send=document.getElementById('send');"+
    "if(address.origin!=="+JSONObject.quote(ORIGIN)+"||address.pathname!=='/caret'||Number(address.searchParams.get('case'))!=="+scenario+"||!composer||!other||!send)return {ready:false,documentUrl:location.href,documentState:document.readyState};"+
    "let trace=window.__caretCompatibilityTrace;if(!trace||trace.composer!==composer||trace.caseNumber!=="+scenario+"){trace=window.__caretCompatibilityTrace={composer,caseNumber:"+scenario+",events:[],overflow:false,sendCount:0};const caseNumber="+scenario+";"+
    "for(const type of ['keydown','keyup','beforeinput','input','compositionstart','compositionupdate','compositionend'])composer.addEventListener(type,e=>{if(trace.events.length>=512){trace.overflow=true;return}trace.events.push({type,key:e.key||'',data:e.data||'',inputType:e.inputType||'',trusted:e.isTrusted,ctrl:!!e.ctrlKey,shift:!!e.shiftKey,composing:!!e.isComposing,start:composer.selectionStart,end:composer.selectionEnd});if(type==='beforeinput'&&caseNumber===10)e.preventDefault()});send.addEventListener('click',()=>trace.sendCount++);}"+
    "const r=composer.getBoundingClientRect(),style=getComputedStyle(composer),canvas=document.createElement('canvas'),context=canvas.getContext('2d');context.font=style.font;const points=[];"+
    "for(let i=0;i<=composer.value.length;i++)points.push({x:r.left+parseFloat(style.borderLeftWidth)+parseFloat(style.paddingLeft)+context.measureText(composer.value.slice(0,i)).width-composer.scrollLeft,y:r.top+parseFloat(style.borderTopWidth)+parseFloat(style.paddingTop)+parseFloat(style.fontSize)*.6});"+
    "const events=trace.events;return {ready:true,case:"+scenario+",documentUrl:location.href,draft:composer.value,otherDraft:other.value,focused:document.activeElement===composer,start:composer.selectionStart,end:composer.selectionEnd,direction:composer.selectionDirection,cookie:document.cookie,sendCount:trace.sendCount,width:innerWidth,height:innerHeight,bounds:{x:r.x,y:r.y,width:r.width,height:r.height},points,events,overflow:trace.overflow,eventCount:events.length,keyCount:events.filter(e=>e.type==='keydown').length,inputCount:events.filter(e=>e.type==='input').length,beforeCount:events.filter(e=>e.type==='beforeinput').length,compositionCount:events.filter(e=>e.type==='compositionstart').length,compositionEndCount:events.filter(e=>e.type==='compositionend').length,allTrusted:events.every(e=>e.trusted)}})()";}
  void read(Result result){if(finished)return;session.web.evaluateJavascript(snapshotScript(),raw->attempt(()->{observed=J.parse(raw);result.accept(observed);}));}
  void waitDocument(){read(value->{if(!value.optBoolean("ready")||value.optInt("case",-1)!=scenario){if(SystemClock.elapsedRealtime()>deadline)throw new IllegalStateException("Document timeout");later(this::waitDocument,100);return;}check("Controlled initial draft is intact",value.optString("draft").equals(SEEDS[scenario]));before=value;hardware("focus",J.arr(tap(value,CARETS[scenario])));deadline=SystemClock.elapsedRealtime()+20000;waitFocus();});}
  JSONObject tap(JSONObject value,int index)throws Exception{JSONArray points=value.getJSONArray("points");JSONObject point=points.getJSONObject(index);int[] position=new int[2];session.web.getLocationOnScreen(position);return J.obj("op","tap","x",position[0]+Math.round((float)point.getDouble("x")*session.web.getWidth()/value.getInt("width")),"y",position[1]+Math.round((float)point.getDouble("y")*session.web.getHeight()/value.getInt("height")),"expectedCaret",index);}
  void hardware(String name,JSONArray commands){String id=IDS[scenario]+"-"+name+"-"+(sequence++);JSONObject action=J.obj("id",id,"scenario",IDS[scenario],"origin","adb-input-keyboard-and-touch","commands",commands);currentActions.put(action);event("stepNeeded",action);}
  void waitFocus(){read(value->{
    InputMethodManager manager=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);WindowInsets insets=session.web.getRootWindowInsets();boolean ime=Build.VERSION.SDK_INT>=30&&insets!=null&&insets.isVisible(WindowInsets.Type.ime());
    boolean ready=value.optBoolean("focused")&&session.web.hasFocus()&&manager!=null&&manager.isAcceptingText()&&ime&&value.optInt("start",-1)==CARETS[scenario]&&value.optInt("end",-1)==CARETS[scenario];
    String key=value.optInt("start")+"|"+value.optInt("end")+"|"+value.optJSONObject("bounds")+"|"+value.optInt("width")+"|"+value.optInt("height");long now=SystemClock.elapsedRealtime();if(!ready){stable="";stableSince=0;}else if(!key.equals(stable)){stable=key;stableSince=now;}
    if(ready&&now-stableSince>=600){before=value;check("Real tap establishes the exact caret and visible IME",true);checkpoint("focus",SEEDS[scenario],CARETS[scenario],CARETS[scenario],0,0,0,value,now-stableSince);execute();return;}if(now>deadline)throw new IllegalStateException("Real focus/caret failed: "+value);later(this::waitFocus,100);
  });}
  void input(String label,Edit edit,Step next)throws Exception{
    Object sdk=((FixtureView)session.web).current.getTextInput();Field connectionField=sdk.getClass().getDeclaredField("mInputConnection");connectionField.setAccessible(true);Object existing=connectionField.get(sdk);if(!(existing instanceof InputConnection))throw new IllegalStateException("Original SDK input connection unavailable");InputConnection input=(InputConnection)existing;
    Field editableField=sdk.getClass().getDeclaredField("mEditable");editableField.setAccessible(true);Object editable=editableField.get(sdk);Method post=editable.getClass().getDeclaredMethod("postToInputConnection",Runnable.class);post.setAccessible(true);
    post.invoke(editable,(Runnable)()->{try{boolean accepted=edit.run(input);long thread=Thread.currentThread().getId();handler.post(()->attempt(()->{JSONObject call=J.obj("index",apiCalls.length(),"scenario",IDS[scenario],"api",label,"origin","original-sdk-inputconnection","accepted",accepted,"thread",thread);apiCalls.put(call);currentActions.put(call);event("api",call);check("Original InputConnection accepts "+label,accepted);next.run();}));}catch(Exception error){handler.post(()->fail(error));}});
  }
  void expect(String draft,int start,int end,int minimumKeys,int minimumInputs,int minimumBefore,Step next){stable="";stableSince=0;long expires=SystemClock.elapsedRealtime()+12000;poll(draft,start,end,minimumKeys,minimumInputs,minimumBefore,expires,next);}
  void poll(String draft,int start,int end,int keys,int inputs,int beforeInputs,long expires,Step next){read(value->{
    boolean correct=value.optString("draft").equals(draft)&&value.optInt("start",-1)==start&&value.optInt("end",-1)==end&&value.optInt("keyCount")>=keys&&value.optInt("inputCount")>=inputs&&value.optInt("beforeCount")>=beforeInputs;
    String key=value.optString("draft")+"|"+value.optInt("start")+"|"+value.optInt("end")+"|"+value.optInt("eventCount");long now=SystemClock.elapsedRealtime();if(!correct){stable="";stableSince=0;}else if(!key.equals(stable)){stable=key;stableSince=now;}
    if(correct&&now-stableSince>=350){check("Exact draft and selection after original input",true);check("Preserved other draft, synthetic cookie and no send",value.optString("otherDraft").equals("untouched independent draft")&&value.optString("cookie").contains("session=synthetic-caret")&&value.optInt("sendCount")==0);check("Input events are trusted and bounded",value.optBoolean("allTrusted")&&!value.optBoolean("overflow"));before=value;checkpoint("expect",draft,start,end,keys,inputs,beforeInputs,value,now-stableSince);next.run();return;}
    if(now>expires)throw new IllegalStateException("Expected draft="+draft+" selection="+start+":"+end+"; actual="+compact(value));later(()->poll(draft,start,end,keys,inputs,beforeInputs,expires,next),80);
  });}
  JSONObject compact(JSONObject value){JSONObject copy=J.parse(value.toString());copy.remove("events");copy.remove("points");return copy;}
  void checkpoint(String phase,String draft,int start,int end,int keys,int inputs,int beforeInputs,JSONObject value,long stableMillis){JSONObject item=J.obj("index",checkpoints.length(),"scenario",IDS[scenario],"phase",phase,"expected",J.obj("draft",draft,"start",start,"end",end,"minimumKeys",keys,"minimumInputs",inputs,"minimumBefore",beforeInputs),"actual",compact(value),"stableMillis",stableMillis);checkpoints.put(item);event("checkpoint",item);}
  void complete(){attempt(()->{JSONArray events=before.optJSONArray("events");if(events!=null)for(int offset=0;offset<events.length();offset+=4){JSONArray batch=new JSONArray();for(int i=offset;i<Math.min(events.length(),offset+4);i++)batch.put(events.optJSONObject(i));event("trustedEvents",J.obj("id",IDS[scenario],"offset",offset,"events",batch));}JSONObject item=J.obj("id",IDS[scenario],"initialDraft",SEEDS[scenario],"actual",compact(before),"actions",currentActions);cases.put(item);event("scenario",item);if(++scenario==IDS.length){report("passed","");return;}load();});}
  void execute()throws Exception{
    switch(scenario){
      case 0:hardware("two-rapid-taps-and-type",J.arr(tap(before,2),tap(before,9),J.obj("op","text","text","Q")));expect("abcdefghiQj",10,10,1,1,1,this::complete);break;
      case 1:input("setSelection(2,5)",c->c.setSelection(2,5),()->expect(SEEDS[scenario],2,5,0,0,0,()->{hardware("replace-selection",J.arr(J.obj("op","text","text","Z")));expect("abZfghij",3,3,1,1,1,this::complete);}));break;
      case 2:hardware("arrow-backspace-delete",J.arr(J.obj("op","key","code",21),J.obj("op","key","code",67),J.obj("op","key","code",112)));expect("adef",1,1,3,2,2,this::complete);break;
      case 3:hardware("insert-for-undo",J.arr(J.obj("op","text","text","X")));expect("undoX draft",5,5,1,1,1,()->{hardware("ctrl-z",J.arr(J.obj("op","combination","codes",J.arr(113,54))));expect(SEEDS[scenario],4,4,2,2,1,this::complete);});break;
      case 4:input("commitText(many words,1)",c->c.commitText("many words",1),()->expect("left-many wordsright",15,15,0,1,1,this::complete));break;
      case 5:((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("synthetic caret paste"," paste"));input("performContextMenuAction(paste)",c->c.performContextMenuAction(android.R.id.paste),()->expect("clipboard paste tail",15,15,0,1,1,this::complete));break;
      case 6:chineseStart();break;
      case 7:input("setComposingText(中,1)",c->c.setComposingText("中",1),()->expect("seed中 tail",5,5,0,1,1,()->input("finishComposingText",InputConnection::finishComposingText,()->expect("seed中 tail",5,5,0,1,1,()->{check("Finish composition delivers a real composition end",before.optInt("compositionEndCount")>0);complete();}))));break;
      case 8:input("beginBatch/commitText(one)/commitText(two)/endBatch",c->{boolean begin=c.beginBatchEdit(),one=c.commitText(" one",1),two=c.commitText(" two",1),end=c.endBatchEdit();return begin&&one&&two&&end;},()->expect("batch one two tail",13,13,0,1,1,this::complete));break;
      case 9:input("setSelection(5,2)",c->c.setSelection(5,2),()->expect(SEEDS[scenario],2,5,0,0,0,()->{check("Reversed selection preserves backward direction",before.optString("direction").equals("backward"));input("commitText(QQ,1)",c->c.commitText("QQ",1),()->expect("abQQf",4,4,0,1,1,this::complete));}));break;
      case 10:hardware("rejected-one-key",J.arr(J.obj("op","text","text","Q")));expect(SEEDS[scenario],4,4,1,0,1,()->{check("Rejected beforeinput does not modify the draft",before.optInt("inputCount")==0);check("Rejected key is sent exactly once",before.optInt("keyCount")==1&&before.optInt("beforeCount")==1);complete();});break;
      case 11:input("commitText(Q,1)-soft-path",c->c.commitText("Q",1),()->expect("softQ tail",5,5,0,1,1,this::complete));break;
      case 12:input("deleteSurroundingTextInCodePoints(1,0)",c->c.deleteSurroundingTextInCodePoints(1,0),()->expect("AB",1,1,0,1,1,this::complete));break;
      case 13:input("batch/emptyComposing/finish/endBatch",c->{boolean a=c.beginBatchEdit(),b=c.setComposingText("",1),f=c.finishComposingText(),e=c.endBatchEdit();return a&&b&&f&&e;},()->expect(SEEDS[scenario],4,4,0,0,0,()->{check("No-op composition preserves text without fabricated input",before.optInt("inputCount")==0);hardware("progress-after-noop",J.arr(J.obj("op","text","text","Q")));expect("noopQ tail",5,5,1,1,1,this::complete);}));break;
      default:throw new IllegalStateException("Unknown scenario");
    }
  }
  void chineseStart()throws Exception{input("setComposingText(ni,1)",c->c.setComposingText("ni",1),()->expect("seedni tail",6,6,0,1,1,this::chineseUpdate));}
  void chineseUpdate()throws Exception{input("setComposingText(你,1)",c->c.setComposingText("你",1),()->expect("seed你 tail",5,5,0,2,2,this::chineseCommit));}
  void chineseCommit()throws Exception{input("commitText(你好,1)",c->c.commitText("你好",1),()->expect("seed你好 tail",6,6,0,3,3,this::chineseFinish));}
  void chineseFinish()throws Exception{check("Chinese composition produced real composition events",before.optInt("compositionCount")>0);input("finishComposingText",InputConnection::finishComposingText,()->expect("seed你好 tail",6,6,0,3,3,this::complete));}
  @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);if(session!=null)session.handler.removeCallbacks(session.tick);super.onDestroy();}
}
