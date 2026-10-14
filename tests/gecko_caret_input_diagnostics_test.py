"""Execute the fixture's input diagnostics against explicit host Java doubles.

These controls cover forwarding, read-only snapshots, and evidence ownership.
They do not execute Android, Gecko, an IME, an APK, or trusted device input.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / 'tests/gecko/GeckoCaretCompatibilityIntegrationActivity.java'
PINNED_JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')


def actual_fragment(source, declaration):
    """Extract a complete actual method/class, respecting Java strings/comments."""
    match = re.search(declaration,source)
    if match is None:
        raise AssertionError('Actual input diagnostic declaration is absent: '+declaration)
    cursor,depth,quote = match.end(),1,None
    while cursor<len(source):
        char = source[cursor]
        if quote:
            if char=='\\':
                cursor += 2
                continue
            if char==quote:
                quote = None
        elif char in ('"',"'"):
            quote = char
        elif source.startswith('//',cursor):
            end = source.find('\n',cursor)
            cursor = len(source) if end<0 else end
            continue
        elif source.startswith('/*',cursor):
            end = source.find('*/',cursor+2)
            if end<0:
                raise AssertionError('Unterminated actual input diagnostic comment')
            cursor = end+2
            continue
        elif char=='{':
            depth += 1
        elif char=='}':
            depth -= 1
            if not depth:
                return source[match.start():cursor+1]
        cursor += 1
    raise AssertionError('Incomplete actual input diagnostic declaration')


JAVA_DOUBLES = {
    'android/view/View.java': 'package android.view; public class View {}\n',
    'android/content/Context.java': 'package android.content; public class Context {}\n',
    'android/widget/FrameLayout.java': '''package android.widget;
public class FrameLayout {public static class LayoutParams {public LayoutParams(int width,int height){}}}''',
    'android/view/inputmethod/EditorInfo.java': 'package android.view.inputmethod; public class EditorInfo {}\n',
    'android/view/inputmethod/TextAttribute.java': '''package android.view.inputmethod;
public class TextAttribute {public String toString(){return "Synthetic TextAttribute 中文🙂";}}''',
    'org/mozilla/geckoview/GeckoView.java': '''package org.mozilla.geckoview;
import android.content.Context;import android.view.inputmethod.*;
public class GeckoView {
  public static final int BACKEND_TEXTURE_VIEW=1;
  public static InputConnection originalToReturn;public static int createCalls;public static EditorInfo receivedAttrs;
  public GeckoView(Context context){}public void setViewBackend(int backend){}
  public InputConnection onCreateInputConnection(EditorInfo attrs){createCalls++;receivedAttrs=attrs;return originalToReturn;}
}''',
    'android/os/SystemClock.java': '''package android.os;
public final class SystemClock {
  public static long elapsedRealtime(){return System.nanoTime()/1000000;}
  public static long elapsedRealtimeNanos(){return System.nanoTime();}
}''',
    'android/text/Spannable.java': '''package android.text;
public interface Spannable extends CharSequence {
  int getSpanStart(Object tag); int getSpanEnd(Object tag);
  void setSpan(Object tag,int start,int end,int flags); void removeSpan(Object tag);
}''',
    'android/text/Editable.java': '''package android.text;
public interface Editable extends Spannable {}''',
    'android/text/Selection.java': '''package android.text;
public final class Selection {
  public static final Object SELECTION_START=new Object(),SELECTION_END=new Object();
  public static int getSelectionStart(CharSequence text){return ((Spannable)text).getSpanStart(SELECTION_START);}
  public static int getSelectionEnd(CharSequence text){return ((Spannable)text).getSpanStart(SELECTION_END);}
  public static void setSelection(Spannable text,int start,int end){
    text.setSpan(SELECTION_START,start,start,0);text.setSpan(SELECTION_END,end,end,0);
  }
}''',
    'android/view/inputmethod/InputConnection.java': '''package android.view.inputmethod;
public interface InputConnection {
  boolean finishComposingText(); boolean setSelection(int start,int end);
  boolean setComposingText(CharSequence text,int cursor); boolean commitText(CharSequence text,int cursor);
  boolean setComposingText(CharSequence text,int cursor,TextAttribute attribute);
  boolean commitText(CharSequence text,int cursor,TextAttribute attribute);
  boolean beginBatchEdit(); boolean endBatchEdit();
  boolean setComposingRegion(int start,int end);boolean setComposingRegion(int start,int end,TextAttribute attribute);
  boolean replaceText(int start,int end,CharSequence text,int cursor,TextAttribute attribute);
  boolean deleteSurroundingText(int before,int after);boolean deleteSurroundingTextInCodePoints(int before,int after);
  void closeConnection();
}''',
    'android/view/inputmethod/InputConnectionWrapper.java': '''package android.view.inputmethod;
public class InputConnectionWrapper implements InputConnection {
  public static InputConnection constructedTarget;public static boolean constructedMutable;
  private InputConnection target;private final boolean mutable;
  public InputConnectionWrapper(InputConnection target,boolean mutable){
    this.target=target;this.mutable=mutable;constructedTarget=target;constructedMutable=mutable;
  }
  public void setTarget(InputConnection replacement){
    if(!mutable)throw new SecurityException("Synthetic immutable wrapper target");target=replacement;
  }
  public boolean finishComposingText(){return target.finishComposingText();}
  public boolean setSelection(int start,int end){return target.setSelection(start,end);}
  public boolean setComposingText(CharSequence text,int cursor){return target.setComposingText(text,cursor);}
  public boolean setComposingText(CharSequence text,int cursor,TextAttribute attribute){return target.setComposingText(text,cursor,attribute);}
  public boolean commitText(CharSequence text,int cursor){return target.commitText(text,cursor);}
  public boolean commitText(CharSequence text,int cursor,TextAttribute attribute){return target.commitText(text,cursor,attribute);}
  public boolean beginBatchEdit(){return target.beginBatchEdit();}
  public boolean endBatchEdit(){return target.endBatchEdit();}
  public boolean setComposingRegion(int start,int end){return target.setComposingRegion(start,end);}
  public boolean setComposingRegion(int start,int end,TextAttribute attribute){return target.setComposingRegion(start,end,attribute);}
  public boolean replaceText(int start,int end,CharSequence text,int cursor,TextAttribute attribute){return target.replaceText(start,end,text,cursor,attribute);}
  public boolean deleteSurroundingText(int before,int after){return target.deleteSurroundingText(before,after);}
  public boolean deleteSurroundingTextInCodePoints(int before,int after){return target.deleteSurroundingTextInCodePoints(before,after);}
  public void closeConnection(){target.closeConnection();}
}''',
    'android/view/inputmethod/BaseInputConnection.java': '''package android.view.inputmethod;
import android.text.*;import android.view.View;
public class BaseInputConnection implements InputConnection {
  public static final Object SYNTHETIC_COMPOSING=new Object();
  public BaseInputConnection(View target,boolean fullEditor){}
  public Editable getEditable(){return null;}
  public static int getComposingSpanStart(Spannable text){return text.getSpanStart(SYNTHETIC_COMPOSING);}
  public static int getComposingSpanEnd(Spannable text){return text.getSpanEnd(SYNTHETIC_COMPOSING);}
  public boolean finishComposingText(){throw new AssertionError("Unadapted synthetic method");}
  public boolean setSelection(int start,int end){throw new AssertionError("Unadapted synthetic method");}
  public boolean setComposingText(CharSequence text,int cursor){throw new AssertionError("Unadapted synthetic method");}
  public boolean setComposingText(CharSequence text,int cursor,TextAttribute attribute){throw new AssertionError("Unadapted synthetic method");}
  public boolean commitText(CharSequence text,int cursor){throw new AssertionError("Unadapted synthetic method");}
  public boolean commitText(CharSequence text,int cursor,TextAttribute attribute){throw new AssertionError("Unadapted synthetic method");}
  public boolean beginBatchEdit(){throw new AssertionError("Unadapted synthetic method");}
  public boolean endBatchEdit(){throw new AssertionError("Unadapted synthetic method");}
  public boolean setComposingRegion(int start,int end){throw new AssertionError("Unadapted synthetic method");}
  public boolean setComposingRegion(int start,int end,TextAttribute attribute){throw new AssertionError("Unadapted synthetic method");}
  public boolean replaceText(int start,int end,CharSequence text,int cursor,TextAttribute attribute){throw new AssertionError("Unadapted synthetic method");}
  public boolean deleteSurroundingText(int before,int after){throw new AssertionError("Unadapted synthetic method");}
  public boolean deleteSurroundingTextInCodePoints(int before,int after){throw new AssertionError("Unadapted synthetic method");}
  public void closeConnection(){throw new AssertionError("Unadapted synthetic method");}
}''',
    'org/json/JSONObject.java': '''package org.json;
import java.util.*;
public class JSONObject {
  public static final Object NULL=new Object();
  public final Map<String,Object> values=new LinkedHashMap<>();
  public JSONObject put(String key,Object value){values.put(key,value);return this;}
  public Object get(String key){if(!values.containsKey(key))throw new IllegalArgumentException("Missing "+key);return values.get(key);}
  public Object opt(String key){return values.get(key);}public boolean has(String key){return values.containsKey(key);}
  public String getString(String key){return (String)get(key);}
  public String optString(String key){return optString(key,"");}
  public String optString(String key,String fallback){Object v=values.get(key);return v instanceof String?(String)v:fallback;}
  public int getInt(String key){return ((Number)get(key)).intValue();}
  public int optInt(String key){return optInt(key,0);}
  public int optInt(String key,int fallback){Object v=values.get(key);return v instanceof Number?((Number)v).intValue():fallback;}
  public long optLong(String key){return optLong(key,0);}
  public long optLong(String key,long fallback){Object v=values.get(key);return v instanceof Number?((Number)v).longValue():fallback;}
  public double getDouble(String key){return ((Number)get(key)).doubleValue();}
  public double optDouble(String key){Object v=values.get(key);return v instanceof Number?((Number)v).doubleValue():Double.NaN;}
  public boolean getBoolean(String key){return (Boolean)get(key);}
  public boolean optBoolean(String key){return Boolean.TRUE.equals(values.get(key));}
  public JSONObject getJSONObject(String key){return (JSONObject)get(key);}
  public JSONObject optJSONObject(String key){return (JSONObject)values.get(key);}
  public JSONArray getJSONArray(String key){return (JSONArray)get(key);}
  public JSONArray optJSONArray(String key){return (JSONArray)values.get(key);}
  public Object remove(String key){return values.remove(key);}
  public String toString(){return values.toString();}
}''',
    'org/json/JSONArray.java': '''package org.json;
import java.util.*;
public class JSONArray {
  public final List<Object> values=new ArrayList<>();
  public JSONArray(){}public JSONArray(Collection<?> initial){values.addAll(initial);}
  public JSONArray put(Object value){values.add(value);return this;}public int length(){return values.size();}
  public Object get(int i){return values.get(i);}public JSONObject getJSONObject(int i){return (JSONObject)get(i);}
  public JSONObject optJSONObject(int i){return i<values.size()?(JSONObject)values.get(i):null;}
  public String toString(){return values.toString();}
}''',
}


JAVA_CHECKS = r'''
  static final String SOURCE="a".repeat(40),RUN="12345",ATTEMPT="2",NONCE="e".repeat(32);
  static final double TIME_ORIGIN=12345;
  static final String[] APIS={"finishComposingText","setSelection","setComposingText",
    "setComposingTextWithAttribute","commitText","commitTextWithAttribute","beginBatchEdit","endBatchEdit",
    "setComposingRegion","setComposingRegionWithAttribute","replaceText","deleteSurroundingText",
    "deleteSurroundingTextInCodePoints","closeConnection"};
  static final CharSequence TEXT=new StringBuilder("你🙂 synthetic text");
  static final TextAttribute ATTRIBUTE=new TextAttribute();
  static class J {
    static JSONObject obj(Object... pairs){JSONObject value=new JSONObject();for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);return value;}
    static JSONArray arr(Object... values){JSONArray result=new JSONArray();for(Object value:values)result.put(value);return result;}
  }
  static void require(boolean condition,String message){if(!condition)throw new AssertionError(message);}
  interface Work {void run() throws Exception;}
  static void rejected(Work call)throws Exception{
    try{call.run();}catch(Exception expected){return;}
    throw new AssertionError("Invalid diagnostic event owner/order was accepted");
  }
  static class FakeEditable implements Editable {
    String text="seedni tail";int start=6,end=6,compositionStart=4,compositionEnd=6,writes;
    public int length(){return text.length();}public char charAt(int i){return text.charAt(i);}
    public CharSequence subSequence(int start,int end){return text.subSequence(start,end);}
    public String toString(){return text;}
    public int getSpanStart(Object tag){
      if(tag==Selection.SELECTION_START)return start;if(tag==Selection.SELECTION_END)return end;
      return tag==BaseInputConnection.SYNTHETIC_COMPOSING?compositionStart:-1;
    }
    public int getSpanEnd(Object tag){return tag==BaseInputConnection.SYNTHETIC_COMPOSING?compositionEnd:getSpanStart(tag);}
    public void setSpan(Object tag,int start,int end,int flags){writes++;throw new AssertionError("Diagnostic snapshot called a setter");}
    public void removeSpan(Object tag){writes++;throw new AssertionError("Diagnostic snapshot removed a span");}
  }
  static class FakeOriginal extends BaseInputConnection {
    final FakeEditable editable=new FakeEditable();final List<String> calls=new ArrayList<>();
    Object[] arguments;boolean result=true,missingEditable;int reads;Throwable readFailure,inputFailure;
    FakeOriginal(){super(new android.view.View(),true);}
    public Editable getEditable(){reads++;throwSame(readFailure);return missingEditable?null:editable;}
    static void throwSame(Throwable failure){if(failure instanceof RuntimeException)throw (RuntimeException)failure;if(failure instanceof Error)throw (Error)failure;}
    boolean called(String api,Object... arguments){
      calls.add(api);this.arguments=arguments;
      // These authorized target changes are synthetic and deliberately do not
      // implement Android editing semantics. Diagnostics must merely observe them.
      editable.text="Synthetic target changed "+api;editable.start=2;editable.end=5;
      editable.compositionStart=-1;editable.compositionEnd=-1;
      throwSame(inputFailure);return result;
    }
    public boolean finishComposingText(){return called("finishComposingText");}
    public boolean setSelection(int start,int end){return called("setSelection",start,end);}
    public boolean setComposingText(CharSequence text,int cursor){return called("setComposingText",text,cursor);}
    public boolean setComposingText(CharSequence text,int cursor,TextAttribute attribute){return called("setComposingTextWithAttribute",text,cursor,attribute);}
    public boolean commitText(CharSequence text,int cursor){return called("commitText",text,cursor);}
    public boolean commitText(CharSequence text,int cursor,TextAttribute attribute){return called("commitTextWithAttribute",text,cursor,attribute);}
    public boolean beginBatchEdit(){return called("beginBatchEdit");}
    public boolean endBatchEdit(){return called("endBatchEdit");}
    public boolean setComposingRegion(int start,int end){return called("setComposingRegion",start,end);}
    public boolean setComposingRegion(int start,int end,TextAttribute attribute){return called("setComposingRegionWithAttribute",start,end,attribute);}
    public boolean replaceText(int start,int end,CharSequence text,int cursor,TextAttribute attribute){return called("replaceText",start,end,text,cursor,attribute);}
    public boolean deleteSurroundingText(int before,int after){return called("deleteSurroundingText",before,after);}
    public boolean deleteSurroundingTextInCodePoints(int before,int after){return called("deleteSurroundingTextInCodePoints",before,after);}
    public void closeConnection(){called("closeConnection");}
  }
  static Boolean invoke(InputConnection input,String api,CharSequence text,TextAttribute attribute){
    switch(api){
      case "finishComposingText":return input.finishComposingText();
      case "setSelection":return input.setSelection(5,2);
      case "setComposingText":return input.setComposingText(text,1);
      case "setComposingTextWithAttribute":return input.setComposingText(text,1,attribute);
      case "commitText":return input.commitText(text,-1);
      case "commitTextWithAttribute":return input.commitText(text,-1,attribute);
      case "beginBatchEdit":return input.beginBatchEdit();case "endBatchEdit":return input.endBatchEdit();
      case "setComposingRegion":return input.setComposingRegion(4,6);
      case "setComposingRegionWithAttribute":return input.setComposingRegion(4,6,attribute);
      case "replaceText":return input.replaceText(4,6,text,1,attribute);
      case "deleteSurroundingText":return input.deleteSurroundingText(1,2);
      case "deleteSurroundingTextInCodePoints":return input.deleteSurroundingTextInCodePoints(2,0);
      case "closeConnection":input.closeConnection();return null;
      default:throw new AssertionError("Unknown host callback vector");
    }
  }
  static Object[] expectedArguments(String api,Object text,Object attribute){
    switch(api){
      case "setSelection":return new Object[]{5,2};
      case "setComposingText":return new Object[]{text,1};
      case "setComposingTextWithAttribute":return new Object[]{text,1,attribute};
      case "commitText":return new Object[]{text,-1};
      case "commitTextWithAttribute":return new Object[]{text,-1,attribute};
      case "setComposingRegion":return new Object[]{4,6};
      case "setComposingRegionWithAttribute":return new Object[]{4,6,attribute};
      case "replaceText":return new Object[]{4,6,text,1,attribute};
      case "deleteSurroundingText":return new Object[]{1,2};
      case "deleteSurroundingTextInCodePoints":return new Object[]{2,0};
      default:return new Object[]{};
    }
  }
  static void state(JSONObject snapshot,FakeOriginal original,boolean before){
    require(snapshot.getBoolean("available"),"Public original state must be available");
    require(snapshot.getString("draft").equals(before?"seedni tail":original.editable.text),"Snapshot draft differs");
    require(snapshot.getInt("start")== (before?6:2)&&snapshot.getInt("end")== (before?6:5),"Snapshot selection differs");
    require(snapshot.getInt("composingStart")== (before?4:-1)&&snapshot.getInt("composingEnd")== (before?6:-1),"Snapshot composition differs");
    require(snapshot.getInt("connectionIdentity")==System.identityHashCode(original),"Snapshot substituted original object");
    require(snapshot.optLong("thread")==Thread.currentThread().getId(),"Snapshot thread was invented");
    require(snapshot.getBoolean("javaStateOnly")&&!snapshot.getBoolean("nativeAcknowledgement"),"Read state was promoted to native ACK");
    require(original.editable.writes==0,"Diagnostics changed original spans");
  }
  static void successfulRow(JSONObject row,FakeOriginal original,String api,CharSequence text,TextAttribute attribute){
    require(row.getString("api").equals(api)&&row.getString("origin").equals("android-returned-inputconnection-forwarded-original-sdk"),"Callback owner differs");
    require(row.getInt("forwardCount")==1&&row.getInt("connectionIdentity")==System.identityHashCode(original),"Forward target/count differs");
    require(row.optLong("thread")==Thread.currentThread().getId(),"Callback thread differs");
    require(row.optLong("startedAtElapsedRealtime")>0&&row.optLong("completedAtElapsedRealtime")>=row.optLong("startedAtElapsedRealtime"),"Callback lifetime missing/unordered");
    Object value=api.equals("closeConnection")?JSONObject.NULL:original.result;
    require(row.get("returned")==value||row.get("returned").equals(value),"Return value changed");
    require(row.getString("returnKind").equals(api.equals("closeConnection")?"void":"boolean"),"Void method was exposed as boolean");
    require(Arrays.equals(row.getJSONArray("arguments").values.toArray(),expectedArguments(api,
      text==null?JSONObject.NULL:text.toString(),attribute==null?JSONObject.NULL:attribute.toString())),"Logged arguments differ");
    state(row.getJSONObject("before"),original,true);state(row.getJSONObject("after"),original,false);
  }
  static class BadText implements CharSequence {
    public int length(){return 1;}public char charAt(int i){return 'Q';}public CharSequence subSequence(int s,int e){return this;}
    public String toString(){throw new AssertionError("Synthetic argument diagnostic failure");}
  }
  static JSONObject document(int count){
    JSONArray events=new JSONArray();for(int i=0;i<count;i++)events.put(J.obj("index",i,"type",i==1?"compositionend":"input",
      "trusted",false,"data","Synthetic raw 中文🙂\n"+i,"start",i,"end",i,"draft","Synthetic document "+i));
    return J.obj("sourceCommit",SOURCE,"runId",RUN,"runAttempt",ATTEMPT,"runNonce",NONCE,"case",6,
      "documentUrl",ORIGIN+"/caret?case=6","timeOrigin",TIME_ORIGIN,"eventCount",count,"events",events);
  }
  static JSONArray chunks(JSONObject value,double origin)throws Exception{
    return failureEventChunks(value,SOURCE,RUN,ATTEMPT,NONCE,6,origin);
  }
  static class HostQueue {
    final List<Runnable> pending=new ArrayList<>();int posts;
    boolean post(Runnable task){posts++;pending.add(task);return true;}
    void flush(){List<Runnable> batch=new ArrayList<>(pending);pending.clear();for(Runnable task:batch)task.run();}
    private void postToInputConnection(Runnable task){post(task);}
  }
  static class FakeSdk {
    private final InputConnection mInputConnection;private final HostQueue mEditable=new HostQueue();
    FakeSdk(InputConnection original){mInputConnection=original;}
  }
  static class HostSession {FakeSdk sdk;Object getTextInput(){return sdk;}}
  static class ChatSession {GeckoWebView web;}
  static class GeckoWebView {
    final Context displayContext;org.mozilla.geckoview.GeckoView surface;final HostSession current=new HostSession();
    GeckoWebView(Context context,ChatSession owner){displayContext=context;}
    void addView(org.mozilla.geckoview.GeckoView view,android.widget.FrameLayout.LayoutParams params){}
    protected boolean allowedUrl(String value){return false;}boolean readingPage(String value){return false;}
  }
  final List<JSONObject> diagnostics=new ArrayList<>();void recordExternalIme(JSONObject value){diagnostics.add(value);}
  final HostQueue handler=new HostQueue();ChatSession session;final JSONArray apiCalls=new JSONArray(),currentActions=new JSONArray();
  void attempt(Step action){try{action.run();}catch(Exception error){throw new RuntimeException(error);}}
  void check(String name,boolean pass){require(pass,name);}
  final List<String> emittedKinds=new ArrayList<>();final List<JSONObject> emittedValues=new ArrayList<>();
  JSONObject observed,initialSnapshot;String sourceCommit=SOURCE,runId=RUN,runAttempt=ATTEMPT,runNonce=NONCE;int scenario=6;
  // Transport and JSON compaction adapters are explicit host doubles; the
  // actual failure function/chunk helper alone decide what gets emitted.
  JSONObject compact(JSONObject value){JSONObject copy=new JSONObject();copy.values.putAll(value.values);copy.remove("events");return copy;}
  void event(String kind,JSONObject value){emittedKinds.add(kind);emittedValues.add(value);}
  void report(String status,String error){event("report",J.obj("status",status,"error",error));}
  public static void main(String[] args)throws Exception{
    switch(args[0]){
      case "readonly-state":{
        FakeOriginal original=new FakeOriginal();original.editable.text="你🙂 original draft";
        original.editable.start=8;original.editable.end=3;
        JSONObject snapshot=originalInputState(original);
        require(snapshot.getString("draft").equals("你🙂 original draft"),"Unicode draft was rewritten");
        require(snapshot.getInt("start")==8&&snapshot.getInt("end")==3,"Reversed selection was normalized");
        require(snapshot.getInt("composingStart")==4&&snapshot.getInt("composingEnd")==6,"Composition was rewritten");
        require(snapshot.getBoolean("javaStateOnly")&&!snapshot.getBoolean("nativeAcknowledgement"),"Snapshot falsely acknowledges Gecko");
        require(original.calls.isEmpty()&&original.reads==1&&original.editable.writes==0,"Read state invoked an editing API");
        break;
      }
      case "unavailable-state":{
        FakeOriginal original=new FakeOriginal();
        for(InputConnection input:new InputConnection[]{null,new InputConnectionWrapper(original,false)}){
          JSONObject snapshot=originalInputState(input);require(!snapshot.getBoolean("available"),"Unknown public API was fabricated");
          require(snapshot.getInt("connectionIdentity")==System.identityHashCode(input),"Unavailable state substituted target");
          require(snapshot.getBoolean("javaStateOnly")&&!snapshot.getBoolean("nativeAcknowledgement"),"Unavailable state claims native ACK");
        }
        original.missingEditable=true;require(!originalInputState(original).getBoolean("available"),"Missing Editable was fabricated");
        for(Throwable failure:new Throwable[]{new RuntimeException("Synthetic getter failure"),new AssertionError("Synthetic getter error")}){
          original.readFailure=failure;JSONObject snapshot=originalInputState(original);
          require(!snapshot.getBoolean("available")&&snapshot.getString("readError").equals(failure.toString()),"Getter error lost");
        }
        require(original.calls.isEmpty()&&original.editable.writes==0,"Unavailable state invoked editing API");break;
      }
      case "forward-results":{
        for(String api:APIS)for(boolean returned:new boolean[]{true,false}){
          FakeOriginal original=new FakeOriginal();original.result=returned;List<JSONObject> rows=new ArrayList<>();
          DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,rows::add);
          Boolean value=invoke(wrapper,api,TEXT,ATTRIBUTE);
          require(api.equals("closeConnection")?value==null:value==returned,"Wrapper return was changed");
          require(original.calls.equals(List.of(api))&&original.reads==2&&rows.size()==1,"Target was retried/skipped or unpaired state read");
          require(Arrays.equals(original.arguments,expectedArguments(api,TEXT,ATTRIBUTE)),"Original arguments/objects changed");
          successfulRow(rows.get(0),original,api,TEXT,ATTRIBUTE);
        }break;
      }
      case "immutable-target":{
        FakeOriginal original=new FakeOriginal(),foreign=new FakeOriginal();DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,value->{});
        require(wrapper.original==original&&InputConnectionWrapper.constructedTarget==original&&!InputConnectionWrapper.constructedMutable,"Original immutable target differs");
        try{wrapper.setTarget(foreign);throw new AssertionError("Wrapper target was mutable");}catch(SecurityException expected){}
        wrapper.finishComposingText();require(original.calls.equals(List.of("finishComposingText"))&&foreign.calls.isEmpty(),"Foreign target received mutation");break;
      }
      case "forward-errors":{
        for(String api:APIS)for(Throwable failure:new Throwable[]{new RuntimeException("Synthetic original failure"),new AssertionError("Synthetic original error")}){
          FakeOriginal original=new FakeOriginal();original.inputFailure=failure;List<JSONObject> rows=new ArrayList<>();
          DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,rows::add);
          try{invoke(wrapper,api,TEXT,ATTRIBUTE);throw new AssertionError("Original error was swallowed");}
          catch(RuntimeException|Error caught){require(caught==failure,"Original error was replaced");}
          require(original.calls.equals(List.of(api))&&original.reads==2&&rows.size()==1,"Failed target retried or finally snapshot missing");
          JSONObject row=rows.get(0);require(row.getString("error").equals(failure.toString())&&row.getString("errorType").equals(failure.getClass().getName()),"Original error diagnostic differs");
          require(!row.has("returned"),"Failed method fabricated return value");
          state(row.getJSONObject("before"),original,true);state(row.getJSONObject("after"),original,false);
          require(row.optLong("completedAtElapsedRealtime")>=row.optLong("startedAtElapsedRealtime"),"Failed callback lifetime missing");
        }break;
      }
      case "sink-errors":{
        for(Throwable sinkFailure:new Throwable[]{new RuntimeException("Synthetic sink failure"),new AssertionError("Synthetic sink error")})for(String api:APIS){
          for(boolean returned:new boolean[]{true,false}){
            FakeOriginal original=new FakeOriginal();original.result=returned;
            DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,value->FakeOriginal.throwSame(sinkFailure));
            Boolean value=invoke(wrapper,api,TEXT,ATTRIBUTE);
            require(api.equals("closeConnection")?value==null:value==returned,"Sink error changed return");
            require(original.calls.equals(List.of(api)),"Sink error changed original forwarding");
          }
          FakeOriginal original=new FakeOriginal();Throwable originalFailure=new RuntimeException("Synthetic distinct original failure");original.inputFailure=originalFailure;
          DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,value->FakeOriginal.throwSame(sinkFailure));
          try{invoke(wrapper,api,TEXT,ATTRIBUTE);throw new AssertionError("Original failure was swallowed");}
          catch(RuntimeException caught){require(caught==originalFailure,"Sink error replaced original failure");}
          require(original.calls.equals(List.of(api)),"Sink error caused replay");
        }break;
      }
      case "argument-errors":{
        CharSequence bad=new BadText();for(String api:new String[]{"setComposingText","setComposingTextWithAttribute","commitText","commitTextWithAttribute","replaceText"}){
          FakeOriginal original=new FakeOriginal();original.result=false;List<JSONObject> rows=new ArrayList<>();
          DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,rows::add);
          require(!invoke(wrapper,api,bad,ATTRIBUTE),"Argument logging error changed result");
          require(original.calls.equals(List.of(api))&&Arrays.equals(original.arguments,expectedArguments(api,bad,ATTRIBUTE)),"Argument error skipped/changed original call");
          require(rows.isEmpty(),"Failed argument capture fabricated a successful diagnostic");
        }break;
      }
      case "getter-errors-forward":{
        for(String api:APIS){FakeOriginal original=new FakeOriginal();original.readFailure=new AssertionError("Synthetic read failure");List<JSONObject> rows=new ArrayList<>();
          DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,rows::add);invoke(wrapper,api,TEXT,ATTRIBUTE);
          require(original.calls.equals(List.of(api))&&rows.size()==1,"Getter failure blocked original forwarding");
          for(String field:new String[]{"before","after"})require(!rows.get(0).getJSONObject(field).getBoolean("available"),"Failed getter produced invented state");
        }break;
      }
      case "null-arguments":{
        for(String api:new String[]{"setComposingText","setComposingTextWithAttribute","commitText","commitTextWithAttribute","setComposingRegionWithAttribute","replaceText"}){
          FakeOriginal original=new FakeOriginal();List<JSONObject> rows=new ArrayList<>();DiagnosticInputConnection wrapper=new DiagnosticInputConnection(original,rows::add);
          invoke(wrapper,api,null,null);require(Arrays.equals(original.arguments,expectedArguments(api,null,null)),"Null arguments were substituted");
          successfulRow(rows.get(0),original,api,null,null);
        }break;
      }
      case "android-return-installation":{
        GeckoCaretCompatibilityIntegrationActivity fixture=new GeckoCaretCompatibilityIntegrationActivity();FakeOriginal original=new FakeOriginal();
        org.mozilla.geckoview.GeckoView.originalToReturn=original;org.mozilla.geckoview.GeckoView.createCalls=0;
        FixtureView view=new FixtureView(new Context(),new ChatSession(),fixture);EditorInfo attrs=new EditorInfo();
        InputConnection returned=view.surface.onCreateInputConnection(attrs);
        require(returned instanceof DiagnosticInputConnection&&((DiagnosticInputConnection)returned).original==original,"Android return did not retain original target");
        require(org.mozilla.geckoview.GeckoView.createCalls==1&&org.mozilla.geckoview.GeckoView.receivedAttrs==attrs,"Original creation was retried/attributes replaced");
        // Direct fixture APIs continue using the original object independently
        // of the wrapper returned to Android.
        original.finishComposingText();require(fixture.diagnostics.isEmpty(),"Direct original API was relabeled as external IME");
        returned.finishComposingText();require(fixture.diagnostics.size()==1&&original.calls.size()==2,"Android return failed exact forwarding");
        org.mozilla.geckoview.GeckoView.originalToReturn=null;
        require(view.surface.onCreateInputConnection(attrs)==null,"Null original created a diagnostic connection");break;
      }
      case "readonly-checkpoint-post":{
        GeckoCaretCompatibilityIntegrationActivity fixture=new GeckoCaretCompatibilityIntegrationActivity();FakeOriginal original=new FakeOriginal();
        FixtureView view=new FixtureView(new Context(),new ChatSession(),fixture);FakeSdk sdk=new FakeSdk(original);view.current.sdk=sdk;
        fixture.session=new ChatSession();fixture.session.web=view;List<JSONObject> results=new ArrayList<>();
        fixture.observeOriginalState(results::add);
        require(sdk.mEditable.posts==1&&sdk.mEditable.pending.size()==1&&original.reads==0&&results.isEmpty(),"Read-only observation was paced/replayed or ran off original queue");
        sdk.mEditable.flush();require(original.reads==1&&fixture.handler.posts==1&&results.isEmpty(),"Original read or UI continuation count differs");
        fixture.handler.flush();require(results.size()==1,"Checkpoint read continued more than once");state(results.get(0),original,true);
        require(sdk.mInputConnection==original&&original.calls.isEmpty()&&fixture.diagnostics.isEmpty(),"Checkpoint probe replaced original or invoked editing API");break;
      }
      case "direct-api-pre-post":{
        GeckoCaretCompatibilityIntegrationActivity fixture=new GeckoCaretCompatibilityIntegrationActivity();FakeOriginal original=new FakeOriginal();
        FixtureView view=new FixtureView(new Context(),new ChatSession(),fixture);FakeSdk sdk=new FakeSdk(original);view.current.sdk=sdk;
        fixture.session=new ChatSession();fixture.session.web=view;List<String> order=new ArrayList<>();
        fixture.inputBatch(new String[]{"setComposingText"},new JSONArray[]{J.arr(TEXT.toString(),1)},
          new Edit[]{input->{require(input==original,"Direct fixture API received diagnostic wrapper");order.add("original-api");return input.setComposingText(TEXT,1);}},
          ()->order.add("next"));
        require(original.calls.isEmpty()&&sdk.mEditable.posts==1,"Direct API was paced/replayed or escaped original queue");
        sdk.mEditable.flush();require(original.calls.equals(List.of("setComposingText"))&&original.reads==2&&order.equals(List.of("original-api")),"Direct API pre/post reads changed forwarding");
        fixture.handler.flush();require(order.equals(List.of("original-api","next"))&&fixture.apiCalls.length()==1,"Direct API continuation/call journal duplicated");
        JSONObject call=fixture.apiCalls.getJSONObject(0);state(call.getJSONObject("javaStateBefore"),original,true);state(call.getJSONObject("javaStateAfter"),original,false);
        require(call.getString("origin").equals("original-sdk-inputconnection")&&call.getInt("connectionIdentity")==System.identityHashCode(original),"Direct SDK owner changed");
        require(Arrays.equals(call.getJSONArray("arguments").values.toArray(),new Object[]{TEXT.toString(),1}),"Direct API arguments changed");
        require(sdk.mInputConnection==original&&fixture.diagnostics.isEmpty(),"Direct API altered/reclassified SDK connection");break;
      }
      case "failure-chunks":{
        for(int count:new int[]{0,1,4,5,26,512}){
          JSONObject value=document(count);JSONArray original=value.getJSONArray("events"),captured=chunks(value,TIME_ORIGIN);
          require(captured.length()==(count+3)/4,"Bounded chunk count differs");int cursor=0;
          for(int i=0;i<captured.length();i++){
            JSONObject chunk=captured.getJSONObject(i),owner=chunk.getJSONObject("owner");JSONArray events=chunk.getJSONArray("events");
            require(chunk.getString("id").equals("chinese-composition")&&chunk.getBoolean("failure")&&chunk.getInt("offset")==cursor,"Failed chunk owner/order missing");
            require(owner.values.equals(J.obj("sourceCommit",SOURCE,"runId",RUN,"runAttempt",ATTEMPT,"runNonce",NONCE,
              "case",6,"documentUrl",ORIGIN+"/caret?case=6","timeOrigin",TIME_ORIGIN).values),"Chunk document/source/run owner differs");
            require(events.length()>0&&events.length()<=4,"Failed events exceed payload chunk bound");
            for(int e=0;e<events.length();e++,cursor++)require(events.getJSONObject(e)==original.getJSONObject(cursor),"Raw event was edited, dropped or reordered");
          }
          require(cursor==count&&original.length()==count&&value.getInt("eventCount")==count,"Chunking mutated/dropped source events");
        }break;
      }
      case "failure-owner-refusal":{
        for(String key:new String[]{"sourceCommit","runId","runAttempt","runNonce","documentUrl","case"}){
          JSONObject value=document(5);value.put(key,key.equals("case")?7:"foreign synthetic owner");rejected(()->chunks(value,TIME_ORIGIN));
        }
        for(double invalid:new double[]{0,-1,Double.NaN,Double.POSITIVE_INFINITY,Double.NEGATIVE_INFINITY,TIME_ORIGIN+1}){
          JSONObject value=document(5);value.put("timeOrigin",invalid);rejected(()->chunks(value,TIME_ORIGIN));
          rejected(()->chunks(document(5),invalid));
        }
        for(int number:new int[]{-1,14})rejected(()->failureEventChunks(document(5),SOURCE,RUN,ATTEMPT,NONCE,number,TIME_ORIGIN));break;
      }
      case "failure-bounds-order":{
        rejected(()->chunks(document(513),TIME_ORIGIN));
        for(int count:new int[]{-1,0,4,6}){JSONObject value=document(5);value.put("eventCount",count);rejected(()->chunks(value,TIME_ORIGIN));}
        for(int index:new int[]{0,4}){JSONObject value=document(5);value.getJSONArray("events").getJSONObject(index).put("index",99);rejected(()->chunks(value,TIME_ORIGIN));}
        JSONObject missing=document(5);missing.remove("events");rejected(()->chunks(missing,TIME_ORIGIN));break;
      }
      case "failure-emission":{
        GeckoCaretCompatibilityIntegrationActivity fixture=new GeckoCaretCompatibilityIntegrationActivity();fixture.observed=document(5);fixture.initialSnapshot=document(0);
        RuntimeException failure=new RuntimeException("Synthetic original failure 中文🙂");fixture.fail(failure);
        require(fixture.emittedKinds.equals(List.of("trustedEvents","trustedEvents","failureSnapshot","report")),"Actual failure omitted/reordered trusted events");
        require(fixture.emittedValues.get(0).getJSONArray("events").getJSONObject(0)==fixture.observed.getJSONArray("events").getJSONObject(0),"Failure rewrote raw event");
        require(!fixture.emittedValues.get(2).has("events"),"Failure snapshot duplicated unbounded raw events");
        require(fixture.emittedValues.get(3).getString("status").equals("failed")&&fixture.emittedValues.get(3).getString("error").equals(failure.toString()),"Diagnostics changed original failure");break;
      }
      case "failure-no-partial-emission":{
        for(String defect:new String[]{"late-event-index","foreign-timeOrigin","missing-initial-document"}){
          GeckoCaretCompatibilityIntegrationActivity fixture=new GeckoCaretCompatibilityIntegrationActivity();fixture.observed=document(5);fixture.initialSnapshot=document(0);
          if(defect.equals("late-event-index"))fixture.observed.getJSONArray("events").getJSONObject(4).put("index",99);
          if(defect.equals("foreign-timeOrigin"))fixture.initialSnapshot.put("timeOrigin",TIME_ORIGIN+1);
          if(defect.equals("missing-initial-document"))fixture.initialSnapshot=null;
          RuntimeException failure=new RuntimeException("Synthetic initial failure remains authoritative");fixture.fail(failure);
          require(fixture.emittedKinds.equals(List.of("failureSnapshot","report")),"Partial or foreign raw events escaped before rejection");
          require(fixture.emittedValues.get(0).has("failureEventCaptureError"),"Failed diagnostic capture gap was hidden");
          require(fixture.emittedValues.get(1).getString("error").equals(failure.toString()),"Capture error replaced original failure");
        }break;
      }
      default:throw new AssertionError("Unknown host diagnostic vector");
    }
    System.out.println("PASS "+args[0]+"; explicit host Java doubles only");
  }
'''


class CaretInputDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or (str(PINNED_JAVA) if PINNED_JAVA.exists() else shutil.which('java'))
        if not cls.java:
            raise RuntimeError('A host JDK is required to execute actual Java diagnostic fragments')
        cls.temporary = tempfile.TemporaryDirectory(prefix='caret-input-diagnostics-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        source = ACTIVITY.read_text()
        declarations = [r'\binterface\s+'+name+r'\s*\{' for name in ['DiagnosticSink','Forward','Arguments','Step','Result','Edit']]
        declarations += [r'\bstatic\s+JSONObject\s+originalInputState\s*\([^)]*\)\s*\{',
            r'\bstatic\s+final\s+class\s+DiagnosticInputConnection\b[^\{]*\{',
            r'\bstatic\s+final\s+class\s+FixtureView\b[^\{]*\{',
            r'\bstatic\s+JSONArray\s+failureEventChunks\s*\([^)]*\)\s*throws\s+Exception\s*\{',
            r'\bvoid\s+observeOriginalState\s*\([^)]*\)\s*\{',
            r'\bvoid\s+inputBatch\s*\([^)]*\)\s*throws\s+Exception\s*\{',
            r'\bvoid\s+fail\s*\(Exception\s+error\)\s*\{']
        fragments = '\n'.join(actual_fragment(source,pattern) for pattern in declarations)
        constants = []
        for pattern in [r'\bstatic\s+final\s+String\s+ORIGIN\s*=[^;]+;',
                        r'\bstatic\s+final\s+String\[\]\s+IDS\s*=[^;]+;']:
            found = re.search(pattern,source)
            if found is None:
                raise AssertionError('Actual document/scenario constant absent')
            constants.append(found.group())
        generated = ('import android.content.Context;import android.os.SystemClock;import android.text.*;'
            'import android.view.inputmethod.*;import java.util.*;import java.lang.reflect.*;import org.json.*;\n'
            'public final class GeckoCaretCompatibilityIntegrationActivity {\n'+
            '\n'.join(constants)+'\n'+fragments+'\n'+JAVA_CHECKS+'\n}\n')
        files = dict(JAVA_DOUBLES,**{'GeckoCaretCompatibilityIntegrationActivity.java':generated})
        paths = []
        for name,body in files.items():
            path = cls.directory/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(body)
            paths.append(str(path))
        compiled = subprocess.run([cls.java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8',*paths],
                                  text=True,capture_output=True,timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual diagnostic Java source did not compile:\n'+compiled.stdout+compiled.stderr)

    def vector(self,name):
        result = subprocess.run([self.java,'-cp',str(self.directory),'GeckoCaretCompatibilityIntegrationActivity',name],
                                text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(result.stdout.strip(),'PASS '+name+'; explicit host Java doubles only')

    def test_original_public_editable_read_is_exact_and_does_not_invoke_setters(self):
        self.vector('readonly-state')

    def test_unknown_missing_and_failed_editable_reads_remain_unavailable(self):
        self.vector('unavailable-state')

    def test_all_fourteen_methods_forward_once_with_exact_arguments_and_unchanged_results(self):
        self.vector('forward-results')

    def test_wrapper_target_is_original_and_cannot_be_replaced(self):
        self.vector('immutable-target')

    def test_original_runtime_exception_and_error_are_propagated_after_final_state_capture(self):
        self.vector('forward-errors')

    def test_diagnostic_sink_failures_cannot_change_results_or_replace_original_errors(self):
        self.vector('sink-errors')

    def test_argument_diagnostic_errors_cannot_block_or_change_original_call(self):
        self.vector('argument-errors')

    def test_editable_read_errors_cannot_block_original_forwarding(self):
        self.vector('getter-errors-forward')

    def test_null_text_and_attribute_are_forwarded_without_substitution(self):
        self.vector('null-arguments')

    def test_actual_fixture_wraps_only_android_return_and_preserves_null(self):
        self.vector('android-return-installation')

    def test_checkpoint_observation_posts_one_read_then_one_continuation_without_editing(self):
        self.vector('readonly-checkpoint-post')

    def test_direct_fixture_api_still_targets_original_sdk_with_exact_paired_state_reads(self):
        self.vector('direct-api-pre-post')

    def test_failure_events_keep_full_raw_order_owner_and_four_event_chunk_bound(self):
        self.vector('failure-chunks')

    def test_foreign_identity_document_case_and_time_origin_are_rejected(self):
        self.vector('failure-owner-refusal')

    def test_overflow_count_mismatch_missing_events_and_wrong_event_index_are_rejected(self):
        self.vector('failure-bounds-order')

    def test_actual_failure_emits_existing_trusted_event_kind_before_snapshot_and_original_report(self):
        self.vector('failure-emission')

    def test_late_corruption_and_foreign_document_cannot_emit_partial_chunks_or_replace_failure(self):
        self.vector('failure-no-partial-emission')


if __name__ == '__main__':
    unittest.main()

