"""Production fit completion with recorded native measurements, not a renderer.

The zoom boundary records requested factors and never changes measured scale.
Only a separately supplied native measurement may let the controller align.
"""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest
from fingerprint_source_compatibility import reading_preservation_bytes
from reading_zoom_trace_contract import original_reading_fixture_bytes
from reading45_source_compatibility import reading45_source_bytes
from experience46_source_compatibility import experience46_source_bytes

ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
HOST_ROOT=ROOT/'tests/browser-reading-host'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
OLD_RESTORE='''    float current=session.web.getScale(),target=BrowserReadingPolicy.target(width,density(),viewportWidth,choice());
    if(current<=0||target<=0)return;float factor=target/current;
    if(Math.abs(factor-1)>.015f&&restoreAttempts++<3){session.web.zoomBy(Math.max(.01f,Math.min(100f,factor)));session.handler.removeCallbacks(restore);session.handler.postDelayed(restore,500);}
    else if(Math.abs(factor-1)<=.015f&&alignLeft){alignLeft=false;session.web.alignReadingLeft(fitY);fitY=Float.NaN;}'''
NEW_RESTORE='''    boolean nativeFit=alignLeft&&session.web.requiresViewportMeasurement();
    // setReadingLayout may retain a nearby value; fit that applied layout.
    float current=session.web.getScale(),target=BrowserReadingPolicy.target(width,density(),viewportWidth,nativeFit?session.web.readingLayout:choice());
    if(current<=0||target<=0)return;float factor=target/current;
    // Both measurements include readingLayout; undo it once to compare the
    // rendered page width with the native view before consuming a fit anchor.
    boolean atTarget=alignLeft&&(nativeFit?BrowserReadingPolicy.fitted(width,current,viewportWidth,session.web.readingLayout):Math.abs(factor-1)<=.015f);
    boolean correction=nativeFit?!atTarget:Math.abs(factor-1)>.015f;
    if(correction&&restoreAttempts++<3){session.web.zoomBy(Math.max(.01f,Math.min(100f,factor)));session.handler.removeCallbacks(restore);session.handler.postDelayed(restore,500);}
    else if(atTarget){alignLeft=false;session.web.alignReadingLeft(fitY);fitY=Float.NaN;}'''
ORIGINAL_READING_SHA='8d3c7ae23d86378e2125d46a62c024178cc0d424f28c79ae488e45e72662b1c7'
ORIGINAL_POLICY_SHA='aa20d57539f7581691d0261fb16b793a5898cea8a4a4412425de1ff20e1d42a2'
ORIGINAL_PROTECTED={
 'tests/gecko/GeckoIntegrationTestActivity.java':'7d6cc589a2718f629568205c79c290ef713d745b05a62a700a72451846c8d814',
 'tests/gecko/run_device.py':'019bc8e8b8e61def3d6fe87fe70d9eb7a87a3a556d86b921489331f9f4757e5d',
 'app/src/main/java/local/pocketchat/GeckoWebView.java':'0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10',
 'tests/browser-reading-host/local/pocketchat/BrowserReadingHostTest.java':'8e29601536facc3c49a64346b523fdcc671159cfd2f8d414ec72a129a7bd9a3e',
 'tests/browser-reading-host/local/pocketchat/ChatSession.java':'366b6de6e82de8ff8f71226bfb0f15a0125fcb66930f97e82e8c993a222c67ff',
}
FITTED='''  static boolean fitted(int width,float scale,float viewport,float layout){
    if(width<=0||!Float.isFinite(scale)||scale<=0||!Float.isFinite(viewport)||viewport<=0||!Float.isFinite(layout)||layout<=0)return false;
    double residual=Math.abs((double)scale*viewport/layout-width);
    // clientWidth is integral. Allow its sub-CSS-pixel rounding, while keeping
    // both the native width error below 6px and the page edge within 1 CSS px.
    return residual<6&&residual<=scale;
  }
'''

