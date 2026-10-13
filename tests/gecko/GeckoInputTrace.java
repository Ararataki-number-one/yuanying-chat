package local.pocketchat;

import android.content.Context;
import android.os.Handler;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.CursorAnchorInfo;
import android.view.inputmethod.ExtractedText;
import android.view.inputmethod.ExtractedTextRequest;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicIntegerArray;
import org.json.JSONObject;
import org.json.JSONArray;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.SessionTextInput;
import org.mozilla.geckoview.GeckoView;

/** Optional public delegate tracing, plus independent native-only snapshots after the burst. */
final class GeckoInputTrace {
  interface LogSink {void record(JSONObject event);}
  static final String NATIVE_PREFIX="gecko-native-ime.log",NATIVE_SNAPSHOT="gecko-native-ime-snapshot.log",NATIVE_METADATA="gecko-native-ime-snapshot.json";
  static final String LOG_MODULES="timestamp,IMEStateManager:3,IMEContentObserver:4";
  static final String VIEW_SNAPSHOT="gecko-view-input-snapshot.json";
  final Buffered buffered;final LogSink sink;
  private GeckoInputTrace(GeckoSession session,LogSink value){buffered=new Buffered(session);sink=value;}
  static GeckoInputTrace attach(GeckoSession session,LogSink sink){return new GeckoInputTrace(session,sink);}
  void stop(){buffered.stopAndFlush(null,sink,null);}

