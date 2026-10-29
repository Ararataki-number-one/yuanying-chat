"""Compile the SDK-only fixture over declared edges and preserve the original pool workload.

No Android, native Gecko permission, gesture or TLS operation executes in this host test.
Actual SDK ABI compilation and the three one-shot device requests belong to Android CI.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PINS = {'tests/gecko/GeckoConnectionPoolIntegrationActivity.java': '53e80066191b479247b5db8e2031c5a884f8ccd31e91542796af1216fb95e331',
        'tests/gecko/run_gecko_pool.py': '9cbb16e206a3e271317881e0806003bb3c932f096a853aa841f0a49d58bcc59d'}
ACTIVITY = 'tests/gecko/GeckoConnectionPoolIntegrationActivity.java'
RUNNER = 'tests/gecko/run_gecko_pool.py'


def once(text, added, previous=''):
    if text.count(added) != 1:
        raise ValueError('Missing or repeated exact permission-fixture addition')
    return text.replace(added, previous, 1)


def original_activity(text):
    text = once(text, '  final GeckoSitePermissionFixture sitePermissions=new GeckoSitePermissionFixture(this);\n')
    text = once(text, '});sdk.setPermissionDelegate(test.sitePermissions.observe(sdk,sdk.getPermissionDelegate()));return sdk;', '});return sdk;')
    return once(text, '      NetworkCatalog.put(report,"sitePermissions",sitePermissions.evidence);sitePermissions.run();\n')


def original_runner(text):
    text = once(text, 'from gecko.site_permission_evidence import permission_tap_command, verify_site_permission_evidence\n')
    text = once(text, '        permission_gestures = []\n        permission_taps = {}\n')
    text = once(text, '''                        if value.get('kind') == 'permissionTapNeeded':
                            bounds = value['value']
                            key = (bounds.get('nonce'), bounds.get('stage'))
                            if key in permission_taps:
                                assert permission_taps[key] == bounds, 'Permission gesture changed after its one attempt'
                            else:
                                command = permission_tap_command(bounds, [row['stage'] for row in permission_gestures])
                                adb(*command)
                                permission_taps[key] = bounds
                                permission_gestures.append(dict(nonce=bounds['nonce'], stage=bounds['stage'], command=command,
                                                                bounds=bounds, oneAttempt=True))
''')
    text = once(text, "            report['sitePermissionsGestures'] = permission_gestures\n")
    return once(text, '''            permission_result = verify_site_permission_evidence(report['sitePermissions'], permission_gestures)
            (OUT / 'site-permission-sdk-results.json').write_text(json.dumps(dict(evidence=report['sitePermissions'], gestures=permission_gestures,
                                                                             verification=permission_result,
                                                                             sourceCommit=report['sourceCommit']), indent=2) + '\\n')
''')


APP = r'''
package local.pocketchat;
import org.json.*;import org.mozilla.geckoview.*;
class GeckoConnectionPoolIntegrationActivity {
  static final String ORIGIN="https://127.0.0.1:9877";View view;Owner session;
  interface Work<T>{T run()throws Exception;}
  <T>T ui(Work<T> work)throws Exception{return null;}
  JSONObject eval(String code)throws Exception{return null;}
  void event(String kind,JSONObject value){}
  void await(String name,Work<Boolean> condition,long limit)throws Exception{}
}
class View {GeckoSession current;GeckoRuntime runtime;Surface surface;String getUrl(){return null;}}
class Surface {void getLocationOnScreen(int[] value){}int getWidth(){return 0;}int getHeight(){return 0;}}
class Owner {android.os.Handler handler;}
class NetworkCatalog {static void put(JSONObject value,String key,Object item){}}
'''
SDK = r'''
package org.mozilla.geckoview;
public class GeckoSession {
  public boolean isOpen(){return false;}public Settings getSettings(){return null;}
  public static class Settings {public String getContextId(){return null;}public boolean getUsePrivateMode(){return false;}}
  public interface PermissionDelegate {
    int PERMISSION_DESKTOP_NOTIFICATION=1;
    class ContentPermission {
      public static final int VALUE_ALLOW=1,VALUE_DENY=2,VALUE_PROMPT=3;
      public String uri,thirdPartyOrigin,contextId;public boolean privateMode;public int permission,value;
    }
    interface Callback {}interface MediaCallback {}class MediaSource {}
    default void onAndroidPermissionsRequest(GeckoSession s,String[] names,Callback callback){}
    default void onMediaPermissionRequest(GeckoSession s,String origin,MediaSource[] video,MediaSource[] audio,MediaCallback callback){}
    default GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission permission){return null;}
  }
}
'''


PROBE = r'''
package local.pocketchat;
import org.json.*;import org.mozilla.geckoview.*;
final class NativeRequestScopeProbe {
  static int checks,writes;static Object dispatched;static int newValue;
  static void check(boolean value){if(!value)throw new AssertionError("scope check "+checks);checks++;}
  static class Test extends GeckoConnectionPoolIntegrationActivity {
    @Override <T>T ui(Work<T> work)throws Exception{return work.run();}
  }
  static GeckoSession.PermissionDelegate.ContentPermission permission(int value,String third){
    GeckoSession.PermissionDelegate.ContentPermission p=new GeckoSession.PermissionDelegate.ContentPermission();
    p.permission=1;p.value=value;p.uri=GeckoConnectionPoolIntegrationActivity.ORIGIN;p.thirdPartyOrigin=third;return p;
  }
  public static void main(String[] args)throws Exception {
    Test t=new Test();t.view=new View(){@Override String getUrl(){return GeckoConnectionPoolIntegrationActivity.ORIGIN+"/pool";}};
    GeckoSession session=new GeckoSession(){@Override public boolean isOpen(){return true;}};
    t.view.current=session;t.view.runtime=new GeckoRuntime(){@Override public StorageController getStorageController(){
      return new StorageController(){@Override public void setPermission(GeckoSession.PermissionDelegate.ContentPermission p,int value){writes++;dispatched=p;newValue=value;}};}};
    GeckoSitePermissionFixture f=new GeckoSitePermissionFixture(t);f.bound=session;f.context=null;f.privateMode=false;f.active=true;
    String origin=GeckoConnectionPoolIntegrationActivity.ORIGIN;
    GeckoSession.PermissionDelegate.ContentPermission live=permission(0,origin),stored=permission(2,null);
    check(f.requestKey(live));check(!f.storedKey(live));check(f.storedKey(stored));check(!f.requestKey(stored));
    check("native-request-unmapped".equals(GeckoSitePermissionFixture.requestValueSemantics(0)));
    check(!f.storedKey(permission(0,null)));check(!f.requestKey(permission(4,origin)));
    for(int value=1;value<=3;value++){check(f.storedKey(permission(value,null)));check(f.requestKey(permission(value,origin)));}
    for(String wrong:new String[]{null,"",origin+"/pool","https://other.test",new String(new char[2049]).replace('\0','x')}){
      check(!f.requestKey(permission(0,wrong)));
    }
    for(int axis=0;axis<4;axis++){
      GeckoSession.PermissionDelegate.ContentPermission p=permission(0,origin);
      if(axis==0)p.uri="https://other.test";if(axis==1)p.contextId="";if(axis==2)p.privateMode=true;if(axis==3)p.permission=3;
      check(!f.requestKey(p));
      p=permission(2,null);if(axis==0)p.uri="https://other.test";if(axis==1)p.contextId="";if(axis==2)p.privateMode=true;if(axis==3)p.permission=3;
      check(!f.storedKey(p));
    }
    check("null".equals(GeckoSitePermissionFixture.thirdPartyKind(null)));
    check("empty".equals(GeckoSitePermissionFixture.thirdPartyKind("")));
    check("other".equals(GeckoSitePermissionFixture.thirdPartyKind("https://other.test")));
    check("oversize".equals(GeckoSitePermissionFixture.thirdPartyKind(new String(new char[2049]))));
    check(GeckoSitePermissionFixture.thirdPartyDigest(new String(new char[2049]))==JSONObject.NULL);
    final int[] forwarded={0};
    GeckoSession.PermissionDelegate observed=f.observe(session,new GeckoSession.PermissionDelegate(){
      @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession s,ContentPermission p){forwarded[0]++;return null;}});
    observed.onContentPermissionRequest(new GeckoSession(),live);check(f.nativeCallbacks.isEmpty());
    observed.onContentPermissionRequest(session,live);check(f.nativeCallbacks.size()==1&&f.nativeCallbacks.get(0)==live&&forwarded[0]==2);
    JSONObject callback=f.callbacks.getJSONObject(0);check(callback.getInt("value")==0&&"native-request-unmapped".equals(callback.getString("valueSemantics")));
    check(origin.equals(callback.getString("thirdPartyOrigin"))&&callback.getInt("thirdPartyOriginLength")==origin.length());
    check("5d247053c598a4ab5ea02c4a6a4c367539a2e7861baf2240f003fe4d626c1ab4".equals(callback.getString("thirdPartyOriginSha256")));
    f.write("deny",live,2);check(writes==1&&dispatched==live&&newValue==2&&live.value==0&&origin.equals(live.thirdPartyOrigin));
    f.write("default",stored,3);check(writes==2&&dispatched==stored&&newValue==3&&stored.value==2&&stored.thirdPartyOrigin==null);
    for(int item=0;item<5;item++){
      try{if(item==0)f.write("deny",permission(0,"https://other.test"),2);
        if(item==1)f.write("deny",permission(0,origin),2);
        if(item==2)f.write("default",live,3);
        if(item==3)f.write("deny",live,1);
        if(item==4)f.write("default",stored,2);
        throw new IllegalStateException("unexpected dispatch");
      }catch(AssertionError expected){check(writes==2);}
    }
    observed.onContentPermissionRequest(session,permission(0,"https://other.test"));
    JSONObject foreign=f.callbacks.getJSONObject(1);check(foreign.isNull("thirdPartyOrigin")&&"other".equals(foreign.getString("thirdPartyOriginKind"))&&foreign.getString("thirdPartyOriginSha256").length()==64);
    check(f.mutations.getJSONObject(0).getInt("sourceValue")==0&&"native-request-unmapped".equals(f.mutations.getJSONObject(0).getString("sourceValueSemantics")));
    System.out.println(checks);
  }
}
'''


class SitePermissionFixtureTest(unittest.TestCase):
    def test_whole_original_activity_runner_and_all_old_budgets_inverse_exactly(self):
        for path, inverse in [(ACTIVITY, original_activity), (RUNNER, original_runner)]:
            current = (ROOT / path).read_text()
            self.assertEqual(hashlib.sha256(inverse(current).encode()).hexdigest(), PINS[path])
            modified = current.replace('240' if path == RUNNER else 'unsent pool draft', '999' if path == RUNNER else 'changed original draft', 1)
            self.assertNotEqual(hashlib.sha256(inverse(modified).encode()).hexdigest(), PINS[path])
        helper = (ROOT / 'tests/gecko/GeckoSitePermissionFixture.java').read_text()
        self.assertIn('return original.onContentPermissionRequest(s,permission);', helper)
        self.assertIn('original.onAndroidPermissionsRequest(s,names,callback);', helper)
        self.assertIn('original.onMediaPermissionRequest(s,origin,video,audio,callback);', helper)
        for forbidden in ['VALUE_ALLOW', 'fromJson(', 'clearData(', 'requestPermissions(', 'callback.grant(', 'permission.grant(']:
            self.assertNotIn(forbidden, helper)

    def test_fixture_compiles_with_real_android_classes_and_declared_gecko_edges(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK17+ required')
        configured = os.environ.get('PROFILE_ANDROID_JAR')
        sdk_root = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        choices = [Path(configured)] if configured else ([Path(sdk_root) / 'platforms' / version / 'android.jar'
                  for version in ('android-37.1', 'android-37', 'android-35')] if sdk_root else [])
        framework = next((path for path in choices if path.is_file()), None)
        self.assertIsNotNone(framework, 'A real Android framework JAR is required')
        jars = [Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar')),
                Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT / 'work/profile-host/android-json.jar'))]
        for jar in jars:
            self.assertTrue(jar.is_file(), 'JSON jar missing: ' + str(jar))
            with tempfile.TemporaryDirectory(prefix='site-permission-fixture-') as temporary:
                temp = Path(temporary);app = temp / 'BoundaryDoubles.java';app.write_text(APP)
                sdk = temp / 'GeckoSession.java';sdk.write_text(SDK)
                probe = temp / 'NativeRequestScopeProbe.java';probe.write_text(PROBE)
                production = ROOT / 'app/src/main/java/local/pocketchat'
                edges = ROOT / 'tests/site-permissions-ui-host/org/mozilla/geckoview'
                sources = [production / 'SitePermissions.java', production / 'J.java', ROOT / 'tests/gecko/GeckoSitePermissionFixture.java', app, sdk, probe]
                sources += [edges / (name + '.java') for name in ['StorageController', 'GeckoRuntime', 'GeckoResult']]
                run = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
                                      '-cp', os.pathsep.join((str(framework), str(jar))), '-d', str(temp / 'classes'), *map(str, sources)],
                                     capture_output=True, text=True, timeout=35)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                executed = subprocess.run([java, '-cp', os.pathsep.join((str(temp / 'classes'), str(jar), str(framework))),
                                           'local.pocketchat.NativeRequestScopeProbe'], capture_output=True, text=True, timeout=15)
                self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
                self.assertGreaterEqual(int(executed.stdout.strip()), 40)


if __name__ == '__main__':
    unittest.main()
