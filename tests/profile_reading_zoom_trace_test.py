"""Optional fixture numeric trace controls; no Android or Gecko execution."""
import argparse,ast,copy,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from reading_zoom_trace_contract import ROOT,PATHS,trace_manifest,original_reading_fixture_bytes
from reading45_source_compatibility import reading45_source_bytes
FIXTURE='tests/gecko/GeckoIntegrationTestActivity.java'
RUNNER='tests/gecko/run_device.py'
PINS={'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796','dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}

def member(text,needle):
 start=text.index(needle);opening=text.index('{',start);level=0
 for i in range(opening,len(text)):
  if text[i]=='{':level+=1
  elif text[i]=='}':
   level-=1
   if level==0:return text[start:i+1]
 raise AssertionError('Unclosed controlled Java member')

def start_call(source):
 tree=ast.parse(source)
 return next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='adb' and len(n.args)>3 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='am' and isinstance(n.args[2],ast.Constant) and n.args[2].value=='start')

class ReadingZoomTraceControls(unittest.TestCase):
 def test_exact_original_whole_sources_recovered(self):
  for path,(digest,_) in PATHS.items():self.assertEqual(hashlib.sha256(original_reading_fixture_bytes((ROOT/path).read_bytes(),path)).hexdigest(),digest)
 def test_each_optional_addition_rejects_missing_duplicate_changed_and_relocated(self):
  for path,row in trace_manifest()['paths'].items():
   source=(ROOT/path).read_text()
   for item in row['insertions']:
    literal=item['before']+item['inserted']+item['after'];old=item['before']+item['after']
    for candidate in [source.replace(literal,old,1),source.replace(literal,item['before']+item['inserted']*2+item['after'],1),source.replace(literal,item['before']+item['inserted']+' '+item['after'],1),source.replace(literal,old,1)+item['inserted']]:
     with self.subTest(path=path,addition=item['id']):
      with self.assertRaises(ValueError):original_reading_fixture_bytes(candidate.encode(),path)
 def test_old_oracle_and_runner_changes_cannot_hide_behind_observation(self):
  for path,old,new in [(FIXTURE,'Math.abs(relative-4.2)<.05','Math.abs(relative-4.2)<.06'),(FIXTURE,'SystemClock.elapsedRealtime()+20000','SystemClock.elapsedRealtime()+21000'),(RUNNER,'deadline=time.monotonic()+120','deadline=time.monotonic()+121')]:
   source=(ROOT/path).read_text();self.assertIn(old,source)
   with self.assertRaises(ValueError):original_reading_fixture_bytes(source.replace(old,new,1).encode(),path)
 def test_default_and_other_action_argv_are_exactly_original(self):
  current=(ROOT/RUNNER).read_text();old=original_reading_fixture_bytes(current.encode(),RUNNER).decode()
  def evaluate(source,args,action,extra):
   call=start_call(source);received=[];scope=dict(args=args,action=action,extra=extra,package='fixed.package',activity='FixedActivity',nonce='fixed-nonce',adb=lambda *v:received.append(v));eval(compile(ast.Expression(copy.deepcopy(call)),'<actual am-start call>','eval'),scope);self.assertEqual(len(received),1);return received[0]
  for action in ('read','readingBounds','readingBoundsProtected','readingBoundsInput','readingZoom'):
   for extra in [(),('--es','geometryPhase','portrait')]:
    expected=evaluate(old,SimpleNamespace(),action,extra)
    for args in [SimpleNamespace(),SimpleNamespace(reading_zoom_trace=False),SimpleNamespace(reading_zoom_trace='true')]:self.assertEqual(evaluate(current,args,action,extra),expected)
    actual=evaluate(current,SimpleNamespace(reading_zoom_trace=True),action,extra)
    if action in ('readingBounds','readingBoundsProtected'):
     end=len(expected)-len(extra);self.assertEqual(actual,expected[:end]+('--ez','readingZoomTrace','true')+extra)
    else:self.assertEqual(actual,expected)
 def test_real_parser_flag_defaults_false_and_explicitly_enables(self):
  tree=ast.parse((ROOT/RUNNER).read_text());main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main');nodes=[]
  for n in main.body:
   nodes.append(copy.deepcopy(n))
   if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='args' for t in n.targets):break
  for switches,expected in [([],False),(['--reading-zoom-trace'],True)]:
   scope=dict(argparse=argparse,pathlib=pathlib,ROOT=ROOT)
   with patch.object(sys,'argv',['controlled','--adb','fixed',*switches]):exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual parser>','exec'),scope)
   self.assertIs(scope['args'].reading_zoom_trace,expected)
 def test_observation_has_no_new_sdk_script_or_scheduled_work(self):
  rows=trace_manifest()['paths'][FIXTURE]['insertions'];added=''.join(x['inserted'] for x in rows)
  for denied in ('.evaluateJavascript(','.getScale(','.getClientToSurfaceMatrix(','.getPanZoomController(','.postDelayed(','.setCompositorScrollDelegate('):self.assertNotIn(denied,added)
  self.assertIn('getBooleanExtra("readingZoomTrace",false)',added);self.assertEqual(added.count('super.zoomBy(factor);'),1)
  self.assertIn('if(test.trace!=null&&serial==run)recordReadingZoomNative(serial,test,update.zoom);',added)
  self.assertIn('test.nativeSession!=session.web.current',added)
  baseline=original_reading_fixture_bytes((ROOT/FIXTURE).read_bytes(),FIXTURE).decode();current=(ROOT/FIXTURE).read_text()
  self.assertEqual(current.count('test.priorDelegate.onScrollChanged(own,update)'),baseline.count('test.priorDelegate.onScrollChanged(own,update)'))
  self.assertEqual(current.count('evaluateJavascript('),baseline.count('evaluateJavascript('));self.assertEqual(current.count('postDelayed('),baseline.count('postDelayed('))
 def test_original_golden_guard_bodies_and_hashes_remain(self):
  path=ROOT/'tests/profile_reading_fit_completion_test.py';s=reading45_source_bytes(path.read_bytes(),'tests/profile_reading_fit_completion_test.py').decode();s=s.replace('from reading_zoom_trace_contract import original_reading_fixture_bytes\n','',1).replace("   if name in ('tests/gecko/GeckoIntegrationTestActivity.java','tests/gecko/run_device.py'):raw=original_reading_fixture_bytes(raw,name)\n",'',1)
  self.assertEqual(hashlib.sha256(s.encode()).hexdigest(),'ea2ee6f5f0a3d9c9937c6d0a6e1e39589643d1509b42250b4e2a4ecc31825806')
  path=ROOT/'tests/gecko_device_readiness_test.py';s=path.read_text();s=s.replace("    from reading_zoom_trace_contract import strip_reviewed_reading_trace_additions\n    source=strip_reviewed_reading_trace_additions(source.encode('utf-8'),'tests/gecko/run_device.py').decode('utf-8')\n",'',1)
  self.assertEqual(hashlib.sha256(s.encode()).hexdigest(),'a034b67f5e1e951bc4742f7f866c906516dd5bfa4acacfef616baf434d714c61')
 def test_actual_ring_sampler_and_forwarding_boundaries_on_both_json_runtimes(self):
  source=(ROOT/FIXTURE).read_text();collector=member(source,'  static final class ReadingZoomTrace {');view=trace_manifest()['paths'][FIXTURE]['insertions'][2]['inserted'];callback=member(source,'@Override public void onScrollChanged(org.mozilla.geckoview.GeckoSession own,org.mozilla.geckoview.GeckoSession.ScrollPositionUpdate update)');body=callback[callback.index('{'):]
  program=JAVA_HOST.replace('/*COLLECTOR*/',collector).replace('/*VIEW*/',view).replace('/*CALLBACK*/',body)
  java=os.environ.get('PROFILE_JAVA') or shutil.which('java');self.assertTrue(java,'JDK required')
  choices=[ROOT/'work/profile-host/json.jar',ROOT/'work/profile-host/android-json.jar'];self.assertTrue(all(p.is_file() for p in choices),'Both pinned JSON jars required')
  reports=[]
  for jar in choices:
   self.assertIn(hashlib.sha256(jar.read_bytes()).hexdigest(),PINS)
   with tempfile.TemporaryDirectory(prefix='reading-trace-host-') as tmp:
    p=pathlib.Path(tmp);f=p/'ReadingTraceHost.java';f.write_text(program)
    c=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(p),str(f)],capture_output=True,text=True);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
    r=subprocess.run([java,'-cp',str(p)+os.pathsep+str(jar),'ReadingTraceHost'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr);v=json.loads(r.stdout);self.assertEqual(v['checks'],v['passed']);self.assertGreaterEqual(v['checks'],12);reports.append(v)
  out=ROOT/'work/profile-host/reading-zoom-trace-host.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(dict(schema=1,actualAndroidExecution=False,actualGeckoExecution=False,reports=reports),indent=2)+'\n')

JAVA_HOST=r'''import org.json.*;
public final class ReadingTraceHost {
 static int checks;static void check(boolean value,String name){checks++;if(!value)throw new AssertionError(name);}
 /*COLLECTOR*/
 static class Base {int forwarded;float factor;public void zoomBy(float v){forwarded++;factor=v;}}
 static class Boundary extends Base {/*VIEW*/}
 static class Update {float scrollX=12,scrollY=18,zoom=11.18f;}
 interface Prior {void onScrollChanged(Object own,Update update);}
 static class Case {float scrollX,scrollY,zoom;int updates;ReadingZoomTrace trace;Prior priorDelegate;}
 static class NativeBoundary {Case test=new Case();long serial=1,run=1;int observed;float observedZoom;void recordReadingZoomNative(long s,Case c,float value){observed++;observedZoom=value;}void onUpdate(Object own,Update update)/*CALLBACK*/}
 public static void main(String[] args)throws Exception{
  final long[] ticks={0};ReadingZoomTrace t=new ReadingZoomTrace(()->++ticks[0]);Boundary view=new Boundary();view.zoomBy(.99f);check(view.forwarded==1&&view.factor==.99f&&ticks[0]==0,"default forwards once without observer");
  view.readingZoomTraceCurrent=()->true;view.readingZoomRequest=f->t.add(0,f,11,0,1,414,1080,1,false,-1,-1);view.zoomBy(.979f);check(view.forwarded==2&&t.size==1&&ticks[0]==1,"enabled request still forwards once");
  check(t.snapshot()[0][10]==-1&&t.snapshot()[0][11]==-1,"focus attachment unknown before existing sample");
  view.readingZoomTraceCurrent=()->false;view.zoomBy(1.1f);check(view.forwarded==3&&t.size==1&&view.readingZoomRequest==null,"stale owner retires observer without record");
  NativeBoundary n=new NativeBoundary();final int[] forwards={0};Object own=new Object();Update update=new Update();n.test.priorDelegate=(o,u)->{check(o==own&&u==update,"same callback arguments");forwards[0]++;};n.onUpdate(own,update);check(n.test.updates==1&&n.observed==0&&forwards[0]==1,"default native callback unchanged");n.test.trace=t;n.onUpdate(own,update);check(n.test.updates==2&&n.observed==1&&forwards[0]==2&&n.observedZoom==update.zoom,"enabled native callback observes and forwards once");n.run=2;n.onUpdate(own,update);check(n.observed==1&&forwards[0]==3,"stale callback still forwards original once");
  ReadingZoomTrace s=new ReadingZoomTrace(()->++ticks[0]);s.sample(11,11,1,414,1080,1,false,1,1);long before=ticks[0];s.sample(11,11,1,414,1080,1,false,1,1);check(s.size==1&&ticks[0]==before,"unchanged sample no clock or row");s.sample(11,11,1,414,1080,1,false,0,1);check(s.size==2,"focus change retained");s.sample(11,11,1,414,1080,1,false,0,0);check(s.size==3,"attachment change retained");s.sample(11,11,1,393,1024,2,true,0,0);check(s.size==4,"geometry active attempt change retained");
  ReadingZoomTrace ring=new ReadingZoomTrace(()->++ticks[0]);for(int i=0;i<100;i++)ring.add(1,0,0,i,1,414,1080,i,false,1,1);check(ring.size==64&&ring.dropped==36&&ring.snapshot()[0][4]==36&&ring.snapshot()[63][4]==99,"bounded chronological64 ring");ReadingZoomTrace priority=new ReadingZoomTrace(()->++ticks[0]);priority.add(0,.97,11,0,1,414,1080,1,false,1,1);for(int i=0;i<100;i++)priority.add(1,0,0,i,1,414,1080,i,false,1,1);check(priority.size==64&&priority.snapshot()[0][0]==0&&priority.snapshot()[0][2]==.97&&priority.droppedRequest==0&&priority.droppedObservation==37,"requests survive observer overflow");ReadingZoomTrace fullRequests=new ReadingZoomTrace(()->++ticks[0]);for(int i=0;i<65;i++)fullRequests.add(0,i,11,0,1,414,1080,i,false,1,1);check(fullRequests.size==64&&fullRequests.droppedRequest==1&&fullRequests.snapshot()[0][2]==1,"all request overflow disclosed");fullRequests.add(1,0,0,11,1,414,1080,1,false,1,1);check(fullRequests.droppedObservation==1&&fullRequests.droppedRequest==1&&fullRequests.snapshot()[0][0]==0,"observations cannot evict all-request buffer");double[][] copied=ring.snapshot();copied[0][4]=999;check(ring.snapshot()[0][4]==36,"snapshot cannot mutate ring");before=ticks[0];ring.add(0,Double.NaN,0,0,1,414,1080,1,false,1,1);check(ring.invalid==1&&ring.size==64&&ticks[0]==before,"nonfinite observer value does not reach serialization");JSONObject out=ring.json();check(out.length()==12&&out.getBoolean("partial")&&!out.getBoolean("applicationAcceptance")&&out.getInt("capacity")==64&&out.getJSONArray("entries").length()==64,"numeric bounded report");JSONArray rows=out.getJSONArray("entries");for(int i=0;i<rows.length();i++){JSONArray row=rows.getJSONArray(i);check(row.length()==12,"fixed numeric columns");for(int j=0;j<row.length();j++)check(row.get(j) instanceof Number&&Double.isFinite(row.getDouble(j)),"finite numbers only");}System.out.println("{\"checks\":"+checks+",\"passed\":"+checks+"}");
 }
}'''
if __name__=='__main__':unittest.main()
