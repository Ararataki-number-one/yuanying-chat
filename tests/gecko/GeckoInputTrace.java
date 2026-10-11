package local.pocketchat;

import android.os.Handler;
import android.os.SystemClock;
import android.view.inputmethod.CursorAnchorInfo;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.ExtractedText;
import android.view.inputmethod.ExtractedTextRequest;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputConnectionWrapper;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONObject;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.SessionTextInput;

/** Test-only observation of the existing SDK/IME path, without replacing its view or listener. */
final class GeckoInputTrace {
  interface LogSink {void record(JSONObject event);}
  private static final int LIMIT=256;
  private final SessionTextInput input;
  private final Field clientField;
  private final Object originalClient,observedClient;
  private final GeckoSession.TextInputDelegate originalDelegate,observedDelegate;
  private final LogSink sink;
  private final AtomicInteger sequence=new AtomicInteger();
  private volatile boolean active=true;

  static GeckoInputTrace attach(GeckoSession session,LogSink sink)throws ReflectiveOperationException {
    return new GeckoInputTrace(session,sink);
  }

  private GeckoInputTrace(GeckoSession session,LogSink sink)throws ReflectiveOperationException {
    this.input=session.getTextInput();this.sink=sink;
    clientField=SessionTextInput.class.getDeclaredField("mInputConnection");clientField.setAccessible(true);
    originalClient=clientField.get(input);
    if(originalClient==null)throw new IllegalStateException("The existing SDK input client is not initialized");
    originalDelegate=input.getDelegate();
    // The SDK's own GeckoInputConnection.wrapForDebug uses this same private
    // client-interface proxy pattern. Forward its handler/view unchanged and
    // observe only the InputConnection returned to Android after real focus.
    Class<?> listenerType=Class.forName("org.mozilla.geckoview.SessionTextInput$EditableListener",false,clientField.getType().getClassLoader());
    observedClient=Proxy.newProxyInstance(clientField.getType().getClassLoader(),new Class<?>[]{clientField.getType(),listenerType},(proxy,method,args)->{
      method.setAccessible(true);Object value;
      try{value=method.invoke(originalClient,args);}catch(InvocationTargetException failure){throw failure.getCause();}
      if("onCreateInputConnection".equals(method.getName())){
        EditorInfo attrs=args!=null&&args.length>0&&args[0] instanceof EditorInfo?(EditorInfo)args[0]:null;
        emit("client.onCreateInputConnection","available",value!=null,"start",attrs==null?-1:attrs.initialSelStart,"end",attrs==null?-1:attrs.initialSelEnd,"inputType",attrs==null?0:attrs.inputType,"imeOptions",attrs==null?0:attrs.imeOptions);
        if(value instanceof InputConnection)return new ObservedConnection((InputConnection)value);
      }
      if("getHandler".equals(method.getName()))emit("client.getHandler","handlerThread",value instanceof Handler?((Handler)value).getLooper().getThread().getName():"");
      else if("onSelectionChange".equals(method.getName()))emit("listener.onSelectionChange");
      else if("notifyIME".equals(method.getName()))emit("listener.notifyIME","type",args!=null&&args.length>0?args[0]:JSONObject.NULL);
      return value;
    });
    observedDelegate=new GeckoSession.TextInputDelegate(){
      @Override public void restartInput(GeckoSession session,int reason){emit("delegate.restartInput","reason",reason);originalDelegate.restartInput(session,reason);}
      @Override public void showSoftInput(GeckoSession session){emit("delegate.showSoftInput");originalDelegate.showSoftInput(session);}
      @Override public void hideSoftInput(GeckoSession session){emit("delegate.hideSoftInput");originalDelegate.hideSoftInput(session);}
      @Override public void updateSelection(GeckoSession session,int start,int end,int compositionStart,int compositionEnd){emit("delegate.updateSelection","start",start,"end",end,"compositionStart",compositionStart,"compositionEnd",compositionEnd);originalDelegate.updateSelection(session,start,end,compositionStart,compositionEnd);}
      @Override public void updateExtractedText(GeckoSession session,ExtractedTextRequest request,ExtractedText text){emit("delegate.updateExtractedText","token",request.token,"start",text.selectionStart,"end",text.selectionEnd,"startOffset",text.startOffset,"partialStartOffset",text.partialStartOffset,"partialEndOffset",text.partialEndOffset,"textLength",text.text==null?0:text.text.length());originalDelegate.updateExtractedText(session,request,text);}
      @Override public void updateCursorAnchorInfo(GeckoSession session,CursorAnchorInfo info){emit("delegate.updateCursorAnchorInfo","start",info.getSelectionStart(),"end",info.getSelectionEnd(),"compositionStart",info.getComposingTextStart(),"compositionLength",info.getComposingText()==null?0:info.getComposingText().length());originalDelegate.updateCursorAnchorInfo(session,info);}
    };
    clientField.set(input,observedClient);input.setDelegate(observedDelegate);
    emit("trace.attached","session",System.identityHashCode(session),"client",originalClient.getClass().getName(),"delegate",originalDelegate.getClass().getName());
  }

