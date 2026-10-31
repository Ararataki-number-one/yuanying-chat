"""Real overview state and auxiliary session/delegates on declared JVM SDK doubles.

No rendering, socket routing, Android focus, or real Gecko background work is claimed.
"""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
HOST=ROOT/'tests/experience46-overview-host'
def member(source,needle):
 start=source.index(needle);opening=source.index('{',start);depth=0
 for at in range(opening,len(source)):
  if source[at]=='{':depth+=1
  elif source[at]=='}':
   depth-=1
   if depth==0:return source[start:at+1]
 raise ValueError('unclosed method')
class Overview46Test(unittest.TestCase):
 def test_actual_deadline_gate_and_auxiliary_lifecycle(self):
  java=Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
  javac=java.with_name('javac')
  self.assertTrue(java.is_file() and javac.is_file(),'JDK compiler required')
  browser=(PRODUCTION/'GeckoWebView.java').read_text()
  methods='\n'.join(member(browser,signature) for signature in ['  boolean hasExitIpPage()', '  boolean readingOwnerVisible()', '  String openExitIpPage(', '  boolean closeExitIpPage()'])
  sources=[PRODUCTION/'EnvironmentOverviewState.java',PRODUCTION/'EnvironmentOverviewInfo.java',PRODUCTION/'ExitIpPageSession.java',PRODUCTION/'GeckoWebView.java',HOST/'Overview46Host.java',HOST/'Stubs.java',Path(__file__)]
  before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
  with tempfile.TemporaryDirectory(prefix='overview46-host-') as directory:
   base=Path(directory)
   for relative,text in SDK.items():
    p=base/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   for name in ['EnvironmentOverviewState.java','EnvironmentOverviewInfo.java','ExitIpPageSession.java']:(base/name).write_bytes((PRODUCTION/name).read_bytes())
   for name in ['Overview46Host.java','Stubs.java']:(base/name).write_bytes((HOST/name).read_bytes())
   (base/'GeckoWebView.java').write_text(WEB.replace('/*ACTUAL*/',methods))
   result=subprocess.run([str(javac),'-encoding','UTF-8','-d',str(base),*map(str,base.rglob('*.java'))],capture_output=True,text=True,timeout=45)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   result=subprocess.run([str(java),'-cp',str(base),'local.pocketchat.Overview46Host'],capture_output=True,text=True,timeout=20)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   report=json.loads(result.stdout);self.assertGreaterEqual(report['passed'],70)
  self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
  report.update(sourceSha256=before,scope='Actual production overview state and auxiliary controller plus extracted real display open/close methods on synthetic Android/Gecko boundaries; no device/network acceptance.')
  output=os.environ.get('OVERVIEW46_REPORT')
  if output:Path(output).write_text(json.dumps(report,indent=2)+'\n')
