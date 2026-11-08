"""Execute the exact test-only glass owner observer with mutation sentinels.

Android view/animation state is modeled here. These tests create no device,
HWUI-counter, visual, runtime, or release acceptance evidence.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/gecko/ChromeCollapseIntegration.java'
JSON_FIXTURE = ROOT / 'tests/persistent-runtime-path-host/json-20240303.jar.b64'
J_SOURCE = ROOT / 'app/src/main/java/local/pocketchat/J.java'
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def java_member(raw, needle):
    if raw.count(needle) != 1:
        raise ValueError('One complete actual Java member is required: ' + needle)
    start = raw.index(needle)
    opening = raw.index('{', start)
    depth, quote, escaped, comment = 0, None, False, None
    index = opening
    while index < len(raw):
        char, pair = raw[index], raw[index:index + 2]
        if comment == '//':
            if char == '\n':
                comment = None
        elif comment == '/*':
            if pair == '*/':
                comment = None;index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif pair in ('//', '/*'):
            comment = pair;index += 1
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return raw[start:index + 1]
        index += 1
    raise ValueError('Unclosed actual Java member: ' + needle)


def observer_source():
    return java_member(FIXTURE.read_text(), 'static final class GlassOwnerObservation')


def java_tools():
    selected = os.environ.get('PROFILE_JAVA')
    javac = Path(os.environ.get('PROFILE_JAVAC') or (Path(selected).with_name('javac') if selected else None)
                 or shutil.which('javac') or Path(os.environ.get('JAVA_HOME',
                 '/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64')) / 'bin/javac')
    java = Path(selected or javac.with_name('java'))
    if not java.is_file() or not javac.is_file():
        raise RuntimeError('Actual JDK java/javac required')
    return java, javac


def owner_model():
    """Keep the observed private declarations exactly as in production."""
    value = OWNERS
    for name, required, token in (
            ('LiquidGlassDrawable', {'animation', 'pressed', 'strength', 'bend'}, '@LIQUID_FIELDS@'),
            ('GlassDock', {'transition', 'opacity', 'flow'}, '@DOCK_FIELDS@'),
            ('GlassBackdrop', {'glassActive'}, '@BACKDROP_FIELDS@')):
        declarations, found = [], set()
        for line in (PRODUCTION / (name + '.java')).read_text().splitlines():
            match = re.fullmatch(r'\s*private\s+(ValueAnimator|boolean|float)\s+([^;]+);\s*', line)
            if not match:
                continue
            names = {member.split('=')[0].strip() for member in match[2].split(',')}
            relevant = names & required
            if relevant:
                if relevant & found:
                    raise ValueError('Duplicate actual observed field declaration')
                declarations.append(line);found.update(relevant)
        if found != required:
            raise ValueError('Actual observed owner fields changed: ' + name)
        value = value.replace(token, '\n'.join(declarations))
    value = value.replace('@BACKDROP_ACTIVE@', java_member(
        (PRODUCTION / 'GlassBackdrop.java').read_text(), 'boolean isGlassActive()'))
    return value


class GlassOwnerObservationTests(unittest.TestCase):
    observations = []

    def test_actual_observer_compiles_against_pinned_android35_api(self):
        selected = os.environ.get('PROFILE_ANDROID_JAR')
        sdk_candidates = tuple(Path(os.environ[key]) / 'platforms/android-35/android.jar'
                               for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT') if os.environ.get(key))
        candidates = (*sdk_candidates,
                      Path('/usr/local/lib/android/sdk/platforms/android-35/android.jar'),
                      Path('/tmp/pocketchat-shared-tools/android-35/android.jar'),
                      ROOT / 'work/cloud-setup/platform/android-35/android.jar',
                      Path('/workspace/yuanying-chat/work/cloud-setup/platform/android-35/android.jar'))
        android = Path(selected) if selected else next((path for path in candidates if path.is_file()), candidates[0])
        self.assertTrue(android.is_file(), 'Pinned Android35 API jar required')
        self.assertEqual(SHA(android.read_bytes()), '4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b')
        _, javac = java_tools()
        paths = (FIXTURE, J_SOURCE, Path(__file__),
                 *[PRODUCTION / (name + '.java') for name in ('LiquidGlassDrawable', 'GlassDock', 'GlassBackdrop')])
        before = {str(path.relative_to(ROOT)): SHA(path.read_bytes()) for path in paths}
        owners = owner_model()
        substitutions = (
            ('final class LiquidGlassDrawable extends Drawable {',
             'final class LiquidGlassDrawable extends Drawable {'
             'public void draw(android.graphics.Canvas canvas){throw new UnsupportedOperationException("compile-only owner");}'
             'public void setAlpha(int alpha){throw new UnsupportedOperationException("compile-only owner");}'
             'public void setColorFilter(android.graphics.ColorFilter filter){throw new UnsupportedOperationException("compile-only owner");}'
             'public int getOpacity(){throw new UnsupportedOperationException("compile-only owner");}'),
            ('final class GlassDock extends ViewGroup {', 'final class GlassDock extends android.widget.FrameLayout {'),
            ('GlassDock(ValueAnimator animator){', 'GlassDock(ValueAnimator animator){super((android.content.Context)null);'),
            ('final class GlassBackdrop extends ViewGroup {', 'final class GlassBackdrop extends android.widget.FrameLayout {'),
            ('GlassBackdrop(){', 'GlassBackdrop(){super((android.content.Context)null);'))
        for old, new in substitutions:
            self.assertEqual(owners.count(old), 1)
            owners = owners.replace(old, new, 1)
        with tempfile.TemporaryDirectory(prefix='glass-owner-android35-api-') as temporary:
            directory = Path(temporary)
            (directory / 'J.java').write_bytes(J_SOURCE.read_bytes())
            (directory / 'CompileOnlyOwners.java').write_text(owners)
            (directory / 'ChromeCollapseIntegration.java').write_text(
                'package local.pocketchat;import android.view.*;import android.animation.*;'
                'import android.graphics.drawable.*;import java.lang.reflect.*;import java.util.*;import org.json.*;'
                'final class ChromeCollapseIntegration {\n' + observer_source() + '\n}\n')
            result = subprocess.run([str(javac), '-encoding', 'UTF-8', '-cp', str(android), '-d', str(directory / 'classes'),
                                     *[str(path) for path in directory.glob('*.java')]],
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {name: SHA((ROOT / name).read_bytes()) for name in before})
        self.observations.append(dict(kind='actual-android-api-compile', api=35,
                                      androidJarSha256=SHA(android.read_bytes()), ownerStubsExecuted=False))

    def execute(self, mode, missing_field=False, mutation=None):
        java, javac = java_tools()
        before = {str(path.relative_to(ROOT)): SHA(path.read_bytes()) for path in
                  (FIXTURE, JSON_FIXTURE, J_SOURCE, Path(__file__),
                   *[PRODUCTION / (name + '.java') for name in ('LiquidGlassDrawable', 'GlassDock', 'GlassBackdrop')])}
        encoded = JSON_FIXTURE.read_bytes()
        self.assertEqual(SHA(encoded), '01e2506eba3d8bb475bfbb4a85714ec5b11f0abc841d45de516fe32ee8e30348')
        dependency = base64.b64decode(b''.join(encoded.splitlines()), validate=True)
        self.assertEqual(SHA(dependency), '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed')
        actual = observer_source()
        if mutation is not None:
            old, new = mutation
            self.assertEqual(actual.count(old), 1)
            actual = actual.replace(old, new, 1)
        with tempfile.TemporaryDirectory(prefix='glass-owner-readonly-') as temporary:
            directory = Path(temporary)
            jar = directory / 'json.jar';jar.write_bytes(dependency)
            for name, text in MODEL.items():
                path = directory / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(text)
            (directory / 'J.java').write_bytes(J_SOURCE.read_bytes())
            (directory / 'ChromeCollapseIntegration.java').write_text(
                'package local.pocketchat;import android.view.*;import android.animation.*;'
                'import android.graphics.drawable.*;import java.lang.reflect.*;import java.util.*;import org.json.*;'
                'final class ChromeCollapseIntegration {\n' + actual + '\n}\n')
            classes = owner_model()
            if missing_field:
                classes = classes.replace('strength', 'missingStrength')
            (directory / 'OwnerHost.java').write_text(classes + HOST)
            compiled = subprocess.run([str(javac), '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(directory / 'classes'),
                                       *[str(path) for path in directory.rglob('*.java')]],
                                      capture_output=True, text=True, timeout=45)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(java), '-cp', str(directory / 'classes') + os.pathsep + str(jar),
                                     'local.pocketchat.OwnerHost', mode], capture_output=True, text=True, timeout=15)
            if mutation is not None:
                self.assertNotEqual(result.returncode, 0, 'A state-changing observer mutant passed')
                self.assertIn('Observation attempted a state-changing call', result.stderr)
                value = dict(compiledMutationRejected=True)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
        self.assertEqual(before, {name: SHA((ROOT / name).read_bytes()) for name in before})
        if mutation is None:
            self.assertEqual(value['mutationCalls'], 0)
            self.assertTrue(value['stateUnchanged'])
        return value

    def test_hidden_ancestor_does_not_hide_running_material_or_dock_from_observer(self):
        value = self.execute('hidden')
        observed = value['observation']
        self.assertEqual(len(observed['materials']), 1)
        self.assertEqual(len(observed['docks']), 1)
        material, dock = observed['materials'][0], observed['docks'][0]
        self.assertEqual(material['host']['visibility'], 0)
        self.assertFalse(material['host']['shown'])
        self.assertTrue(material['animation']['present'])
        self.assertTrue(material['animation']['started'])
        self.assertTrue(material['animation']['running'])
        self.assertTrue(dock['transition']['running'])
        self.assertFalse(dock['host']['shown'])
        self.assertFalse(observed['backdrop']['isGlassActive'])
        self.observations.append(dict(kind='hidden-active-owner-preserved', status='passed'))

    def test_layer_and_inset_material_fields_are_reported_without_touching_drawable_state(self):
        value = self.execute('visible')
        observed = value['observation']
        self.assertTrue(observed['materials'][0]['host']['shown'])
        self.assertEqual(observed['materials'][0]['drawableState'], [16842910, 16842919])
        self.assertEqual(observed['materials'][0]['drawableAlpha'], 213)
        self.assertEqual(observed['materials'][0]['animation']['durationMillis'], 480)
        self.assertEqual(observed['materials'][0]['animation']['currentPlayTimeMillis'], 73)
        self.assertTrue(observed['materials'][0]['pressed'])
        self.assertAlmostEqual(observed['materials'][0]['strength'], .4, places=5)
        self.assertAlmostEqual(observed['materials'][0]['bend'], .3, places=5)
        self.assertTrue(observed['backdrop']['configuredActive'])
        self.assertTrue(observed['backdrop']['isGlassActive'])
        self.observations.append(dict(kind='layer-inset-visible-owner-read', status='passed'))

    def test_stopped_and_absent_animation_states_remain_distinct(self):
        stopped = self.execute('stopped')['observation']
        self.assertTrue(stopped['materials'][0]['animation']['present'])
        self.assertFalse(stopped['materials'][0]['animation']['running'])
        self.assertFalse(stopped['materials'][0]['animation']['started'])
        absent = self.execute('absent')['observation']
        self.assertFalse(absent['materials'][0]['animation']['present'])
        self.assertFalse(absent['docks'][0]['transition']['present'])
        scheduled = self.execute('scheduled')['observation']
        self.assertTrue(scheduled['materials'][0]['animation']['started'])
        self.assertFalse(scheduled['materials'][0]['animation']['running'])
        self.observations.append(dict(kind='stopped-versus-absent-owner-state', status='passed'))

    def test_visibility_restore_reports_current_state_without_cancelling_live_animation(self):
        value = self.execute('restore')
        before, after = value['previousObservation'], value['observation']
        self.assertFalse(before['materials'][0]['host']['shown'])
        self.assertTrue(after['materials'][0]['host']['shown'])
        self.assertEqual(before['materials'][0]['drawableIdentity'], after['materials'][0]['drawableIdentity'])
        self.assertEqual(before['materials'][0]['animation'], after['materials'][0]['animation'])
        self.assertTrue(after['materials'][0]['animation']['running'])
        self.assertFalse(before['backdrop']['isGlassActive'])
        self.assertTrue(after['backdrop']['isGlassActive'])
        self.observations.append(dict(kind='same-owner-visibility-restored-without-mutation', status='passed'))

    def test_missing_current_native_roots_are_rejected(self):
        for mode in ('null-toolbar', 'null-bar', 'null-panel'):
            with self.subTest(root=mode):
                value = self.execute(mode)
                self.assertEqual(value['errorClass'], 'java.lang.IllegalStateException')
                self.assertNotIn('observation', value)
        self.observations.append(dict(kind='missing-current-roots-fail-closed', rejected=3))

    def test_reflection_failure_is_exposed_instead_of_replaced_with_zero_activity(self):
        value = self.execute('reflection-failure', missing_field=True)
        self.assertEqual(value['errorClass'], 'java.lang.NoSuchFieldException')
        self.assertNotIn('observation', value)
        self.observations.append(dict(kind='missing-private-field-fails-closed', status='passed'))

    def test_compiled_observer_mutants_cannot_invalidate_views_or_cancel_animators(self):
        changes = (
            ('static JSONObject host(View view){', 'static JSONObject host(View view){view.invalidate();'),
            ('android.animation.ValueAnimator animator=(android.animation.ValueAnimator)value;',
             'android.animation.ValueAnimator animator=(android.animation.ValueAnimator)value;animator.cancel();'))
        for change in changes:
            with self.subTest(mutation=change[1]):
                self.assertTrue(self.execute('visible', mutation=change)['compiledMutationRejected'])
        self.observations.append(dict(kind='compiled-write-mutants-rejected', rejected=2))


MODEL = {
    'android/test/Mutation.java': '''package android.test;public final class Mutation {public static int calls;public static void forbidden(){calls++;throw new AssertionError("Observation attempted a state-changing call");}}''',
    'android/view/View.java': '''package android.view;
import android.graphics.drawable.Drawable;
public class View {
 public static final int VISIBLE=0,INVISIBLE=4,GONE=8;
 public int visibility=VISIBLE,windowVisibility=VISIBLE;public boolean attached=true,enabled=true,pressed,windowFocus=true;
 public View parent;public Drawable background;
 public boolean isAttachedToWindow(){return attached;}public boolean isShown(){return visibility==VISIBLE&&(parent==null||parent.isShown());}
 public int getVisibility(){return visibility;}public int getWindowVisibility(){return getRootView().windowVisibility;}
 public boolean hasWindowFocus(){return getRootView().windowFocus;}public boolean isEnabled(){return enabled;}public boolean isPressed(){return pressed;}
 public View getRootView(){return parent==null?this:parent.getRootView();}public Drawable getBackground(){return background;}
 public int getWidth(){return 100;}public int getHeight(){return 100;}
 public CharSequence getContentDescription(){throw new AssertionError("User content must not be read");}
 public void invalidate(){android.test.Mutation.forbidden();}public void requestLayout(){android.test.Mutation.forbidden();}
 public void setVisibility(int v){android.test.Mutation.forbidden();}public void setPressed(boolean p){android.test.Mutation.forbidden();}
 public void jumpDrawablesToCurrentState(){android.test.Mutation.forbidden();}
}''',
    'android/view/ViewGroup.java': '''package android.view;public class ViewGroup extends View {public final java.util.List<View> children=new java.util.ArrayList<>();public int getChildCount(){return children.size();}public View getChildAt(int index){return children.get(index);}public void seed(View v){children.add(v);v.parent=this;}public void addView(View v){android.test.Mutation.forbidden();}}''',
    'android/graphics/drawable/Drawable.java': '''package android.graphics.drawable;public class Drawable {public boolean visible=true;public int alpha=213;public int[] state={16842910,16842919};public boolean isVisible(){return visible;}public int getAlpha(){return alpha;}public int[] getState(){return state;}public boolean setVisible(boolean v,boolean restart){android.test.Mutation.forbidden();return false;}public void jumpToCurrentState(){android.test.Mutation.forbidden();}public void draw(Object canvas){android.test.Mutation.forbidden();}public boolean setState(int[] s){android.test.Mutation.forbidden();return false;}}''',
    'android/graphics/drawable/LayerDrawable.java': '''package android.graphics.drawable;public class LayerDrawable extends Drawable {private final Drawable[] layers;public LayerDrawable(Drawable[] values){layers=values;}public int getNumberOfLayers(){return layers.length;}public Drawable getDrawable(int index){return layers[index];}}''',
    'android/graphics/drawable/InsetDrawable.java': '''package android.graphics.drawable;public class InsetDrawable extends Drawable {private final Drawable child;public InsetDrawable(Drawable value){child=value;}public Drawable getDrawable(){return child;}}''',
    'android/animation/ValueAnimator.java': '''package android.animation;public class ValueAnimator {public boolean started=true,running=true;public long duration=480,playTime=73;public boolean isStarted(){return started;}public boolean isRunning(){return running;}public long getDuration(){return duration;}public long getCurrentPlayTime(){return playTime;}public void cancel(){android.test.Mutation.forbidden();}public void end(){android.test.Mutation.forbidden();}public void start(){android.test.Mutation.forbidden();}public void pause(){android.test.Mutation.forbidden();}}''',
}

OWNERS = '''package local.pocketchat;
import android.view.*;import android.graphics.drawable.*;import android.animation.*;import org.json.*;
final class LiquidGlassDrawable extends Drawable {@LIQUID_FIELDS@ LiquidGlassDrawable(ValueAnimator animator){animation=animator;pressed=true;strength=.4f;bend=.3f;}}
final class GlassDock extends ViewGroup {@DOCK_FIELDS@ GlassDock(ValueAnimator animator){transition=animator;opacity=.7f;flow=.2f;}}
final class GlassBackdrop extends ViewGroup {@BACKDROP_FIELDS@ GlassBackdrop(){glassActive=true;}@BACKDROP_ACTIVE@}
'''

HOST = r'''
public final class OwnerHost {
 static Object field(Object target,String name)throws Exception {java.lang.reflect.Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);}
 static String snapshot(ViewGroup toolbar,ViewGroup bar,GlassBackdrop panel,LiquidGlassDrawable material,GlassDock dock)throws Exception {
  ValueAnimator animation=(ValueAnimator)field(material,"animation"),transition=(ValueAnimator)field(dock,"transition");
  return J.obj("toolbarVisibility",toolbar.visibility,"barVisibility",bar.visibility,"materialVisible",material.visible,"materialAlpha",material.alpha,
   "materialState",J.arr(material.state[0],material.state[1]),"pressed",field(material,"pressed"),"strength",field(material,"strength"),"bend",field(material,"bend"),
   "animation",animation==null?JSONObject.NULL:J.obj("started",animation.started,"running",animation.running,"duration",animation.duration,"playTime",animation.playTime),
   "transition",transition==null?JSONObject.NULL:J.obj("started",transition.started,"running",transition.running,"duration",transition.duration,"playTime",transition.playTime),
   "opacity",field(dock,"opacity"),"flow",field(dock,"flow"),"backdrop",field(panel,"glassActive")).toString();
 }
 public static void main(String[] args)throws Exception {
  String mode=args[0];ViewGroup decor=new ViewGroup(),toolbar=new ViewGroup(),bar=new ViewGroup();decor.seed(toolbar);decor.seed(bar);
  GlassBackdrop panel=new GlassBackdrop();decor.seed(panel);
  ValueAnimator pulse=mode.equals("absent")?null:new ValueAnimator(),travel=mode.equals("absent")?null:new ValueAnimator();
  if(mode.equals("stopped")){pulse.started=pulse.running=travel.started=travel.running=false;}
  if(mode.equals("scheduled")){pulse.running=travel.running=false;}
  LiquidGlassDrawable material=new LiquidGlassDrawable(pulse);View host=new View();
  host.background=new LayerDrawable(new Drawable[]{new Drawable(),new InsetDrawable(material)});toolbar.seed(host);
  GlassDock dock=new GlassDock(travel);bar.seed(dock);
  if(mode.equals("hidden")||mode.equals("restore")){toolbar.visibility=View.GONE;bar.visibility=View.GONE;panel.visibility=View.GONE;}
  if(mode.equals("reflection-failure")){
   try{ChromeCollapseIntegration.GlassOwnerObservation.read(toolbar,bar,panel);throw new AssertionError("Missing private field was masked");}
   catch(NoSuchFieldException expected){System.out.println(J.obj("errorClass",expected.getClass().getName(),"mutationCalls",android.test.Mutation.calls,"stateUnchanged",true));return;}
  }
  String before=snapshot(toolbar,bar,panel,material,dock);
  if(mode.startsWith("null-")){
   try{ChromeCollapseIntegration.GlassOwnerObservation.read(mode.equals("null-toolbar")?null:toolbar,mode.equals("null-bar")?null:bar,mode.equals("null-panel")?null:panel);throw new AssertionError("Missing root was accepted");}
   catch(IllegalStateException expected){System.out.println(J.obj("errorClass",expected.getClass().getName(),"mutationCalls",android.test.Mutation.calls,"stateUnchanged",before.equals(snapshot(toolbar,bar,panel,material,dock))));return;}
  }
  JSONObject observed=ChromeCollapseIntegration.GlassOwnerObservation.read(toolbar,bar,panel);
  String after=snapshot(toolbar,bar,panel,material,dock);
  if(!before.equals(after))throw new AssertionError("Observer changed owner state");
  if(mode.equals("restore")){
   JSONObject previous=observed;toolbar.visibility=View.VISIBLE;bar.visibility=View.VISIBLE;panel.visibility=View.VISIBLE;
   before=snapshot(toolbar,bar,panel,material,dock);observed=ChromeCollapseIntegration.GlassOwnerObservation.read(toolbar,bar,panel);
   after=snapshot(toolbar,bar,panel,material,dock);if(!before.equals(after))throw new AssertionError("Observer changed restored owner state");
   System.out.println(J.obj("previousObservation",previous,"observation",observed,"mutationCalls",android.test.Mutation.calls,"stateUnchanged",before.equals(after)));return;
  }
  System.out.println(J.obj("observation",observed,"mutationCalls",android.test.Mutation.calls,"stateUnchanged",before.equals(after)));
 }
}
'''


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GlassOwnerObservationTests))
    report = dict(schema=1, status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
                  fixtureSha256=SHA(FIXTURE.read_bytes()), helperSourceSha256=SHA(observer_source().encode()),
                  testSha256=SHA(Path(__file__).read_bytes()), observations=GlassOwnerObservationTests.observations,
                  actualAndroidExecution=False, actualGeckoExecution=False, actualHwuiObservation=False,
                  android35ApiCompiled=any(row.get('kind') == 'actual-android-api-compile' for row in GlassOwnerObservationTests.observations),
                  android32ApiCompiled=False,
                  scope='Exact test-only observer body on modeled owner states with fail-fast mutation sentinels and fixed real desktop JSON; separate pinned Android35 API compilation with compile-only owner declarations. No Android stub execution, device or acceptance evidence.')
    output = os.environ.get('PROFILE_GLASS_OWNER_OBSERVATION_REPORT')
    if output:
        path = Path(output);path.parent.mkdir(parents=True, exist_ok=True);path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
