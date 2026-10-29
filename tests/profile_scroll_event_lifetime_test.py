"""Replay exact fixture Java/JS observation lifetime; no Android/APZ evidence.

This only repairs passive observation coverage. It neither predicts late events
in d947 nor changes native_input_contract, workload timing, gestures or budgets.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / 'tests/gecko/GeckoPerformanceIntegrationActivity.java'
ORACLE = ROOT / 'tools/gecko/native_input_contract.py'
spec = importlib.util.spec_from_file_location('scroll_source_blocks', ROOT / 'tools/gecko/run_network_core_host.py')
extract = importlib.util.module_from_spec(spec); spec.loader.exec_module(extract)
block = extract.block
sha = lambda text: hashlib.sha256(text.encode()).hexdigest()
PROTECTED = {
    'void beginScrollDiagnostics()': '2958bced18a8c745891fc077cb01fa4d3f17eb5a62d49c4dee700c8903bd397b',
    'JSONObject scrollNativeSnapshot()': 'c684fde900afc6649027211d4d44daa45978efe3ff2daf40e1c773e205b7752c',
    'void recordScrollSample(': 'ef88d1d42ecfdf7fe6de0541653b96147e8618c0769534d9b2c32394d1f3e10b',
    'void scrollGesture()': '2398fd9d6474fb076837891fce87da15e65c8b82fecdc6f0d70fe3b69965db7c',
    'void waitScroll(': '190ec7eb7386b9a08de0e94a588ae0026b76d7c4e8c5880070dd22bd6ef94e95',
    'void nextSample()': '9b1c1a2dfeaca91994d413a79eece861f9c2ca2acbfb3ea6b21ec772132ad243',
    'void sample()': 'f9c1d045094d3f4514a76ebbf6d6b1355500d7dd7043bd9143a11e3572b25790',
    'String telemetryInstall()': 'aa0dab247b251bc29b040c67221665472b21ca4b04c0bc6810b85641358ab251',
    'static final class FrameSample': '87c53eebc76651c70359c07b9076092c9596e57104084f51219563f9cf0cd099',
    'void fail(': '7154e1eb23806aa380d4b78e716642af39a5518d883cce8b5629e90c751b16eb',
    '@Override protected void onDestroy()': '8752d25c08cc9e2cb66f0e9f7acd8d84bb7c2a199c0753265365508819bae136',
}
ORIGINAL_SNAPSHOT_SHA = '06cea01ba00ee6c7008bc5091084f52fb27c7278b47351e6b29b9638b483a484'
ORIGINAL_MEASURED_SHA = '881df0c4dc2d91ff018ba25a2391f98e95382875ae9d7cd948e2b8c32622cfde'
ORIGINAL_EVENT_SHA = '1f725edf779cb40e7e2b1c011cb18af38c2bf294d66d08c428dfcffb3a053684'
ORIGINAL_ORACLE_SHA = '4d2cce88a7642aed899f3b2e024dce9e4fb1a1dd865558643671332e8790b42d'


def original_oracle(current):
    added = b"          'tests/native-input-driver/NativePreEmitReadiness.java',\n"
    before = b"INPUTS = {'tests/native-input-driver/NativeGestureProtocol.java',\n"
    after = b"          'tests/native-input-driver/NativeInputShell.java',\n"
    reviewed = before + added + after
    if not isinstance(current, bytes) or current.count(added) != 1 or current.count(reviewed) != 1:
        raise ValueError('Unreviewed native input oracle change')
    original = current.replace(reviewed, before + after, 1)
    if hashlib.sha256(original).hexdigest() != ORIGINAL_ORACLE_SHA:
        raise ValueError('Unreviewed native input oracle change')
    return original


def original_snapshot(current):
    replacements = [
        ('active:true,cancelled:false,events:[],count:0,initial:document.scrollingElement.scrollTop,run:"+JSONObject.quote(scrollDiagnosticRun)+",phase:"+JSONObject.quote(variant)+",traceId:"+scrollPhase.started+",document:performance.timeOrigin,url:location.href',
         'active:true,events:[],count:0,initial:document.scrollingElement.scrollTop'),
        ('if(!trace.active)return;if(trace.document!==performance.timeOrigin||trace.url!==location.href){trace.cancel();return;}trace.count++',
         'if(!trace.active)return;trace.count++'),
        ("window.removeEventListener(type,listener,true);window.removeEventListener('pagehide',trace.cancel,true);};trace.cancel=()=>{trace.cancelled=true;trace.stop();};for(const type of types)window.addEventListener(type,listener,{passive:true,capture:true});window.addEventListener('pagehide',trace.cancel,{once:true,capture:true});",
         'window.removeEventListener(type,listener,true);};for(const type of types)window.addEventListener(type,listener,{passive:true,capture:true});'),
        ('const top=d.scrollTop;return', 'const top=d.scrollTop;if(trace&&top>trace.initial)trace.stop();return'),
    ]
    for before, after in replacements:
        if current.count(before) != 1:
            raise ValueError('Unreviewed scroll snapshot change: ' + before[:80])
        current = current.replace(before, after, 1)
    if sha(current) != ORIGINAL_SNAPSHOT_SHA:
        raise ValueError('Snapshot changed beyond identity, cancellation and listener lifetime')
    return current


JAVA_HOST = r'''
import java.util.*;
import org.json.*;
public class ScrollLifetimeHost {
  static class SystemClock {static long now=100;static long elapsedRealtime(){return now;}}
  static class Log {static final List<JSONObject> rows=new ArrayList<>();static void i(String tag,String text){try{rows.add(new JSONObject(text));}catch(JSONException invalid){throw new AssertionError(invalid);}}}
  static class J {static JSONObject obj(Object...pairs){try{JSONObject value=new JSONObject();for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);return value;}catch(JSONException invalid){throw new AssertionError(invalid);}}}
  static class GeckoSession {interface CompositorScrollDelegate{} final CompositorScrollDelegate original=new CompositorScrollDelegate(){};CompositorScrollDelegate delegate=original;CompositorScrollDelegate getCompositorScrollDelegate(){return delegate;}void setCompositorScrollDelegate(CompositorScrollDelegate next){delegate=next;}}
  static class ChatSession {FixtureView web=new FixtureView();long navigationEpoch=7;}
  static class FixtureView {GeckoSession current=new GeckoSession();android.view.View surface=new android.view.View();String url="http://127.0.0.1:8767/performance?variant=baseline";boolean scrollTracing=true;JSONArray scrollTouches=new JSONArray().put(J.obj("action",0)).put(J.obj("action",2));int scrollTouchCount=2;String getUrl(){return url;}}
  ChatSession session=new ChatSession();String variant="baseline",scrollDiagnosticRun="0123456789abcdef0123456789abcdef";boolean finished;
  final JSONArray scrollDiagnosticPhases=new JSONArray();ScrollPhase scrollPhase,scrollDomTail;String saved="";int writes;
  /* EXACT_PHASE */
  /* EXACT_METHODS */
  void writeScrollDiagnostics(){writes++;saved=scrollDiagnosticPhases.toString();}
  ScrollPhase prepare(JSONArray before,boolean deadline)throws Exception{
    SystemClock.now=100;scrollPhase=new ScrollPhase(variant,session);ScrollPhase phase=scrollPhase;
    phase.samples.put(J.obj("dom",J.obj("document",1010,"url",session.web.url),"native",J.obj("untouched",true)));phase.sampleCount=1;
    for(int i=0;i<before.length();i++){JSONObject value=before.getJSONObject(i);phase.domEvents.put(value);event("scrollDomEvent",J.obj("phase",phase.variant,"event",value));}
    event("gestureDeadline",deadline?J.obj("id","baseline-scroll","expiresElapsedMs",20100):J.obj("id","baseline-scroll"));
    return phase;
  }
  static JSONObject scripts()throws Exception{
    ScrollLifetimeHost host=new ScrollLifetimeHost();host.prepare(new JSONArray(),true);
    String begin=host.scrollSnapshotScript(true),snapshot=host.scrollSnapshotScript(false),legacy=host.legacyScrollSnapshotScript(true),legacySnapshot=host.legacyScrollSnapshotScript(false);
    host.finishScrollDiagnostics("passed");
    return J.obj("begin",begin,"snapshot",snapshot,"legacyBegin",legacy,"legacySnapshot",legacySnapshot,"telemetry",host.scrollTelemetryScript(host.scrollDomTail));
  }
  static JSONObject apply(JSONObject request)throws Exception{
    Log.rows.clear();ScrollLifetimeHost host=new ScrollLifetimeHost();ScrollPhase phase=host.prepare(request.getJSONArray("before"),!request.optBoolean("noDeadline"));
    host.finishScrollDiagnostics("passed");String originalSamples=phase.samples.toString(),originalTouches=host.session.web.scrollTouches.toString();
    JSONObject tail=request.optJSONObject("tail");String change=request.optString("change");SystemClock.now=request.optLong("now",200);
    if(change.equals("session"))host.session.web.current=new GeckoSession();
    if(change.equals("surface"))host.session.web.surface=new android.view.View();
    if(change.equals("navigation"))host.session.navigationEpoch++;
    if(change.equals("url"))host.session.web.url+="&changed=1";
    if(change.equals("run"))host.scrollDiagnosticRun="another-run";
    if(change.equals("phase"))host.variant="current";
    if(change.equals("cancel"))host.cancelScrollDomTail("destroyed");
    host.finishScrollDomTail(phase,tail);host.finishScrollDomTail(phase,tail);
    JSONArray logged=new JSONArray();for(JSONObject row:Log.rows)if(row.getString("kind").equals("scrollDomEvent"))logged.put(row.getJSONObject("value").getJSONObject("event"));
    if(!logged.toString().equals(phase.domEvents.toString()))throw new AssertionError("File/log event sequence differs");
    if(!new JSONArray(host.saved).getJSONObject(0).getJSONArray("domEvents").toString().equals(logged.toString()))throw new AssertionError("Final file lost appended events");
    if(!originalSamples.equals(phase.samples.toString())||!originalTouches.equals(host.session.web.scrollTouches.toString()))throw new AssertionError("Native samples changed");
    // A duplicate old callback must not cancel a newer pending observation.
    ScrollPhase newer=new ScrollPhase("current",host.session);host.scrollDomTail=newer;host.finishScrollDomTail(phase,tail);
    if(host.scrollDomTail!=newer)throw new AssertionError("Stale callback consumed a new phase");
    return J.obj("case",request.getString("case"),"phase",scrollPhaseCopy(phase,host),"nativeStopped",!host.session.web.scrollTracing,"delegateRestored",phase.sdk.delegate==phase.prior,"fileLogEqual",true,"nativeSamplesUnchanged",true,"staleCallbackIgnored",true);
  }
  static JSONObject scrollPhaseCopy(ScrollPhase phase,ScrollLifetimeHost host)throws Exception{return new JSONArray(host.saved).getJSONObject(0);}
  public static void main(String[] args)throws Exception{
    if(args[0].equals("scripts")){System.out.println(scripts());return;}
    if(args[0].equals("deadlines")){
      ScrollLifetimeHost host=new ScrollLifetimeHost();host.scrollPhase=new ScrollPhase("baseline",host.session);
      JSONObject wrong=J.obj("id","current-scroll","expiresElapsedMs",90000);String raw=wrong.toString();host.event("gestureDeadline",wrong);long ignored=host.scrollPhase.expiresElapsedMs;
      JSONObject actual=J.obj("id","baseline-scroll","expiresElapsedMs",20100);String original=actual.toString();host.event("gestureDeadline",actual);
      System.out.println(J.obj("wrongIdIgnored",ignored==0,"originalDeadline",host.scrollPhase.expiresElapsedMs,"valuesUnchanged",raw.equals(wrong.toString())&&original.equals(actual.toString()),"originalEnvelope",Log.rows.get(1)));return;
    }
    String text=new String(System.in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);JSONArray requests=new JSONArray(text),results=new JSONArray();
    for(int i=0;i<requests.length();i++)results.put(apply(requests.getJSONObject(i)));System.out.println(results);
  }
}
'''

NODE_HOST = r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const scripts=JSON.parse(fs.readFileSync(0,'utf8'));
function page(){
  const listeners=new Map(),registrations=[];let now=0;
  const window={addEventListener(type,fn,options){registrations.push({type,options});if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(fn);},removeEventListener(type,fn){listeners.get(type)?.delete(fn);}};
  const context={window,document:{scrollingElement:{scrollTop:0,scrollLeft:0,clientHeight:700,clientWidth:414,scrollHeight:90000,scrollWidth:414},hasFocus:()=>true,activeElement:{tagName:'BODY'},visibilityState:'visible'},
    performance:{timeOrigin:1010,now:()=>now},location:{href:'http://127.0.0.1:8767/performance?variant=baseline'},visualViewport:{pageTop:0,pageLeft:0,offsetTop:0,offsetLeft:0,height:700,width:414,scale:1},scrollY:0,scrollX:0,innerHeight:700,innerWidth:414};
  window.__fixtureTelemetry=()=>{context.telemetryCalls++;context.telemetryObserved={active:window.__fixtureScrollDiagnostics?.active,pending:window.__fixtureScrollDiagnostics?.events.length};return {originalMetric:42,elapsedMs:1000}};context.telemetryCalls=0;
  vm.createContext(context);
  const emit=(type,trusted=true)=>{now++;const point={clientX:200,clientY:400};const event={type,isTrusted:trusted,eventPhase:1,touches:type.startsWith('touch')?[point]:[],changedTouches:[point]};for(const fn of [...(listeners.get(type)||[])])fn(event);};
  const scroll=()=>{context.document.scrollingElement.scrollTop=50;context.scrollY=context.visualViewport.pageTop=50;emit('scroll');};
  const evaluate=code=>JSON.parse(JSON.stringify(vm.runInContext(code,context)));
  return {context,emit,scroll,evaluate,registrations};
}
function run(name,mode,legacy=false){
  const p=page();p.evaluate(legacy?scripts.legacyBegin:scripts.begin);
  if(mode==='normal')p.emit('touchstart');p.scroll();
  const first=p.evaluate(legacy?scripts.legacySnapshot:scripts.snapshot);
  if(mode==='normal')p.emit('touchend');
  if(mode==='late')p.emit('touchstart');
  if(mode==='untrusted')p.emit('touchstart',false);
  if(mode==='touchcancel')p.emit('touchcancel');
  if(mode==='cancel'){p.emit('pagehide');p.emit('touchstart');}
  if(mode==='crossdoc'){p.context.performance.timeOrigin=2020;p.emit('touchstart');}
  if(mode==='crossurl'){p.context.location.href+='&changed=1';p.emit('touchstart');}
  if(mode==='cap'){for(let i=0;i<63;i++)p.emit('scroll');p.emit('touchstart');}
  const beforeTelemetry={active:p.context.window.__fixtureScrollDiagnostics.active,pending:p.context.window.__fixtureScrollDiagnostics.events.length};
  const measured=legacy?{scrollDomTail:{events:p.context.window.__fixtureScrollDiagnostics.events}}:p.evaluate(scripts.telemetry);
  if(!legacy){assert.equal(p.context.telemetryCalls,1);assert.deepEqual(p.context.telemetryObserved,beforeTelemetry);assert.equal(measured.originalMetric,42);assert.equal(measured.elapsedMs,1000);assert.ok(p.registrations.filter(x=>x.type!=='pagehide').every(x=>x.options.passive&&x.options.capture));}
  return {case:name,before:first.events,tail:measured.scrollDomTail,first,telemetryCalls:p.context.telemetryCalls,telemetryBeforeDrain:!legacy};
}
const rows=[run('late','late'),run('normal','normal'),run('untrusted','untrusted'),run('missing','missing'),run('cancel','cancel'),run('crossdoc','crossdoc'),run('crossurl','crossurl'),run('cap','cap'),run('touchcancel-only','touchcancel')];
const oldLate=run('old-late','late',true),oldNormal=run('old-normal','normal',true);
assert.equal(oldLate.before.length,1);assert.equal(oldLate.tail.events.length,0);
assert.equal(rows[0].tail.events[0].type,'touchstart');assert.equal(rows[0].tail.events[0].trusted,true);
assert.deepEqual(rows[1].before,oldNormal.before);
for(const field of Object.keys(oldNormal.first))if(!['listenersActive','events'].includes(field))assert.deepEqual(rows[1].first[field],oldNormal.first[field]);
assert.equal(oldNormal.first.listenersActive,false);assert.equal(rows[1].first.listenersActive,true);
assert.equal(rows[7].tail.eventCount,65);assert.equal(rows[7].tail.eventsDropped,1);assert.equal(rows[7].before.length+rows[7].tail.events.length,64);
console.log(JSON.stringify({rows,oldLate,oldNormal,actualAndroidExecution:false,actualGeckoExecution:false}));
'''


def host_source(source):
    signatures = ['  static final class ScrollPhase ', '  void event(', '  String scrollSnapshotScript(',
                  '  String scrollTelemetryScript(', '  void finishScrollDiagnostics(',
                  '  void cancelScrollDomTail(', '  void finishScrollDomTail(']
    selected = {signature: block(source, signature) for signature in signatures}
    legacy = original_snapshot(selected['  String scrollSnapshotScript(']).replace('scrollSnapshotScript(', 'legacyScrollSnapshotScript(', 1)
    host = JAVA_HOST.replace('/* EXACT_PHASE */', selected[signatures[0]])
    host = host.replace('/* EXACT_METHODS */', '\n'.join(selected[s] for s in signatures[1:]) + '\n' + legacy)
    for body in selected.values():
        if host.count(body) != 1:
            raise ValueError('Source-exact block rewritten or duplicated')
    return host, {signature: sha(body) for signature, body in selected.items()}


class ScrollEventLifetimeTest(unittest.TestCase):
    def test_original_workload_and_oracle_are_preserved(self):
        source = ACTIVITY.read_text()
        for signature, expected in PROTECTED.items():
            with self.subTest(signature=signature): self.assertEqual(sha(block(source, '  ' + signature)), expected)
        measured = block(source, '  void measured()')
        before = 'evaluate(scrollTelemetryScript(domPhase),false,telemetry->{\n      finishScrollDomTail(domPhase,telemetry.optJSONObject("scrollDomTail"));'
        self.assertEqual(measured.count(before), 1)
        measured = measured.replace('ScrollPhase domPhase=scrollDomTail;', '', 1).replace(before, 'evaluate("window.__fixtureTelemetry()",false,telemetry->{', 1)
        self.assertEqual(sha(measured), ORIGINAL_MEASURED_SHA)
        event = block(source, '  void event(')
        capture = '\n    if("gestureDeadline".equals(kind)&&scrollPhase!=null&&(scrollPhase.variant+"-scroll").equals(value.optString("id"))){scrollPhase.expiresElapsedMs=value.optLong("expiresElapsedMs",0);scrollPhase.run=scrollDiagnosticRun==null?"":scrollDiagnosticRun;}\n  '
        self.assertEqual(event.count(capture), 1)
        self.assertEqual(sha(event.replace(capture, '', 1)), ORIGINAL_EVENT_SHA)
        finish = block(source, '  void finishScrollDiagnostics(').splitlines()
        native_stop = next(line for line in finish if line.startswith('    ScrollPhase phase=scrollPhase;if(phase==null)return;FixtureView web='))
        self.assertEqual(sha(native_stop), 'e0cbd9ec619b7accbddffb7eaefc97a8503428a9f45cbdbcc53690694ec17668')
        native_fields = next(line for line in finish if line.startswith('    scrollDiagnosticPhases.put(J.obj('))
        self.assertEqual(native_fields.count(',"domObservation",phase.domObservation'), 1)
        self.assertEqual(sha(native_fields.replace(',"domObservation",phase.domObservation', '', 1)), '9b25f1e9656e3c19885bf64f9888c0f3ecddc82865c6ea15aaecc9c9792afccf')
        self.assertEqual(hashlib.sha256(original_oracle(ORACLE.read_bytes())).hexdigest(), ORIGINAL_ORACLE_SHA)
        self.assertEqual(sha(original_snapshot(block(source, '  String scrollSnapshotScript('))), ORIGINAL_SNAPSHOT_SHA)

    def test_oracle_inventory_inverse_rejects_other_changes(self):
        current = ORACLE.read_bytes()
        added = b"          'tests/native-input-driver/NativePreEmitReadiness.java',\n"
        mutations = {
            'missing helper': current.replace(added, b'', 1),
            'duplicate helper': current.replace(added, added + added, 1),
            'misplaced helper': current.replace(added, b'', 1) + added,
            'different indentation': current.replace(added, added[1:], 1),
            'oracle body changed': current.replace(b"raise ValueError('Native input: ' + message)", b'return', 1),
            'protocol changed': current.replace(b"('qualification', 15)", b"('qualification', 16)", 1),
        }
        for name, modified in mutations.items():
            with self.subTest(change=name):
                self.assertNotEqual(modified, current)
                with self.assertRaisesRegex(ValueError, 'Unreviewed native input oracle change'):
                    original_oracle(modified)

    def test_exact_java_and_javascript_observe_real_tail_only(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java'); node = shutil.which('node')
        self.assertTrue(java and node, 'Java17 and Node required for source-exact observation replay')
        jars = [os.environ.get('PROFILE_JSON_JAR', ''), str(ROOT / 'work/profile-host/json.jar'), str(ROOT / 'work/gecko-integration/catalog-json.jar')]
        jar = next((Path(p) for p in jars if p and Path(p).is_file()), None); self.assertIsNotNone(jar, 'Existing host JSON dependency required')
        source = ACTIVITY.read_text(); host, selected = host_source(source)
        inputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ACTIVITY, ORACLE, ROOT / 'tools/gecko/run_network_core_host.py', Path(__file__)]}
        with tempfile.TemporaryDirectory(prefix='scroll-observation-lifetime-') as directory:
            out = Path(directory); (out / 'ScrollLifetimeHost.java').write_text(host)
            (out / 'View.java').write_text('package android.view;public class View{}')
            compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(out), str(out / 'ScrollLifetimeHost.java'), str(out / 'View.java')], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            command = [java, '-cp', str(out) + os.pathsep + str(jar), 'ScrollLifetimeHost']
            emitted = subprocess.run(command + ['scripts'], capture_output=True, text=True, timeout=10); self.assertEqual(emitted.returncode, 0, emitted.stderr)
            scripts = json.loads(emitted.stdout)
            observed = subprocess.run([node, '-e', NODE_HOST], input=json.dumps(scripts), capture_output=True, text=True, timeout=10)
            self.assertEqual(observed.returncode, 0, observed.stdout + observed.stderr); replay = json.loads(observed.stdout)
            requests = copy.deepcopy(replay['rows'])
            for change in ['session', 'surface', 'navigation', 'url', 'run', 'phase', 'cancel']:
                request = copy.deepcopy(replay['rows'][0]); request.update(case='native-' + change, change=change); requests.append(request)
            for name, values in [('deadline-boundary', dict(now=20100)), ('expired', dict(now=20101)), ('missing-deadline', dict(noDeadline=True)), ('missing-tail', dict(tail=None))]:
                request = copy.deepcopy(replay['rows'][0]); request.update(case=name, **values); requests.append(request)
            for name, mutate in [('duplicate-sequence', lambda t: t['events'][0].update(sequence=1)), ('trusted-string', lambda t: t['events'][0].update(trusted='true')), ('incomplete-count', lambda t: t.update(events=[]))]:
                request = copy.deepcopy(replay['rows'][0]); request['case'] = name; mutate(request['tail']); requests.append(request)
            for key, value in [('run','another-run'),('phase','current'),('traceId',101),('document',2020),('url','http://127.0.0.1:8767/other')]:
                request = copy.deepcopy(replay['rows'][0]); request['case'] = 'tail-' + key; request['tail'][key] = value; requests.append(request)
            ran = subprocess.run(command + ['apply'], input=json.dumps(requests), capture_output=True, text=True, timeout=10)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr); results = json.loads(ran.stdout)
            # Execute the original oracle's exact touch predicate, without faking
            # the other signature/device/driver qualification prerequisites.
            tree = ast.parse(ORACLE.read_text())
            call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and len(n.args) > 1 and isinstance(n.args[1], ast.Constant) and n.args[1].value == 'trusted Gecko touch missing')
            predicate = compile(ast.Expression(call.args[0]), str(ORACLE), 'eval')
            old_events = replay['oldLate']['before'] + replay['oldLate']['tail']['events']
            self.assertFalse(eval(predicate, {'phase': {'domEvents': old_events}}))
            for result in results:
                actual = eval(predicate, {'phase': result['phase']})
                self.assertEqual(actual, result['case'] in ['late', 'normal', 'deadline-boundary'], result)
                self.assertTrue(result['nativeStopped'] and result['delegateRestored'] and result['fileLogEqual'] and result['nativeSamplesUnchanged'] and result['staleCallbackIgnored'])
                self.assertLessEqual(len(result['phase']['domEvents']), 64)
                self.assertEqual(set(result['phase']), {'phase','outcome','url','navigationEpoch','sampleCount','samplesDropped','samples','nativeUpdates','nativeUpdatesCount','nativeUpdatesDropped','nativeTouches','nativeTouchCount','nativeTouchesDropped','domEvents','domObservation'})
            cap = next(r for r in results if r['case'] == 'cap')['phase']
            self.assertEqual(cap['domObservation'][0]['eventsDropped'], 1)
            self.assertEqual([e['sequence'] for e in cap['domEvents']], list(range(1, 65)))
            deadlines = subprocess.run(command + ['deadlines'], capture_output=True, text=True, timeout=10); self.assertEqual(deadlines.returncode, 0, deadlines.stderr)
            deadline = json.loads(deadlines.stdout); self.assertTrue(deadline['wrongIdIgnored'] and deadline['valuesUnchanged']); self.assertEqual(deadline['originalDeadline'], 20100)
            self.assertEqual(deadline['originalEnvelope'], {'kind':'gestureDeadline','value':{'id':'baseline-scroll','expiresElapsedMs':20100}})
        self.assertTrue(all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest for p, digest in inputs.items()))
        report = dict(status='passed', actualAndroidExecution=False, actualGeckoExecution=False, actualApzExecution=False,
                      scope='Source-exact fixture Java/JS passive observation replay; synthetic event order and clock only. No prediction that d947 dispatched late touch events.',
                      sourceFiles=inputs, extractedBlocksSha256=selected, jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
                      oldEarlyStop=replay['oldLate'], telemetryBeforeDrain=all(row['telemetryBeforeDrain'] for row in replay['rows']), cases=results, originalDeadline=deadline, executionInputsUnchanged=True)
        target = Path(os.environ.get('PROFILE_SCROLL_LIFETIME_REPORT', ROOT / 'work/gecko-integration/scroll-event-lifetime-host-results.json'))
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__': unittest.main()
