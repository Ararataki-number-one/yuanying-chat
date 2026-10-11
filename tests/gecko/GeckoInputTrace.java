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
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicIntegerArray;
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

  static Buffered attachBuffered(GeckoSession session)throws ReflectiveOperationException {
    return new Buffered(session);
  }

  /**
   * Independent diagnostic: primitive storage on the original SDK/IME threads.
   * No live JSON, logcat, posting, editable reads or JavaScript instrumentation.
   * The observer still forwards each real call exactly once and preserves its
   * return value/exception. It is never attached by the normal regression.
   */
  static final class Buffered {
    static final int LIMIT=1024;
    static final int ATTACH=0,CREATE=1,SELECTION_NOTIFICATION=2,NOTIFY_IME=3,
      RESTART=4,SHOW=5,HIDE=6,SELECTION=7,EXTRACTED=8,CURSOR=9,
      SET_SELECTION=10,COMMIT=11,COMMIT_ATTRIBUTE=12,COMPOSING=13,
      COMPOSING_ATTRIBUTE=14,REGION=15,REGION_ATTRIBUTE=16,REPLACE=17,
      FINISH=18,DELETE=19,DELETE_CODEPOINTS=20,BATCH_BEGIN=21,BATCH_END=22,
      KEY=23,BEFORE_CURSOR=24,AFTER_CURSOR=25,SELECTED=26,SURROUNDING=27,
      GET_EXTRACTED=28,CHILD_ATTACHED=29,CHILD_COMPOSITION=30,
      CHILD_REPLACE=31,CHILD_SYNC=32,CHILD_KEY=33,CHILD_COMMIT=34;
    static final String[] APIS={"trace.attached","client.onCreateInputConnection",
      "listener.onSelectionChange","listener.notifyIME","delegate.restartInput",
      "delegate.showSoftInput","delegate.hideSoftInput","delegate.updateSelection",
      "delegate.updateExtractedText","delegate.updateCursorAnchorInfo",
      "ime.setSelection","ime.commitText","ime.commitTextWithAttribute",
      "ime.setComposingText","ime.setComposingTextWithAttribute",
      "ime.setComposingRegion","ime.setComposingRegionWithAttribute",
      "ime.replaceText","ime.finishComposingText","ime.deleteSurroundingText",
      "ime.deleteSurroundingTextInCodePoints","ime.beginBatchEdit","ime.endBatchEdit",
      "ime.sendKeyEvent","ime.getTextBeforeCursor","ime.getTextAfterCursor",
      "ime.getSelectedText","ime.getSurroundingText","ime.getExtractedText",
      "trace.focusedChildAttached","child.onImeUpdateComposition",
      "child.onImeReplaceText","child.onImeSynchronize","child.onKeyEvent",
      "child.onImeRequestCommit"};
    final int[] api=new int[LIMIT],phase=new int[LIMIT],a=new int[LIMIT],
      b=new int[LIMIT],c=new int[LIMIT],d=new int[LIMIT];
    final long[] uptime=new long[LIMIT],threads=new long[LIMIT];
    final AtomicInteger reserved=new AtomicInteger();
    final AtomicIntegerArray published=new AtomicIntegerArray(LIMIT);
    final SessionTextInput input;final Field clientField;
    final Object editable;final Field childField;final Method postToIc;
    final Object originalClient,observedClient;
    Object originalChild,observedChild;
    final GeckoSession.TextInputDelegate originalDelegate,observedDelegate;
    final long baseUptime=SystemClock.uptimeMillis(),baseElapsed=SystemClock.elapsedRealtime(),baseWall=System.currentTimeMillis();
    volatile boolean active=true;
    boolean childPreparationRequested;volatile boolean childAttached;
    volatile String childError="";

    Buffered(GeckoSession session)throws ReflectiveOperationException {
      input=session.getTextInput();
      clientField=SessionTextInput.class.getDeclaredField("mInputConnection");clientField.setAccessible(true);
      Field editableField=SessionTextInput.class.getDeclaredField("mEditable");editableField.setAccessible(true);editable=editableField.get(input);
      childField=editable.getClass().getDeclaredField("mFocusedChild");childField.setAccessible(true);
      postToIc=editable.getClass().getDeclaredMethod("postToInputConnection",Runnable.class);postToIc.setAccessible(true);
      originalClient=clientField.get(input);originalDelegate=input.getDelegate();
      if(originalClient==null)throw new IllegalStateException("The existing SDK input client is not initialized");
      Class<?> listener=Class.forName("org.mozilla.geckoview.SessionTextInput$EditableListener",false,clientField.getType().getClassLoader());
      observedClient=Proxy.newProxyInstance(clientField.getType().getClassLoader(),new Class<?>[]{clientField.getType(),listener},(proxy,method,args)->{
        String name=method.getName();int code="onSelectionChange".equals(name)?SELECTION_NOTIFICATION:"notifyIME".equals(name)?NOTIFY_IME:-1;
        int parameter=code==NOTIFY_IME&&args!=null&&args.length>0&&args[0] instanceof Integer?(Integer)args[0]:0;
        if(code>=0)record(code,0,parameter,0,0,0);
        method.setAccessible(true);Object value;
        try{value=method.invoke(originalClient,args);}catch(InvocationTargetException failure){throw failure.getCause();}
        if(code>=0)record(code,1,parameter,0,0,0);
        if("onCreateInputConnection".equals(name)){
          EditorInfo attrs=args!=null&&args.length>0&&args[0] instanceof EditorInfo?(EditorInfo)args[0]:null;
          record(CREATE,1,attrs==null?-1:attrs.initialSelStart,attrs==null?-1:attrs.initialSelEnd,attrs==null?0:attrs.inputType,value==null?0:1);
          if(value instanceof InputConnection)return new Connection((InputConnection)value);
        }
        return value;
      });
      observedDelegate=new GeckoSession.TextInputDelegate(){
        @Override public void restartInput(GeckoSession s,int reason){record(RESTART,0,reason,0,0,0);originalDelegate.restartInput(s,reason);record(RESTART,1,reason,0,0,0);}
        @Override public void showSoftInput(GeckoSession s){record(SHOW,0,0,0,0,0);originalDelegate.showSoftInput(s);record(SHOW,1,0,0,0,0);}
        @Override public void hideSoftInput(GeckoSession s){record(HIDE,0,0,0,0,0);originalDelegate.hideSoftInput(s);record(HIDE,1,0,0,0,0);}
        @Override public void updateSelection(GeckoSession s,int start,int end,int cs,int ce){record(SELECTION,0,start,end,cs,ce);originalDelegate.updateSelection(s,start,end,cs,ce);record(SELECTION,1,start,end,cs,ce);}
        @Override public void updateExtractedText(GeckoSession s,ExtractedTextRequest request,ExtractedText text){record(EXTRACTED,0,text.selectionStart,text.selectionEnd,text.startOffset,text.text==null?0:text.text.length());originalDelegate.updateExtractedText(s,request,text);record(EXTRACTED,1,text.selectionStart,text.selectionEnd,text.startOffset,text.text==null?0:text.text.length());}
        @Override public void updateCursorAnchorInfo(GeckoSession s,CursorAnchorInfo info){record(CURSOR,0,info.getSelectionStart(),info.getSelectionEnd(),info.getComposingTextStart(),info.getComposingText()==null?0:info.getComposingText().length());originalDelegate.updateCursorAnchorInfo(s,info);record(CURSOR,1,info.getSelectionStart(),info.getSelectionEnd(),info.getComposingTextStart(),info.getComposingText()==null?0:info.getComposingText().length());}
      };
      clientField.set(input,observedClient);input.setDelegate(observedDelegate);
      record(ATTACH,1,System.identityHashCode(session),0,0,0);
    }

    /** Install once on the original IC handler, after real focus has settled. */
    void prepareFocusedChild(Handler ui,Runnable ready)throws ReflectiveOperationException {
      if(childPreparationRequested)return;childPreparationRequested=true;
      postToIc.invoke(editable,(Runnable)()->{
        try{
          originalChild=childField.get(editable);
          if(originalChild==null)throw new IllegalStateException("Settled SDK input has no focused child");
          observedChild=Proxy.newProxyInstance(childField.getType().getClassLoader(),new Class<?>[]{childField.getType()},(proxy,method,args)->{
            String name=method.getName();int code="onImeUpdateComposition".equals(name)?CHILD_COMPOSITION:"onImeReplaceText".equals(name)?CHILD_REPLACE:
              "onImeSynchronize".equals(name)?CHILD_SYNC:"onKeyEvent".equals(name)?CHILD_KEY:"onImeRequestCommit".equals(name)?CHILD_COMMIT:-1;
            int first=0,second=0,third=0,fourth=0;
            if(code==CHILD_COMPOSITION){first=(Integer)args[0];second=(Integer)args[1];third=(Integer)args[2];}
            else if(code==CHILD_REPLACE){first=(Integer)args[0];second=(Integer)args[1];third=args[2]==null?0:((String)args[2]).length();fourth=third==1?((String)args[2]).charAt(0):0;}
            else if(code==CHILD_KEY){first=(Integer)args[0];second=(Integer)args[1];third=(Integer)args[6];fourth=((Boolean)args[9]?1:0)|((Boolean)args[10]?2:0);}
            if(code>=0)record(code,0,first,second,third,fourth);
            Object result;try{result=method.invoke(originalChild,args);}catch(InvocationTargetException failure){throw failure.getCause();}
            if(code>=0)record(code,1,first,second,third,fourth);
            return result;
          });
          childField.set(editable,observedChild);childAttached=true;
          record(CHILD_ATTACHED,1,System.identityHashCode(originalChild),0,0,0);
        }catch(ReflectiveOperationException|RuntimeException failure){childError=failure.toString();}
        ui.post(ready);
      });
    }

    void record(int code,int edge,int first,int second,int third,int fourth){
      if(!active)return;int n=reserved.getAndIncrement();if(n>=LIMIT)return;
      api[n]=code;phase[n]=edge;a[n]=first;b[n]=second;c[n]=third;d[n]=fourth;
      uptime[n]=SystemClock.uptimeMillis();threads[n]=Thread.currentThread().getId();published.set(n,1);
    }

    void stopAndFlush(Handler ui,LogSink sink,Runnable done){
      if(!active)return;active=false;
      try{
        postToIc.invoke(editable,(Runnable)()->{
          try{if(observedChild!=null&&childField.get(editable)==observedChild)childField.set(editable,originalChild);}
          catch(IllegalAccessException|RuntimeException failure){childError=failure.toString();}
          ui.post(()->flush(sink,done));
        });
      }catch(ReflectiveOperationException|RuntimeException failure){childError=failure.toString();flush(sink,done);}
    }

    void flush(LogSink sink,Runnable done){
      String restoreError="";
      try{if(clientField.get(input)==observedClient)clientField.set(input,originalClient);if(input.getDelegate()==observedDelegate)input.setDelegate(originalDelegate);}
      catch(IllegalAccessException|RuntimeException failure){restoreError=failure.toString();}
      int count=Math.min(reserved.get(),LIMIT),written=0;
      for(int n=0;n<count;n++)if(published.get(n)==1){
        sink.record(J.obj("id","current-input","seq",n,"mode","buffered-primitives","api",APIS[api[n]],"phase",phase[n]==0?"begin":"end",
          "uptimeMillis",uptime[n],"elapsedRealtime",baseElapsed+uptime[n]-baseUptime,"wallTimeMillis",baseWall+uptime[n]-baseUptime,
          "threadId",threads[n],"arg0",a[n],"arg1",b[n],"arg2",c[n],"arg3",d[n]));written++;
      }
      sink.record(J.obj("id","current-input","seq",LIMIT,"mode","buffered-primitives","api","trace.bufferedSummary",
        "capacity",LIMIT,"reserved",reserved.get(),"published",written,"overflow",reserved.get()>LIMIT,"restoreError",restoreError,
        "focusedChildAttached",childAttached,"focusedChildError",childError,
        "argContract","selection=start,end,compositionStart,compositionEnd; text=length,cursor; childComposition=start,end,flags; childReplace=start,end,length,singleCharCode; childKey=action,keyCode,domPrintableKeyValue,(synthesized?1:0)|(waitingReply?2:0); create=start,end,inputType,available; no full text content"));
      if(done!=null)done.run();
    }

    final class Connection extends InputConnectionWrapper {
      Connection(InputConnection target){super(target,false);}
      @Override public Handler getHandler(){return super.getHandler();}
      @Override public boolean setSelection(int start,int end){record(SET_SELECTION,0,start,end,0,0);boolean result=super.setSelection(start,end);record(SET_SELECTION,1,start,end,result?1:0,0);return result;}
      @Override public boolean commitText(CharSequence text,int cursor){record(COMMIT,0,text==null?0:text.length(),cursor,0,0);boolean result=super.commitText(text,cursor);record(COMMIT,1,text==null?0:text.length(),cursor,result?1:0,0);return result;}
      @Override public boolean commitText(CharSequence text,int cursor,android.view.inputmethod.TextAttribute attribute){record(COMMIT_ATTRIBUTE,0,text==null?0:text.length(),cursor,0,0);boolean result=super.commitText(text,cursor,attribute);record(COMMIT_ATTRIBUTE,1,text==null?0:text.length(),cursor,result?1:0,0);return result;}
      @Override public boolean setComposingText(CharSequence text,int cursor){record(COMPOSING,0,text==null?0:text.length(),cursor,0,0);boolean result=super.setComposingText(text,cursor);record(COMPOSING,1,text==null?0:text.length(),cursor,result?1:0,0);return result;}
      @Override public boolean setComposingText(CharSequence text,int cursor,android.view.inputmethod.TextAttribute attribute){record(COMPOSING_ATTRIBUTE,0,text==null?0:text.length(),cursor,0,0);boolean result=super.setComposingText(text,cursor,attribute);record(COMPOSING_ATTRIBUTE,1,text==null?0:text.length(),cursor,result?1:0,0);return result;}
      @Override public boolean setComposingRegion(int start,int end){record(REGION,0,start,end,0,0);boolean result=super.setComposingRegion(start,end);record(REGION,1,start,end,result?1:0,0);return result;}
      @Override public boolean setComposingRegion(int start,int end,android.view.inputmethod.TextAttribute attribute){record(REGION_ATTRIBUTE,0,start,end,0,0);boolean result=super.setComposingRegion(start,end,attribute);record(REGION_ATTRIBUTE,1,start,end,result?1:0,0);return result;}
      @Override public boolean replaceText(int start,int end,CharSequence text,int cursor,android.view.inputmethod.TextAttribute attribute){record(REPLACE,0,start,end,text==null?0:text.length(),cursor);boolean result=super.replaceText(start,end,text,cursor,attribute);record(REPLACE,1,start,end,text==null?0:text.length(),cursor);return result;}
      @Override public boolean finishComposingText(){record(FINISH,0,0,0,0,0);boolean result=super.finishComposingText();record(FINISH,1,result?1:0,0,0,0);return result;}
      @Override public boolean deleteSurroundingText(int before,int after){record(DELETE,0,before,after,0,0);boolean result=super.deleteSurroundingText(before,after);record(DELETE,1,before,after,result?1:0,0);return result;}
      @Override public boolean deleteSurroundingTextInCodePoints(int before,int after){record(DELETE_CODEPOINTS,0,before,after,0,0);boolean result=super.deleteSurroundingTextInCodePoints(before,after);record(DELETE_CODEPOINTS,1,before,after,result?1:0,0);return result;}
      @Override public boolean beginBatchEdit(){record(BATCH_BEGIN,0,0,0,0,0);boolean result=super.beginBatchEdit();record(BATCH_BEGIN,1,result?1:0,0,0,0);return result;}
      @Override public boolean endBatchEdit(){record(BATCH_END,0,0,0,0,0);boolean result=super.endBatchEdit();record(BATCH_END,1,result?1:0,0,0,0);return result;}
      @Override public boolean sendKeyEvent(android.view.KeyEvent event){record(KEY,0,event.getAction(),event.getKeyCode(),event.getFlags(),0);boolean result=super.sendKeyEvent(event);record(KEY,1,event.getAction(),event.getKeyCode(),result?1:0,0);return result;}
      @Override public CharSequence getTextBeforeCursor(int length,int flags){record(BEFORE_CURSOR,0,length,flags,0,0);CharSequence result=super.getTextBeforeCursor(length,flags);record(BEFORE_CURSOR,1,length,flags,result==null?-1:result.length(),0);return result;}
      @Override public CharSequence getTextAfterCursor(int length,int flags){record(AFTER_CURSOR,0,length,flags,0,0);CharSequence result=super.getTextAfterCursor(length,flags);record(AFTER_CURSOR,1,length,flags,result==null?-1:result.length(),0);return result;}
      @Override public CharSequence getSelectedText(int flags){record(SELECTED,0,flags,0,0,0);CharSequence result=super.getSelectedText(flags);record(SELECTED,1,flags,0,result==null?-1:result.length(),0);return result;}
      @Override public android.view.inputmethod.SurroundingText getSurroundingText(int before,int after,int flags){record(SURROUNDING,0,before,after,flags,0);android.view.inputmethod.SurroundingText result=super.getSurroundingText(before,after,flags);record(SURROUNDING,1,result==null?-1:result.getSelectionStart(),result==null?-1:result.getSelectionEnd(),result==null?-1:result.getOffset(),result==null||result.getText()==null?0:result.getText().length());return result;}
      @Override public ExtractedText getExtractedText(ExtractedTextRequest request,int flags){record(GET_EXTRACTED,0,request==null?-1:request.token,flags,0,0);ExtractedText result=super.getExtractedText(request,flags);record(GET_EXTRACTED,1,result==null?-1:result.selectionStart,result==null?-1:result.selectionEnd,result==null?-1:result.startOffset,result==null||result.text==null?0:result.text.length());return result;}
    }
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
