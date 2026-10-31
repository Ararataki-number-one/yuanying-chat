package local.pocketchat;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.net.VpnService;
import android.os.Binder;
import android.os.Bundle;
import android.os.Process;
import java.io.IOException;
import java.io.InputStream;
import org.json.JSONObject;

/** Integration-only same-process IPC for the existing non-forwarding TUN fixture. */
public final class QueuedChangesVpnProvider extends ContentProvider {
  final Object lock=new Object();String selectedRun="",selectedSource="",buildSource="";boolean startDispatched;
  @Override public boolean onCreate(){
    try{
      if(!"local.pocketchat.test".equals(getContext().getPackageName()))throw new SecurityException("Integration package only");
      try(InputStream in=getContext().getAssets().open("pocketchat-integration-build.json")){
        JSONObject stamp=new JSONObject(J.text(in,8192));buildSource=stamp.optString("sourceCommit");
        if(stamp.optInt("schema")!=1||stamp.optBoolean("dirtySource",true)||!buildSource.matches("[0-9a-f]{40}"))throw new IOException("Clean integration source required");
      }
      return true;
    }catch(Exception failure){throw new IllegalStateException("Queued VPN source stamp unavailable",failure);}
  }
  static void requireCaller(String actualPackage,int caller,int own){
    if(!"local.pocketchat.test".equals(actualPackage)||caller!=own)throw new SecurityException("Same integration UID required");
  }
  static void requireIdentity(String run,String source,String expected){
    if(run==null||!run.matches("[0-9a-f]{32}")||source==null||!source.matches("[0-9a-f]{40}")||!source.equals(expected))throw new SecurityException("Exact queued run and installed source required");
  }
  static boolean matches(JSONObject value,String run,String source,long generation){
    return value!=null&&run.equals(value.optString("runNonce"))&&source.equals(value.optString("sourceCommit"))&&integer(value.opt("generation"))&&value.optLong("generation")==generation&&generation>0;
  }
  static boolean integer(Object value){return value instanceof Long||value instanceof Integer;}
  static boolean mayStart(JSONObject value,String run,String source,long generation){
    return value!=null&&Boolean.FALSE.equals(value.opt("running"))&&integer(value.opt("generation"))&&value.optLong("generation")==generation&&generation>=0&&value.opt("runNonce") instanceof String&&value.opt("sourceCommit") instanceof String&&(value.optString("runNonce").isEmpty()&&value.optString("sourceCommit").isEmpty()||run.equals(value.optString("runNonce"))&&source.equals(value.optString("sourceCommit")));
  }
  @Override public Bundle call(String method,String arg,Bundle args){
    requireCaller(getContext().getPackageName(),Binder.getCallingUid(),Process.myUid());
    if(args==null)throw new SecurityException("Queued VPN arguments required");String run=args.getString("runNonce",""),source=args.getString("sourceCommit","");requireIdentity(run,source,buildSource);
    if(!"prepare".equals(method)&&!"state".equals(method)&&!"start".equals(method)&&!"stop".equals(method))throw new IllegalArgumentException("Unknown queued VPN fixture operation");
    synchronized(lock){
      if(selectedRun.isEmpty()){selectedRun=run;selectedSource=source;}
      if(!selectedRun.equals(run)||!selectedSource.equals(source))throw new SecurityException("Queued VPN provider owner changed");
      JSONObject state=NetworkProtectionFixtureVpnService.snapshot();
      if("prepare".equals(method))return response(state,VpnService.prepare(getContext())==null);
      if("state".equals(method))return response(state,VpnService.prepare(getContext())==null);
      if("start".equals(method)){
        if(startDispatched)throw new SecurityException("Queued VPN START already dispatched");
        Object token=args.get("generation");if(!(token instanceof Long)||!mayStart(state,run,source,((Long)token).longValue()))throw new SecurityException("Queued VPN START generation changed");
        if(VpnService.prepare(getContext())!=null)throw new SecurityException("Synthetic VPN consent is not prepared");
        startDispatched=true;getContext().startService(new Intent(getContext(),NetworkProtectionFixtureVpnService.class).setAction("START").putExtra("mode","full").putExtra("runNonce",run).putExtra("sourceCommit",source));
        return response(state,true);
      }
      if("stop".equals(method)){
        Object token=args.get("generation");if(!(token instanceof Long)||!matches(state,run,source,((Long)token).longValue()))throw new SecurityException("Refusing to stop another VPN owner or generation");
        boolean dispatched=state.optBoolean("running");if(dispatched)getContext().startService(new Intent(getContext(),NetworkProtectionFixtureVpnService.class).setAction("STOP").putExtra("runNonce",run).putExtra("sourceCommit",source).putExtra("generation",((Long)token).longValue()));
        Bundle receipt=response(state,VpnService.prepare(getContext())==null);JSONObject value=J.parse(receipt.getString("json"));
        try{value.put("stopDispatched",dispatched).put("stopGeneration",((Long)token).longValue());}catch(org.json.JSONException impossible){throw new IllegalStateException(impossible);}
        receipt.putString("json",value.toString());return receipt;
      }
      throw new IllegalArgumentException("Unknown queued VPN fixture operation");
    }
  }
  Bundle response(JSONObject state,boolean prepared){
    Bundle out=new Bundle();out.putString("json",J.obj("schema",1,"sameProcessServiceState",true,"providerPid",Process.myPid(),"installedSource",buildSource,"prepared",prepared,"state",state,"scope","Actual existing test-package TUN state from its own process; no public routing acceptance").toString());return out;
  }
  @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){throw new UnsupportedOperationException();}
  @Override public String getType(Uri uri){return "application/json";}
  @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
  @Override public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
  @Override public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}