JAVA_HOST=r'''
package local.pocketchat;
import java.util.*;
import android.view.MotionEvent;
public final class ReadingFitCompletionHost {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static boolean near(float a,float b){return Math.abs(a-b)<.00001f;}
  static BrowserReading setup(ChatSession s,float measured,float viewport,float choice,float layout){
    s.web.scale=measured;s.web.scrollY=320;s.web.measuredViewportRequired=true;s.web.readingLayout=layout;s.context.density=2.6086957f;s.prefs.putFloat(BrowserReadingPolicy.ZOOM_KEY,choice);
    BrowserReading r=new BrowserReading(s);s.web.reading=r;r.configure(true);r.started(s.web.url);r.visible(s.web.url);r.viewportMeasured(viewport);s.handler.tasks.clear();return r;
  }
  public static void main(String[] args){
    ChatSession actual=new ChatSession(new ChatSession.Prefs());BrowserReading r=setup(actual,2.6332219f,414,1,1);r.fit();r.restoreScale();
    check("Actual 0aeb 1 percent residual requests a real correction without consuming fit",actual.web.zoomCalls==1&&r.restoreAttempts==1&&r.alignLeft&&actual.web.alignCalls==0&&r.fitY==320);
    check("Native zoom boundary records factor and does not fabricate scale convergence",near(actual.web.lastFactor,1080f/414/2.6332219f)&&actual.web.scale==2.6332219f);
    actual.web.scale=2.62f;r.restoreScale();
    check("A partial native response still beyond the original edge bound cannot confirm fit",actual.web.zoomCalls==2&&actual.web.alignCalls==0&&r.alignLeft&&r.fitY==320);
    actual.web.scale=1080f/414;actual.web.scrollY=357;r.restoreScale();
    check("A measured converged native width consumes the intent once and restores saved Y",actual.web.zoomCalls==2&&actual.web.alignCalls==1&&!r.alignLeft&&Float.isNaN(r.fitY)&&actual.web.scrollY==320);
    r.restoreScale();check("Repeated restore after convergence does not realign or zoom",actual.web.zoomCalls==2&&actual.web.alignCalls==1);
    ChatSession ignored=new ChatSession(new ChatSession.Prefs());BrowserReading ri=setup(ignored,2.6332219f,414,1,1);ri.fit();
    for(int i=0;i<8;i++)ri.restoreScale();
    check("Ignored small pinches stop at the original three actual requests without false completion",ignored.web.zoomCalls==3&&ignored.web.alignCalls==0&&ri.alignLeft&&ri.fitY==320&&ignored.web.scale==2.6332219f);
    ChatSession partial=new ChatSession(new ChatSession.Prefs());BrowserReading rp=setup(partial,2.6332219f,414,1,1);rp.fit();rp.restoreScale();partial.web.scale=2.628f;rp.restoreScale();partial.web.scale=2.624f;rp.restoreScale();partial.web.scale=2.62f;rp.restoreScale();
    check("Exhausted partial responses cannot turn the attempt limit into confirmation",partial.web.zoomCalls==3&&partial.web.alignCalls==0&&rp.alignLeft&&rp.fitY==320);
    ChatSession held=new ChatSession(new ChatSession.Prefs());BrowserReading rh=setup(held,2.6332219f,414,1,1);rh.fit();rh.touch(new MotionEvent(MotionEvent.ACTION_DOWN,1,100,100));held.web.scale=1080f/414;rh.restoreScale();rh.nativeScaleMeasured();held.handler.drain();
    check("A new real touch cancels the old fit even if a late measurement reaches target",held.web.zoomCalls==0&&held.web.alignCalls==0&&!rh.alignLeft&&!rh.restoreAllowed&&Float.isNaN(rh.fitY));
    rh.touch(new MotionEvent(MotionEvent.ACTION_UP,1,100,100));rh.nativeScaleMeasured();held.handler.drain();
    check("Touch UP and late metrics cannot revive a canceled fit",held.web.alignCalls==0&&held.web.zoomCalls==0);
    ChatSession canceled=new ChatSession(new ChatSession.Prefs());BrowserReading rc=setup(canceled,2.6332219f,414,1,1);rc.fit();rc.restoreScale();rc.cancelPosition();canceled.web.scale=1080f/414;rc.restoreScale();
    check("Cancellation after a requested pinch cannot later confirm its fit",canceled.web.zoomCalls==1&&canceled.web.alignCalls==0&&!rc.alignLeft&&Float.isNaN(rc.fitY));
    ChatSession document=new ChatSession(new ChatSession.Prefs());BrowserReading rd=setup(document,2.6332219f,414,1,1);rd.fit();rd.restoreScale();document.web.url="https://chatgpt.com/c/new";document.web.scrollY=900;rd.started(document.web.url);rd.visible(document.web.url);document.web.scale=1080f/414;rd.restoreScale();
    check("A new document discards the old anchor and waits for its own viewport",document.web.alignCalls==0&&rd.viewportWidth==0&&Float.isNaN(rd.fitY));
    rd.viewportMeasured(414);rd.restoreScale();check("Fresh document geometry aligns its current Y rather than an old fit anchor",document.web.alignCalls==1&&document.web.scrollY==900&&Float.isNaN(document.web.lastAlignedY));
    ChatSession active=new ChatSession(new ChatSession.Prefs());BrowserReading ra=setup(active,2.6332219f,414,1,1);ra.fit();active.web.nativeZoomActive=true;ra.restoreScale();
    check("An in-flight native gesture neither overlaps correction nor consumes the anchor",active.web.zoomCalls==0&&active.web.alignCalls==0&&ra.restoreAttempts==0&&ra.alignLeft);
    active.web.nativeZoomActive=false;ra.restoreScale();check("UP without a changed native measurement is not completion",active.web.zoomCalls==1&&active.web.alignCalls==0&&ra.alignLeft);
    ChatSession missing=new ChatSession(new ChatSession.Prefs());BrowserReading rm=setup(missing,2.6332219f,0,1,1);rm.restoreScale();
    check("Production measured backend cannot fall back when viewport is missing",missing.web.zoomCalls==0&&missing.web.alignCalls==0&&rm.alignLeft);
    ChatSession unmeasured=new ChatSession(new ChatSession.Prefs());BrowserReading ru=setup(unmeasured,2.6332219f,414,1,1);unmeasured.web.nativeMeasured=false;ru.restoreScale();
    check("DOM width cannot replace missing native compositor measurement",unmeasured.web.zoomCalls==0&&unmeasured.web.alignCalls==0&&ru.alignLeft);
    ChatSession manual=new ChatSession(new ChatSession.Prefs());BrowserReading rz=setup(manual,1.5f*(1080f/414)*1.0094f,414,1.5f,1);rz.restoreScale();
    check("Ordinary manual magnification retains its original 1.5 percent tolerance",manual.web.zoomCalls==0&&manual.web.alignCalls==0&&!rz.alignLeft);
    rz.choose(1.5f);manual.web.scale=1.5f*(1080f/414)*1.03f;rz.restoreScale();check("Ordinary manual magnification still corrects a larger residual",manual.web.zoomCalls==1);
    ChatSession generic=new ChatSession(new ChatSession.Prefs());BrowserReading rg=setup(generic,3,0,1,1);generic.web.measuredViewportRequired=false;generic.context.density=3;rg.restoreScale();
    check("Generic density fallback retains its preexisting behavior without claiming measured precision",generic.web.zoomCalls==0&&generic.web.alignCalls==1);
    for(float layout:new float[]{.6f,.8f,1f}){
      float dom=414/layout,viewport=dom*layout,target=1080/dom;
      ChatSession small=new ChatSession(new ChatSession.Prefs());BrowserReading rs=setup(small,target*1.01f,viewport,layout,layout);rs.fitY=320;rs.restoreScale();
      check("Layout "+layout+" measures one surface scale and requests correction",small.web.zoomCalls==1&&small.web.alignCalls==0&&rs.alignLeft);
      small.web.scale=target;rs.restoreScale();check("Layout "+layout+" accepts only a newly measured fitted width",small.web.alignCalls==1&&!rs.alignLeft&&small.web.scrollY==320);
    }
    for(float[] pair:new float[][]{{.6009f,.6f},{.6f,.6009f}}){
      float choice=pair[0],layout=pair[1],oldTarget=1080f/414*choice,fitTarget=1080f/414*layout;
      ChatSession rounded=new ChatSession(new ChatSession.Prefs());BrowserReading rr=setup(rounded,oldTarget,414,choice,layout);rr.fitY=320;rr.restoreScale();
      check("Approximate unapplied choice "+choice+" targets actual layout "+layout+" with nontrivial correction",rounded.web.zoomCalls==1&&rounded.web.alignCalls==0&&rr.alignLeft&&Math.abs(rounded.web.lastFactor-1)>.001f&&near(rounded.web.lastFactor,fitTarget/oldTarget));
      rounded.web.scale=fitTarget;rr.restoreScale();check("Actual layout target confirms fit despite unapplied choice "+choice,rounded.web.zoomCalls==1&&rounded.web.alignCalls==1&&!rr.alignLeft&&rounded.web.scrollY==320);
    }
    for(int[] geometry:new int[][]{{945,362},{1024,393},{1128,432},{1080,414}}){
      check("Actual clientWidth rounding remains within original edge tolerance at "+geometry[0],BrowserReadingPolicy.fitted(geometry[0],2.6086957f,geometry[1],1));
    }
    check("The original physical six-pixel boundary remains strict",!BrowserReadingPolicy.fitted(1080,6,181,1));
    check("The original one CSS pixel edge boundary remains inclusive",BrowserReadingPolicy.fitted(1080,3,361,1)&&!BrowserReadingPolicy.fitted(1080,3,361.01f,1));
    for(float invalid:new float[]{0,-1,Float.NaN,Float.POSITIVE_INFINITY}){
      check("Invalid native scale is not fitted "+invalid,!BrowserReadingPolicy.fitted(1080,invalid,414,1));
      check("Invalid viewport is not fitted "+invalid,!BrowserReadingPolicy.fitted(1080,2.6086957f,invalid,1));
      check("Invalid layout is not fitted "+invalid,!BrowserReadingPolicy.fitted(1080,2.6086957f,414,invalid));
    }
    check("An absent native view width is not fitted",!BrowserReadingPolicy.fitted(0,2.6086957f,414,1));
    StringBuilder out=new StringBuilder("{\"passed\":"+checks.size()+",\"checks\":[");for(int i=0;i<checks.size();i++){if(i>0)out.append(',');out.append('\"').append(checks.get(i)).append('\"');}System.out.println(out.append("]}"));
  }
}
'''