  /** Created once through the original surface factory, only for the synthetic opt-in. */
  static final class KeyView extends GeckoView {
    volatile ViewKeys keys;
    KeyView(Context context){super(context);if(!"local.pocketchat.test".equals(context.getPackageName()))throw new SecurityException("Synthetic view diagnostic only");}
    @Override public boolean onKeyDown(int code,KeyEvent event){
      ViewKeys trace=keys;if(trace==null)return super.onKeyDown(code,event);int slot=trace.begin(1,code,event);boolean result=false,returned=false;
      try{result=super.onKeyDown(code,event);returned=true;return result;}finally{trace.end(slot,result?1:0,returned,null,0);}
    }
    @Override public boolean onKeyUp(int code,KeyEvent event){
      ViewKeys trace=keys;if(trace==null)return super.onKeyUp(code,event);int slot=trace.begin(2,code,event);boolean result=false,returned=false;
      try{result=super.onKeyUp(code,event);returned=true;return result;}finally{trace.end(slot,result?1:0,returned,null,0);}
    }
    @Override public InputConnection onCreateInputConnection(EditorInfo attrs){
      ViewKeys trace=keys;if(trace==null)return super.onCreateInputConnection(attrs);int slot=trace.begin(3,0,null);InputConnection result=null;boolean returned=false;
      try{result=super.onCreateInputConnection(attrs);returned=true;return result;}finally{trace.end(slot,result==null?0:1,returned,attrs,result==null?0:System.identityHashCode(result));}
    }
  }
  static final class ViewKeys {
    static final int LIMIT=256;
    final int[] api=new int[LIMIT],code=new int[LIMIT],action=new int[LIMIT],repeat=new int[LIMIT],meta=new int[LIMIT],flags=new int[LIMIT],source=new int[LIMIT],device=new int[LIMIT],scan=new int[LIMIT],result=new int[LIMIT],icIdentity=new int[LIMIT],inputType=new int[LIMIT],imeOptions=new int[LIMIT],selectionStart=new int[LIMIT],selectionEnd=new int[LIMIT];
    final long[] entered=new long[LIMIT],exited=new long[LIMIT],eventTime=new long[LIMIT],downTime=new long[LIMIT],thread=new long[LIMIT];
    final AtomicInteger reserved=new AtomicInteger();final AtomicIntegerArray published=new AtomicIntegerArray(LIMIT);
    final int viewIdentity,nativeSession;final String target;final long navigationEpoch,armed=SystemClock.uptimeMillis();volatile boolean active=true;
    ViewKeys(KeyView view,GeckoSession sdk,String url,long epoch){viewIdentity=System.identityHashCode(view);nativeSession=System.identityHashCode(sdk);target=url;navigationEpoch=epoch;}
    int begin(int method,int keyCode,KeyEvent event){
      if(!active)return -1;int slot=reserved.getAndIncrement();if(slot>=LIMIT)return -1;
      api[slot]=method;code[slot]=keyCode;entered[slot]=SystemClock.uptimeMillis();thread[slot]=Thread.currentThread().getId();
      if(event!=null){action[slot]=event.getAction();repeat[slot]=event.getRepeatCount();meta[slot]=event.getMetaState();flags[slot]=event.getFlags();source[slot]=event.getSource();device[slot]=event.getDeviceId();scan[slot]=event.getScanCode();eventTime[slot]=event.getEventTime();downTime[slot]=event.getDownTime();}return slot;
    }
    void end(int slot,int value,boolean returned,EditorInfo attrs,int identity){
      if(slot<0)return;result[slot]=returned?value:-1;exited[slot]=SystemClock.uptimeMillis();icIdentity[slot]=identity;
      if(attrs!=null){inputType[slot]=attrs.inputType;imeOptions[slot]=attrs.imeOptions;selectionStart[slot]=attrs.initialSelStart;selectionEnd[slot]=attrs.initialSelEnd;}published.set(slot,1);
    }
    JSONObject snapshot(){
      JSONArray events=new JSONArray();int count=Math.min(reserved.get(),LIMIT);
      for(int slot=0;slot<count;slot++)if(published.get(slot)==1)events.put(J.obj("sequence",slot,"api",api[slot]==1?"view.onKeyDown":api[slot]==2?"view.onKeyUp":"view.onCreateInputConnection","keyCode",code[slot],"action",action[slot],"repeat",repeat[slot],"metaState",meta[slot],"flags",flags[slot],"source",source[slot],"deviceId",device[slot],"scanCode",scan[slot],"eventTime",eventTime[slot],"downTime",downTime[slot],"enteredUptime",entered[slot],"returnedUptime",exited[slot],"threadId",thread[slot],"originalSuperReturned",result[slot]>=0,"superReturnValue",result[slot]>0,"originalInputConnectionIdentity",icIdentity[slot],"inputType",inputType[slot],"imeOptions",imeOptions[slot],"initialSelStart",selectionStart[slot],"initialSelEnd",selectionEnd[slot]));
      return J.obj("capacity",LIMIT,"reserved",reserved.get(),"published",events.length(),"incomplete",Math.min(reserved.get(),LIMIT)-events.length(),"overflow",reserved.get()>LIMIT,"armedUptime",armed,"stoppedUptime",SystemClock.uptimeMillis(),"viewIdentity",viewIdentity,"nativeSession",nativeSession,"target",target,"navigationEpoch",navigationEpoch,"events",events);
    }
  }
  static void snapshotView(Context context,ViewKeys keys,String source,String run,int currentView,int currentSession,String currentUrl,long currentEpoch,Handler ui,LogSink sink,Runnable done){
    if(keys!=null)keys.active=false;
    new Thread(()->{
      JSONObject value=J.obj("schema",1,"sourceCommit",source,"runNonce",run,"diagnosticOnly",true,"releaseAcceptance",false,"mode","original-super-view-keys","nativeLoggingEnabled",false,"publicDelegateReplaced",false,"inputConnectionWrapped",false,"inputConnectionClientReplaced",false,"editableListenerReplaced",false,"focusedChildReplaced",false,"originalInputConnectionMethodsCalledByObserver",0,"sdkInputHandlerObserved",false,"currentViewIdentity",currentView,"currentNativeSession",currentSession,"currentUrl",currentUrl,"currentNavigationEpoch",currentEpoch,"sourceBinding","Checked-out source supplied by runner; installed APK bytes independently matched to that CI build; no embedded source stamp claim");
      try{
        if(keys==null)throw new IllegalStateException("View input ring was never armed");value.put("buffer",keys.snapshot());
        android.content.pm.PackageInfo info=context.getPackageManager().getPackageInfo(context.getPackageName(),android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES);
        File apk=new File(context.getApplicationInfo().sourceDir);MessageDigest digest=MessageDigest.getInstance("SHA-256");long bytes=0;
        try(InputStream input=new FileInputStream(apk)){byte[] block=new byte[65536];int count;while((count=input.read(block))!=-1){digest.update(block,0,count);bytes+=count;}}
        JSONArray signers=new JSONArray();if(info.signingInfo!=null)for(android.content.pm.Signature signer:info.signingInfo.getApkContentsSigners())signers.put(sha256(signer.toByteArray()));
        value.put("installedApk",J.obj("package",context.getPackageName(),"version",info.versionName,"versionCode",info.getLongVersionCode(),"bytes",bytes,"sha256",hex(digest.digest()),"signerSha256",signers,"readOnWorker",true));value.put("status","captured");
      }catch(Throwable error){reportPut(value,"status","failed");reportPut(value,"error",String.valueOf(error));}
      try{atomic(context.getFilesDir(),VIEW_SNAPSHOT,value.toString().getBytes(StandardCharsets.UTF_8));}catch(Throwable error){reportPut(value,"exportError",String.valueOf(error));}
      JSONObject notice=J.obj("sourceCommit",source,"runNonce",run,"status",value.optString("status"),"reserved",keys==null?0:keys.reserved.get(),"overflow",keys!=null&&keys.reserved.get()>ViewKeys.LIMIT);
      ui.post(()->{sink.record(J.obj("id","current-input","seq",1026,"mode","original-super-view-keys","api","trace.viewSnapshot","metadata",notice));if(done!=null)done.run();});
    },"view-input-postburst-snapshot").start();
  }