  /** Called on the fixture UI thread; old Android connections still delegate normally. */
  void stop(){
    if(!active)return;emit("trace.stopped");
    try{
      if(clientField.get(input)==observedClient)clientField.set(input,originalClient);
      if(input.getDelegate()==observedDelegate)input.setDelegate(originalDelegate);
    }catch(IllegalAccessException|RuntimeException failure){emit("trace.restoreFailed","error",failure.toString());}
    active=false;
  }

  private void emit(String api,Object... fields){
    if(!active)return;int seq=sequence.getAndIncrement();if(seq>LIMIT)return;
    JSONObject event=J.obj("id","current-input","seq",seq,"elapsedRealtime",SystemClock.elapsedRealtime(),"uptimeMillis",SystemClock.uptimeMillis(),"wallTimeMillis",System.currentTimeMillis(),"thread",Thread.currentThread().getName(),"api",seq==LIMIT?"trace.overflow":api);
    try{
      if(seq<LIMIT)for(int i=0;i+1<fields.length;i+=2)event.put(String.valueOf(fields[i]),fields[i+1]);
      // The sink can be called on the original SDK input thread. It must only
      // log the immutable event; no posting, blocking, editing or re-ordering.
      sink.record(event);
    }catch(RuntimeException|org.json.JSONException ignored){/* A diagnostic observer cannot alter input delivery. */}
  }

  private final class ObservedConnection extends InputConnectionWrapper {
    ObservedConnection(InputConnection target){super(target,false);}
    @Override public Handler getHandler(){return super.getHandler();}
    @Override public boolean setSelection(int start,int end){emit("ime.setSelection","start",start,"end",end);return super.setSelection(start,end);}
    @Override public boolean commitText(CharSequence text,int cursor){emit("ime.commitText","textLength",text==null?0:text.length(),"cursor",cursor);return super.commitText(text,cursor);}
    @Override public boolean commitText(CharSequence text,int cursor,android.view.inputmethod.TextAttribute attribute){emit("ime.commitTextWithAttribute","textLength",text==null?0:text.length(),"cursor",cursor);return super.commitText(text,cursor,attribute);}
    @Override public boolean setComposingText(CharSequence text,int cursor){emit("ime.setComposingText","textLength",text==null?0:text.length(),"cursor",cursor);return super.setComposingText(text,cursor);}
    @Override public boolean setComposingText(CharSequence text,int cursor,android.view.inputmethod.TextAttribute attribute){emit("ime.setComposingTextWithAttribute","textLength",text==null?0:text.length(),"cursor",cursor);return super.setComposingText(text,cursor,attribute);}
    @Override public boolean setComposingRegion(int start,int end){emit("ime.setComposingRegion","start",start,"end",end);return super.setComposingRegion(start,end);}
    @Override public boolean setComposingRegion(int start,int end,android.view.inputmethod.TextAttribute attribute){emit("ime.setComposingRegionWithAttribute","start",start,"end",end);return super.setComposingRegion(start,end,attribute);}
    @Override public boolean replaceText(int start,int end,CharSequence text,int cursor,android.view.inputmethod.TextAttribute attribute){emit("ime.replaceText","start",start,"end",end,"textLength",text==null?0:text.length(),"cursor",cursor);return super.replaceText(start,end,text,cursor,attribute);}
    @Override public boolean finishComposingText(){emit("ime.finishComposingText");return super.finishComposingText();}
    @Override public boolean deleteSurroundingText(int before,int after){emit("ime.deleteSurroundingText","before",before,"after",after);return super.deleteSurroundingText(before,after);}
    @Override public boolean deleteSurroundingTextInCodePoints(int before,int after){emit("ime.deleteSurroundingTextInCodePoints","before",before,"after",after);return super.deleteSurroundingTextInCodePoints(before,after);}
    @Override public boolean beginBatchEdit(){emit("ime.beginBatchEdit");return super.beginBatchEdit();}
    @Override public boolean endBatchEdit(){emit("ime.endBatchEdit");return super.endBatchEdit();}
    @Override public boolean sendKeyEvent(android.view.KeyEvent event){emit("ime.sendKeyEvent","action",event.getAction(),"keyCode",event.getKeyCode(),"eventTime",event.getEventTime());return super.sendKeyEvent(event);}
  }
}