WEB='''package local.pocketchat;
import java.util.*;import org.mozilla.geckoview.*;
class GeckoWebView {
 final ChatSession owner;GeckoSession current;GeckoRuntime runtime=new GeckoRuntime();Surface surface=new Surface();ExitIpPageSession exitIpPage;int exitIpTopInset;boolean desktop,destroyed,failed,browserPaused,originKnown;boolean ready=true,routePrepared=true;Object routePort=new Object();long identityPolicyRevision=4;float readingLayout=.8f;Map<GeckoSession,Object> ports=new IdentityHashMap<>();Map<GeckoSession,Float> viewportWidths=new IdentityHashMap<>();Protection nativeProtection=new Protection();GeckoSettings metadata=new GeckoSettings();
 interface ExitIpPageListener{void changed(String m);void closed();}
 GeckoWebView(ChatSession s){owner=s;s.web=this;current=new GeckoSession(new GeckoSessionSettings.Builder().build());current.open(runtime);current.setActive(true);surface.setSession(current);ports.put(current,new Object());}
 boolean hasVisibleDocument(){return true;}String getUrl(){return "https://chatgpt.com/c/original";}GeckoSettings getSettings(){return metadata;}boolean protectionAllowsNetwork(){return nativeProtection.confirmed;}void cancelZoom(){}void requestLayout(){}int getWidth(){return 1080;}int getHeight(){return 1920;}static class MeasureSpec{static int EXACTLY=1;static int makeMeasureSpec(int size,int mode){return size;}}
 /*ACTUAL*/
 static class Surface{GeckoSession session;float scaleX=1,scaleY=1;GeckoSession getSession(){return session;}void setSession(GeckoSession s){session=s;}void releaseSession(){session=null;}void setScaleX(float f){scaleX=f;}void setScaleY(float f){scaleY=f;}void setPivotX(float f){}void setPivotY(float f){}int measuredWidth,measuredHeight;void measure(int w,int h){measuredWidth=w;measuredHeight=h;}void layout(int l,int t,int r,int b){}int getMeasuredWidth(){return measuredWidth;}int getMeasuredHeight(){return measuredHeight;}}
}'''
SDK={
 'android/text/TextUtils.java':'''package android.text;public class TextUtils{public static String join(String delimiter,Object[] values){return String.join(delimiter,java.util.Arrays.copyOf(values,values.length,String[].class));}}''',
 'android/net/Uri.java':'''package android.net;public class Uri {java.net.URI uri;Uri(String s){uri=java.net.URI.create(s);}public static Uri parse(String s){return new Uri(s);}public String getScheme(){return uri.getScheme();}public String getHost(){return uri.getHost();}public String getUserInfo(){return uri.getUserInfo();}public int getPort(){return uri.getPort();}}''',
 'org/json/JSONObject.java':'''package org.json;public class JSONObject {java.util.Map<String,Object> values=new java.util.HashMap<>();public JSONObject put(String k,Object v){values.put(k,v);return this;}public String optString(String k){Object v=values.get(k);return v instanceof String?(String)v:"";}public int optInt(String k,int fallback){Object v=values.get(k);return v instanceof Number?((Number)v).intValue():fallback;}public boolean optBoolean(String k){return Boolean.TRUE.equals(values.get(k));}public Object opt(String k){return values.get(k);}public JSONObject optJSONObject(String k){Object v=values.get(k);return v instanceof JSONObject?(JSONObject)v:null;}public long optLong(String k){Object v=values.get(k);return v instanceof Number?((Number)v).longValue():0;}public int length(){return values.size();}}''',
 'org/mozilla/geckoview/GeckoResult.java':'''package org.mozilla.geckoview;public class GeckoResult<T>{public T value;public static <T> GeckoResult<T> fromValue(T value){GeckoResult<T> r=new GeckoResult<>();r.value=value;return r;}}''',
 'org/mozilla/geckoview/GeckoRuntime.java':'package org.mozilla.geckoview;public class GeckoRuntime {}',
 'org/mozilla/geckoview/AllowOrDeny.java':'package org.mozilla.geckoview;public enum AllowOrDeny{ALLOW,DENY}',
 'org/mozilla/geckoview/WebRequestError.java':'package org.mozilla.geckoview;public class WebRequestError {}',
 'org/mozilla/geckoview/WebResponse.java':'package org.mozilla.geckoview;public class WebResponse {public java.io.InputStream body;}',
 'org/mozilla/geckoview/GeckoSessionSettings.java':'''package org.mozilla.geckoview;public class GeckoSessionSettings{public static int USER_AGENT_MODE_DESKTOP=1,USER_AGENT_MODE_MOBILE=0,VIEWPORT_MODE_MOBILE=0;public static class Builder{public Builder userAgentMode(int v){return this;}public Builder viewportMode(int v){return this;}public GeckoSessionSettings build(){return new GeckoSessionSettings();}}}''',
 'org/mozilla/geckoview/GeckoSession.java':'''package org.mozilla.geckoview;import java.util.*;public class GeckoSession {
 public boolean open,active;public int loads,tracking;public String lastUrl;public GeckoRuntime runtime;public NavigationDelegate navigation;public ProgressDelegate progress;public ContentDelegate content;
 public GeckoSession(GeckoSessionSettings s){}public void open(GeckoRuntime r){open=true;runtime=r;}public boolean isOpen(){return open;}public void setActive(boolean v){active=v;}public void loadUri(String url){loads++;lastUrl=url;}public void stop(){}public void close(){open=false;}
 public void setNavigationDelegate(NavigationDelegate d){navigation=d;}public void setProgressDelegate(ProgressDelegate d){progress=d;}public void setContentDelegate(ContentDelegate d){content=d;}public void setPromptDelegate(PromptDelegate d){}public void setPermissionDelegate(PermissionDelegate d){}
 public interface NavigationDelegate{public static class LoadRequest{public String uri;public LoadRequest(String u){uri=u;}}default GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest r){return null;}default void onLocationChange(GeckoSession s,String u,List<PermissionDelegate.ContentPermission> p,Boolean b){}default GeckoResult<GeckoSession> onNewSession(GeckoSession s,String u){return null;}default GeckoResult<String> onLoadError(GeckoSession s,String u,WebRequestError e){return null;}}
 public interface ProgressDelegate{default void onPageStop(GeckoSession s,boolean b){}}
 public interface ContentDelegate{default void onCloseRequest(GeckoSession s){}default void onCrash(GeckoSession s){}default void onKill(GeckoSession s){}default void onExternalResponse(GeckoSession s,WebResponse r){}}
 public interface PromptDelegate{class PromptResponse{}class FilePrompt{public PromptResponse dismiss(){return new PromptResponse();}}default GeckoResult<PromptResponse> onFilePrompt(GeckoSession s,FilePrompt p){return null;}}
 public interface PermissionDelegate{class ContentPermission{}class MediaSource{}interface Callback{void reject();}interface MediaCallback{void reject();}default GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission p){return null;}default void onAndroidPermissionsRequest(GeckoSession s,String[] p,Callback c){}default void onMediaPermissionRequest(GeckoSession s,String o,MediaSource[] v,MediaSource[] a,MediaCallback c){}}
}'''
}
if __name__=='__main__':unittest.main(verbosity=2)