  static final class Buffered {
    static final int LIMIT=1024;
    static final String[] APIS={"trace.attached","delegate.restartInput","delegate.showSoftInput","delegate.hideSoftInput","delegate.updateSelection","delegate.updateExtractedText","delegate.updateCursorAnchorInfo"};
    final int[] api=new int[LIMIT],phase=new int[LIMIT],a=new int[LIMIT],b=new int[LIMIT],c=new int[LIMIT],d=new int[LIMIT];
    final long[] uptime=new long[LIMIT],threads=new long[LIMIT];
    final AtomicInteger reserved=new AtomicInteger();final AtomicIntegerArray published=new AtomicIntegerArray(LIMIT);
    final SessionTextInput input;final GeckoSession.TextInputDelegate originalDelegate,observedDelegate;
    final long baseUptime=SystemClock.uptimeMillis(),baseElapsed=SystemClock.elapsedRealtime(),baseWall=System.currentTimeMillis();
    volatile boolean active=true;
    Buffered(GeckoSession session){
      input=session.getTextInput();originalDelegate=input.getDelegate();
      observedDelegate=new GeckoSession.TextInputDelegate(){
        @Override public void restartInput(GeckoSession s,int reason){record(1,0,reason,0,0,0);try{originalDelegate.restartInput(s,reason);}finally{record(1,1,reason,0,0,0);}}
        @Override public void showSoftInput(GeckoSession s){record(2,0,0,0,0,0);try{originalDelegate.showSoftInput(s);}finally{record(2,1,0,0,0,0);}}
        @Override public void hideSoftInput(GeckoSession s){record(3,0,0,0,0,0);try{originalDelegate.hideSoftInput(s);}finally{record(3,1,0,0,0,0);}}
        @Override public void updateSelection(GeckoSession s,int start,int end,int cs,int ce){record(4,0,start,end,cs,ce);try{originalDelegate.updateSelection(s,start,end,cs,ce);}finally{record(4,1,start,end,cs,ce);}}
        @Override public void updateExtractedText(GeckoSession s,ExtractedTextRequest request,ExtractedText text){record(5,0,text.selectionStart,text.selectionEnd,text.startOffset,text.text==null?0:text.text.length());try{originalDelegate.updateExtractedText(s,request,text);}finally{record(5,1,text.selectionStart,text.selectionEnd,text.startOffset,text.text==null?0:text.text.length());}}
        @Override public void updateCursorAnchorInfo(GeckoSession s,CursorAnchorInfo info){record(6,0,info.getSelectionStart(),info.getSelectionEnd(),info.getComposingTextStart(),info.getComposingText()==null?0:info.getComposingText().length());try{originalDelegate.updateCursorAnchorInfo(s,info);}finally{record(6,1,info.getSelectionStart(),info.getSelectionEnd(),info.getComposingTextStart(),info.getComposingText()==null?0:info.getComposingText().length());}}
      };
      input.setDelegate(observedDelegate);record(0,1,System.identityHashCode(session),0,0,0);
    }
    void record(int code,int edge,int first,int second,int third,int fourth){
      if(!active)return;int n=reserved.getAndIncrement();if(n>=LIMIT)return;
      api[n]=code;phase[n]=edge;a[n]=first;b[n]=second;c[n]=third;d[n]=fourth;
      uptime[n]=SystemClock.uptimeMillis();threads[n]=Thread.currentThread().getId();published.set(n,1);
    }
    void stopAndFlush(Handler unused,LogSink sink,Runnable done){
      if(!active)return;active=false;String restoreError="";
      try{if(input.getDelegate()==observedDelegate)input.setDelegate(originalDelegate);else restoreError="Delegate ownership changed";}
      catch(RuntimeException error){restoreError=error.toString();}
      int count=Math.min(reserved.get(),LIMIT),written=0;
      for(int n=0;n<count;n++)if(published.get(n)==1){
        sink.record(J.obj("id","current-input","seq",n,"mode","public-delegate-primitives","api",APIS[api[n]],"phase",phase[n]==0?"begin":"end","uptimeMillis",uptime[n],"elapsedRealtime",baseElapsed+uptime[n]-baseUptime,"wallTimeMillis",baseWall+uptime[n]-baseUptime,"threadId",threads[n],"arg0",a[n],"arg1",b[n],"arg2",c[n],"arg3",d[n]));written++;
      }
      sink.record(J.obj("id","current-input","seq",LIMIT,"mode","public-delegate-primitives","api","trace.bufferedSummary","capacity",LIMIT,"reserved",reserved.get(),"published",written,"overflow",reserved.get()>LIMIT,"restoreError",restoreError,"inputConnectionWrapped",false,"inputConnectionClientReplaced",false,"editableListenerReplaced",false,"focusedChildReplaced",false,"direction","SDK public delegate to original Android IMM delegate; not incoming input writer","argContract","selection=start,end,compositionStart,compositionEnd; extracted=start,end,startOffset,textLength; cursor=start,end,compositionStart,compositionLength"));
      if(done!=null)done.run();
    }
  }

