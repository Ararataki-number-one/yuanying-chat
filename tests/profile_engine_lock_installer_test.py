"""Verify production Chromium eligibility and owner-bound route code with host doubles."""
from pathlib import Path
import os
import runpy
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app/src/main/java/local/pocketchat'
member = runpy.run_path(str(ROOT / 'tests/default-environment-host/run.py'))['member']


class InstallerEngineLockTest(unittest.TestCase):
    def test_exact_route_identity_and_chromium_availability(self):
        ins = (APP / 'ChromiumModuleInstaller.java').read_text()
        rt = (APP / 'ChromiumModuleRoute.java').read_text()
        identity = member((APP / 'EnvironmentSpec.java').read_text(), 'static final class Identity')
        consts = '\n'.join(line.strip() for line in ins.splitlines() if line.strip().startswith((
            'private static final String SLOT =', 'private static final String GENERATION =',
            'private static final String ENVIRONMENT =')))
        methods = '\n'.join(member(ins, sig) for sig in ('static boolean selectableForNewEnvironment(',
            'static EnvironmentSpec.Identity requestedOwner(', 'static boolean ownerCurrent(',
            'static synchronized Operation begin('))
        script = r"""
import java.io.*;
import java.util.*;
import java.util.concurrent.Callable;
import java.util.function.BooleanSupplier;
public class EngineLockInstallerHost {
  static final String OLD="00000000-0000-0000-0000-000000000001", NEW="00000000-0000-0000-0000-000000000002";
  static int passed;
  static void check(boolean yes,String label){if(!yes)throw new AssertionError(label);passed++;}
  static final class JSONObject {}
  static final class EnvironmentSpec {
    static JSONObject object(Object... ignored){return new JSONObject();}
    /* identity */
  }
  static EnvironmentSpec.Identity id(int generation,String key){return new EnvironmentSpec.Identity(2,generation,key);}
  static final class Context {
    boolean supported=true, managed=true, downloaded, available=true, chromium=true, readable=true;
    EnvironmentSpec.Identity owner=id(3,OLD), replaceWhenSnapshot;
  }
  static final class Profiles {
    static Context context(Context context,int slot){return context;}
    static Context global(Context context){return context;}
  }
  static final class ProfileCatalog {
    final Context context;
    ProfileCatalog(Context context){this.context=context;}
    static ProfileCatalog get(Context context){return new ProfileCatalog(context);}
    EnvironmentSpec.Identity identity(int slot)throws IOException{
      if(!context.readable||context.owner.slot!=slot)throw new IOException();
      return context.owner;
    }
    <T>T withIdentity(EnvironmentSpec.Identity expected,Callable<T> read)throws Exception{
      if(context.replaceWhenSnapshot!=null)context.owner=context.replaceWhenSnapshot;
      if(!identity(expected.slot).equals(expected))throw new IOException("Owner changed under writer lease");
      return read.call();
    }
  }
  static final class BrowserPreferences { static boolean startBrowser(Context context){return context.chromium;} }
  static final class ChromiumEntry { static boolean managed(Context context){return context.managed;} }
  static final class Intent {
    final Map<String,Object> values=new HashMap<>();
    Intent putExtra(String key,Object value){values.put(key,value);return this;}
    int getIntExtra(String key,int fallback){Object value=values.get(key);return value instanceof Integer?(int)value:fallback;}
    String getStringExtra(String key){Object value=values.get(key);return value instanceof String?(String)value:null;}
  }
  static final class ChromiumModuleInstaller {
    /* constants */
    static boolean supported(Context context){return context.supported;}
    static boolean installed(Context context){return context.downloaded;}
    static boolean available(Context context){return context.available;}
    static Operation current;
    static final java.util.concurrent.Executor WORKER=ignored -> {};
    static final class Operation {
      final EnvironmentSpec.Identity expected;
      boolean done;
      Operation(Context unused,EnvironmentSpec.Identity expected){this.expected=expected;}
      void run(){}
    }
    /* installer */
  }
  static final class CefriumRoutePolicy { static final class Selection {} }
  static final class ChromiumModuleRoute {
    final EnvironmentSpec.Identity owner;
    static int snapshots,network;
    ChromiumModuleRoute(Context profile,EnvironmentSpec.Identity owner,CefriumRoutePolicy.Selection selected,BooleanSupplier stop){this.owner=owner;}
    static CefriumRoutePolicy.Selection selection(Context context){snapshots++;return new CefriumRoutePolicy.Selection();}
    static IOException unavailable(){return new IOException("owner changed");}
    void open()throws IOException{network++;}
    void close(){}
    /* route */
  }
  static boolean rejectRoute(Context c,EnvironmentSpec.Identity id,boolean cancelled){
    try{ChromiumModuleRoute.acquire(c,id,()->cancelled);return false;}
    catch(IOException expected){return true;}
  }
  public static void main(String[] args)throws Exception{
    Context c=new Context();
    check(ChromiumModuleInstaller.selectableForNewEnvironment(c),"Official optional delivery works before the split is present");
    c.available=false;
    check(!ChromiumModuleInstaller.selectableForNewEnvironment(c),"Without official deliverability or split, hide Chromium choice");
    c.downloaded=true;
    check(ChromiumModuleInstaller.selectableForNewEnvironment(c),"Matching installed split supports parallel package without downloader");
    c.managed=false;
    check(!ChromiumModuleInstaller.selectableForNewEnvironment(c),"No Android WebView substitute");
    c.managed=true; c.supported=false;
    check(!ChromiumModuleInstaller.selectableForNewEnvironment(c),"Unsupported API or ABI cannot be stranded");
    c.supported=true;
    Intent launch=new Intent().putExtra(ChromiumModuleInstaller.SLOT,2)
      .putExtra(ChromiumModuleInstaller.GENERATION,3).putExtra(ChromiumModuleInstaller.ENVIRONMENT,OLD);
    EnvironmentSpec.Identity expected=ChromiumModuleInstaller.requestedOwner(launch);
    check(c.owner.equals(expected),"Owner round-trips with slot, generation and UUID");
    check(ChromiumModuleInstaller.requestedOwner(new Intent().putExtra(ChromiumModuleInstaller.SLOT,2))==null,"No slot-only request");
    check(ChromiumModuleInstaller.begin(c,expected).expected.equals(expected),"Operation captures exact owner");
    check(ChromiumModuleRoute.acquire(c,expected,()->false).owner.equals(expected),"Route uses that same owner");
    for(EnvironmentSpec.Identity replacement:new EnvironmentSpec.Identity[]{id(4,OLD),id(3,NEW)}){
      c.owner=replacement;
      check(ChromiumModuleInstaller.begin(c,expected)==null,"Reused slot must not start, even if operation exists");
      check(rejectRoute(c,expected,false)&&ChromiumModuleRoute.snapshots==1&&ChromiumModuleRoute.network==1,
        "Stale owner no longer reads the slot or opens sockets");
    }
    c.owner=expected;c.replaceWhenSnapshot=id(4,NEW);
    check(rejectRoute(c,expected,false)&&ChromiumModuleRoute.snapshots==1&&ChromiumModuleRoute.network==1,
      "Replacement between precheck and writer lease cannot read the new route");
    c.replaceWhenSnapshot=null;c.owner=expected;c.chromium=false;
    check(ChromiumModuleInstaller.begin(c,expected)==null,"Firefox owner cannot consent to this Chromium route");
    c.chromium=true;c.readable=false;
    check(ChromiumModuleInstaller.begin(c,expected)==null,"Removed/unreadable owner fails closed");
    c.readable=true;
    check(rejectRoute(c,expected,true)&&ChromiumModuleRoute.snapshots==1&&ChromiumModuleRoute.network==1,
      "Cancellation does not open replacement work");
    System.out.println("passed="+passed);
  }
}
"""
        source = (script.replace('/* identity */', identity).replace('/* constants */', consts)
                  .replace('/* installer */', methods).replace('/* route */', member(rt, 'static ChromiumModuleRoute acquire(')))
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java)
        with tempfile.TemporaryDirectory(prefix='pocketchat-engine-installer-') as directory:
            file = Path(directory) / 'EngineLockInstallerHost.java'
            file.write_text(source, encoding='utf-8')
            result = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '17',
                                     '-encoding', 'UTF-8', str(file)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([java, '-cp', directory, 'EngineLockInstallerHost'],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), 'passed=17')

    def test_legacy_entries_and_mutation_boundaries(self):
        ui = (APP / 'BrowserSettingsUi.java').read_text()
        picker = member(ui, 'static Spinner creationPicker(')
        editor = member(ui, 'private static void show(')
        self.assertIn('selectableForNewEnvironment(activity)', picker)
        self.assertNotIn('new Spinner(', editor)
        self.assertIn('BrowserPreferences.saveHome(profile,address)', editor)
        self.assertIn('ChromiumModuleInstaller.show(activity,expected)', editor)
        # Login reset removes an allowlist of transient data, never the entire preference store.
        reset = member((APP / 'EnvironmentResetActivity.java').read_text(), 'private static void performReset(')
        self.assertNotIn('KEY_START', reset)
        self.assertNotIn('browserStartScreen', reset)
        self.assertNotIn('preferences.clear()', reset)
        # All app-side binding writes are in fresh reservation paths, not network import or runtime.
        owners = sorted(p.name for p in APP.glob('*.java') if 'EnvironmentEngine.stageNew(' in p.read_text())
        self.assertEqual(owners, ['EnvironmentConfigTransfer.java', 'Profiles.java'])


if __name__ == '__main__':
    unittest.main()