def java_paths():
 java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
 if not java:raise unittest.SkipTest('Java runtime unavailable')
 javac=Path(java).with_name('javac')
 if not javac.exists():raise unittest.SkipTest('Java compiler unavailable')
 return java,javac

def execute(reading=None,policy=None):
 java,javac=java_paths()
 with tempfile.TemporaryDirectory(prefix='reading-fit-completion-') as temp:
  target=Path(temp);sources=[]
  for name,content in [('BrowserReading.java',reading),('BrowserReadingPolicy.java',policy),('BrowserDisplay.java',None)]:
   p=target/name;p.write_text(content if content is not None else (PRODUCTION/name).read_text());sources.append(p)
  double=(HOST_ROOT/'local/pocketchat/ChatSession.java').read_text()
  old='zoomCalls++;scale*=factor;scrollY+=37;if(reading!=null)reading.scaled(scale);'
  if double.count(old)!=1:raise ValueError('Exact host zoom boundary changed')
  double=double.replace(old,'zoomCalls++;lastFactor=factor;',1).replace('float scale=3,','float lastFactor,scale=3,',1)
  # Execute the exact production layout quantization guard. These cases never
  # require a surface relayout, whose Android boundary remains out of scope.
  guard='if(!enabled)return false;float next=Math.min(1,BrowserReadingPolicy.bounded(choice));if(Math.abs(next-readingLayout)<.001f)return false;'
  if (PRODUCTION/'GeckoWebView.java').read_text().count(guard)!=1:raise ValueError('Actual layout quantization guard changed')
  double=double.replace('int width=1080,','boolean enabled=true;int width=1080,',1).replace('boolean setReadingLayout(float choice){return false;}','boolean setReadingLayout(float choice){'+guard+'throw new AssertionError("Unexpected Android surface relayout");}',1)
  p=target/'ChatSession.java';p.write_text(double);sources.append(p)
  p=target/'ReadingFitCompletionHost.java';p.write_text(JAVA_HOST);sources.append(p)
  sources += [HOST_ROOT/'android/os/SystemClock.java',HOST_ROOT/'android/view/MotionEvent.java']
  compile_result=subprocess.run([str(javac),'-encoding','UTF-8','-d',temp,*map(str,sources)],capture_output=True,text=True)
  if compile_result.returncode:raise AssertionError(compile_result.stderr)
  return subprocess.run([str(java),'-cp',temp,'local.pocketchat.ReadingFitCompletionHost'],capture_output=True,text=True)