  /** After the input burst only: capture bounded raw native logs without changing the logger. */
  static void snapshotNative(Context context,String source,String run,Handler ui,LogSink sink,Runnable done){
    new Thread(()->{
      JSONObject metadata=J.obj("schema",1,"sourceCommit",source,"runNonce",run,"diagnosticOnly",true,"releaseAcceptance",false,"mode","native-log-only","modules",LOG_MODULES,"javaShadowLogging","Official stable Java LOGGING is nightly-gated; not enabled here","nativeLogsMayAffectTiming",true,"publicDelegateReplaced",false,"inputConnectionWrapped",false,"inputConnectionClientReplaced",false,"editableListenerReplaced",false,"focusedChildReplaced",false,"nativeLoggerStillRunning",true);
      try{
        File root=context.getFilesDir();File[] found=root.listFiles(file->file.isFile()&&!java.nio.file.Files.isSymbolicLink(file.toPath())&&file.getName().matches("gecko-native-ime\\.log(?:\\.child-[0-9]+)?(?:\\.moz_log)?(?:\\.[0-3])?"));
        if(found==null)throw new IOException("Native log directory unavailable");Arrays.sort(found,Comparator.comparingLong(File::lastModified).reversed());
        final int limit=1900*1024;ByteArrayOutputStream combined=new ByteArrayOutputStream();JSONArray files=new JSONArray();boolean limited=found.length>16;
        for(int index=0;index<Math.min(found.length,16);index++){
          File file=found[index];long original=file.length();int budget=Math.min(128*1024,limit-combined.size()-256);if(budget<=0){limited=true;break;}
          int bytes=(int)Math.min(original,budget);long offset=original-bytes;byte[] captured=new byte[bytes];
          try(RandomAccessFile input=new RandomAccessFile(file,"r")){input.seek(offset);input.readFully(captured);}
          byte[] heading=("\n=== "+file.getName()+" bytes "+offset+".."+original+" ===\n").getBytes(StandardCharsets.UTF_8);combined.write(heading);combined.write(captured);
          files.put(J.obj("name",file.getName(),"originalBytes",original,"capturedFrom",offset,"capturedBytes",bytes,"capturedSha256",sha256(captured),"changedDuringRead",file.length()!=original));limited|=offset>0;
        }
        byte[] captured=combined.toByteArray();atomic(root,NATIVE_SNAPSHOT,captured);
        metadata.put("status","captured");metadata.put("files",files);metadata.put("foundFiles",found.length);metadata.put("bytes",captured.length);metadata.put("sha256",sha256(captured));metadata.put("byteLimit",limit);metadata.put("truncated",limited);metadata.put("capturedAtWallTime",System.currentTimeMillis());
      }catch(Throwable error){reportPut(metadata,"status","failed");reportPut(metadata,"error",String.valueOf(error));}
      try{atomic(context.getFilesDir(),NATIVE_METADATA,metadata.toString().getBytes(StandardCharsets.UTF_8));}catch(Throwable error){reportPut(metadata,"exportError",String.valueOf(error));}
      // Keep the logcat notification below its per-line limit. The complete
      // metadata and every captured native byte remain in the fixed exports.
      JSONObject notice=J.obj("sourceCommit",source,"runNonce",run,"status",metadata.optString("status"),"bytes",metadata.optLong("bytes"),"sha256",metadata.optString("sha256"),"foundFiles",metadata.optInt("foundFiles"),"truncated",metadata.optBoolean("truncated"));
      ui.post(()->{sink.record(J.obj("id","current-input","seq",1025,"mode","native-log-only","api","trace.nativeLogSnapshot","metadata",notice));if(done!=null)done.run();});
    },"native-ime-log-snapshot").start();
  }
  static void atomic(File root,String name,byte[] bytes)throws IOException{File file=new File(root,name),temp=new File(root,name+".tmp");try(FileOutputStream out=new FileOutputStream(temp)){out.write(bytes);out.getFD().sync();}if(!temp.renameTo(file))throw new IOException("Native diagnostic publication failed");}
  static String sha256(byte[] bytes)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(bytes));}
  static String hex(byte[] bytes){StringBuilder result=new StringBuilder();for(byte value:bytes)result.append(String.format(Locale.ROOT,"%02x",value&255));return result.toString();}
  static void reportPut(JSONObject object,String key,Object value){try{object.put(key,value);}catch(org.json.JSONException error){throw new IllegalStateException(error);}}
}