class ReadingFitCompletionTests(unittest.TestCase):
 def test_original_controller_and_oracle_preservation(self):
  reading=reading45_source_bytes((PRODUCTION/'BrowserReading.java').read_bytes(),'app/src/main/java/local/pocketchat/BrowserReading.java').decode();self.assertEqual(reading.count(NEW_RESTORE),1)
  self.assertEqual(sha(reading.replace(NEW_RESTORE,OLD_RESTORE,1).encode()),ORIGINAL_READING_SHA)
  policy=reading45_source_bytes((PRODUCTION/'BrowserReadingPolicy.java').read_bytes(),'app/src/main/java/local/pocketchat/BrowserReadingPolicy.java').decode();self.assertEqual(policy.count(FITTED),1)
  self.assertEqual(sha(policy.replace(FITTED,'',1).encode()),ORIGINAL_POLICY_SHA)
  for name,digest in ORIGINAL_PROTECTED.items():
   raw=(ROOT/name).read_bytes()
   if name=='tests/gecko/run_device.py':raw=experience46_source_bytes(raw,name)
   if name=='app/src/main/java/local/pocketchat/GeckoWebView.java':raw=reading_preservation_bytes(raw)
   if name in ('tests/gecko/GeckoIntegrationTestActivity.java','tests/gecko/run_device.py'):raw=original_reading_fixture_bytes(raw,name)
   self.assertEqual(sha(raw),digest)
  self.assertEqual((PRODUCTION/'GeckoWebView.java').read_text().count('boolean requiresViewportMeasurement(){return true;}'),1)

 def test_fingerprint_inverse_cannot_hide_a_reading_geometry_change(self):
  raw=(PRODUCTION/'GeckoWebView.java').read_bytes();needle=b'Math.abs(next-readingLayout)<.001f'
  self.assertEqual(raw.count(needle),1)
  with self.assertRaises(ValueError):reading_preservation_bytes(raw.replace(needle,b'Math.abs(next-readingLayout)<.002f',1))

 def test_measured_completion_and_failure_controls(self):
  result=execute();self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads(result.stdout)
  report.update({'scope':'Unmodified production controller/policy, recorded zoom requests and separately injected measurements; no Android/APZ renderer','actualAndroidExecution':False,'smallNativePinchAcceptance':False,'sourceSha256':{name:sha((PRODUCTION/name).read_bytes()) for name in ['BrowserReading.java','BrowserReadingPolicy.java','GeckoWebView.java']}})
  output=os.environ.get('READING_FIT_COMPLETION_REPORT')
  if output:Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  self.assertEqual(report['passed'],48)

 def test_completion_mutations_are_rejected(self):
  reading=reading45_source_bytes((PRODUCTION/'BrowserReading.java').read_bytes(),'app/src/main/java/local/pocketchat/BrowserReading.java').decode();policy=reading45_source_bytes((PRODUCTION/'BrowserReadingPolicy.java').read_bytes(),'app/src/main/java/local/pocketchat/BrowserReadingPolicy.java').decode()
  mutants=[('old relative completion',reading.replace(NEW_RESTORE,OLD_RESTORE,1),policy),('consume before measured fit',reading.replace('else if(atTarget){','else if(alignLeft){',1),policy),('ignore layout scaling',reading,policy.replace('(double)scale*viewport/layout-width','(double)scale*viewport-width',1)),('relaxed edge',reading,policy.replace('residual<=scale','residual<=scale*5',1)),('target unapplied approximate choice',reading.replace('viewportWidth,nativeFit?session.web.readingLayout:choice()','viewportWidth,choice()',1),policy)]
  outcomes=[]
  for label,r,p in mutants:
   with self.subTest(label=label):
    result=execute(r,p);self.assertNotEqual(result.returncode,0,'Mutation escaped: '+label)
    self.assertIn('AssertionError',result.stderr)
    outcomes.append({'mutation':label,'returnCode':result.returncode,'stderr':result.stderr})
  output=os.environ.get('READING_FIT_COMPLETION_MUTATIONS_REPORT')
  if output:Path(output).write_text(json.dumps({'rejected':len(outcomes),'mutations':outcomes,'scope':'Controlled modified source counterexamples; not Android observations'},indent=2)+'\n')

if __name__=='__main__':unittest.main()
