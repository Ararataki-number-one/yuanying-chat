"""Recorded native measurements and bounded restoration ownership, not Gecko.

The native zoom boundary only records requests. Each compositor response below
is independently supplied; the clock/queue honor actual scheduled delays.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'
HOST = ROOT / 'tests/browser-reading-host'

JAVA = r'''
package local.pocketchat;
import java.util.*;
import android.os.SystemClock;
import android.view.MotionEvent;
public final class ReadingPrecision45Host {
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static float scale(float relative){return 1080f/414*relative;}
  static BrowserReading setup(ChatSession s,float measured,float choice){
    SystemClock.time=10000;s.web.measuredViewportRequired=true;s.web.scale=measured;s.prefs.putFloat(BrowserReadingPolicy.ZOOM_KEY,choice);
    BrowserReading r=new BrowserReading(s);s.web.reading=r;r.configure(true);r.started(s.web.url);r.visible(s.web.url);r.viewportMeasured(414);s.handler.clear();return r;
  }
  static void measure(ChatSession s,BrowserReading r,float measured){s.web.scale=measured;r.scaled(measured);}
  static void three(ChatSession s,BrowserReading r){
    r.restoreScale();SystemClock.time+=500;s.web.scale=scale(3.9f);r.restoreScale();SystemClock.time+=500;s.web.scale=scale(4.5f);r.restoreScale();
    check("Three original requests use independently supplied prior samples",s.web.zoomCalls==3&&r.restoreAttempts==3&&!r.scaleRestore.fineUsed);
  }
  public static void main(String[] args){
    check("Actual failed measurement remains outside precise stored choice",!BrowserReadingPolicy.restored(1080,11.12214183807373f,414,4.2f));
    check("The previous relative tolerance accepted the actual failed value",Math.abs((1080f/414*4.2f)/11.12214183807373f-1)<=.015f);
    check("Actual unclamped zoom above maximum is never mistaken for maximum choice",!BrowserReadingPolicy.restored(1080,scale(21),414,20));
    for(float value:new float[]{0,-1,Float.NaN,Float.POSITIVE_INFINITY}){
      check("Invalid native measurement is not precise "+value,!BrowserReadingPolicy.restored(1080,value,414,4.2f));
      check("Invalid viewport is not precise "+value,!BrowserReadingPolicy.restored(1080,scale(4.2f),value,4.2f));
    }
    check("Missing native view width cannot confirm precision",!BrowserReadingPolicy.restored(0,scale(4.2f),414,4.2f));
    ChatSession precise=new ChatSession(new ChatSession.Prefs());BrowserReading pr=setup(precise,scale(4.2f),4.2f);pr.restoreScale();
    check("A precise measured choice issues zero native requests",precise.web.zoomCalls==0&&pr.restoreAttempts==0);
    ChatSession actual=new ChatSession(new ChatSession.Prefs());BrowserReading ar=setup(actual,scale(3.8f),4.2f);three(actual,ar);
    measure(actual,ar,11.12214183807373f);actual.handler.advance(120);
    check("An early 120ms callback neither requests nor spends the three-request budget",actual.web.zoomCalls==3&&ar.restoreAttempts==3&&actual.handler.nextDelay()==380);
    actual.handler.advance(379);check("Primary observation remains at the original 500ms floor",actual.web.zoomCalls==3);
    actual.handler.advance(1);
    check("Actual terminal residual after three progressing requests permits exactly one fine correction",actual.web.zoomCalls==4&&ar.restoreAttempts==4&&ar.scaleRestore.fineUsed&&actual.web.scale==11.12214183807373f);
    check("Fine request does not fabricate native convergence or leave a polling task",actual.handler.tasks.isEmpty()&&!BrowserReadingPolicy.restored(1080,actual.web.scale,414,4.2f));
    for(int i=0;i<5;i++){measure(actual,ar,scale(4.21f+i*.001f));actual.handler.advance(500);}
    check("Subsequent changed native samples cannot request a fifth pinch",actual.web.zoomCalls==4&&actual.handler.tasks.isEmpty());
    ChatSession getter=new ChatSession(new ChatSession.Prefs());BrowserReading gr=setup(getter,scale(3.8f),4.2f);three(getter,gr);
    getter.web.scale=11.12214183807373f;getter.handler.advance(500);
    check("The original 500ms probe accepts a fresh getter value when same-zoom callback was suppressed",getter.web.zoomCalls==4&&gr.scaleRestore.fineUsed);
    ChatSession ignored=new ChatSession(new ChatSession.Prefs());BrowserReading ir=setup(ignored,11.12214183807373f,4.2f);
    ir.restoreScale();ignored.handler.advance(500);ignored.handler.advance(500);ignored.handler.advance(500);
    check("Three ignored native requests stop without a fourth or an endless timer",ignored.web.zoomCalls==3&&ir.restoreAttempts==3&&ignored.handler.tasks.isEmpty());
    measure(ignored,ir,ignored.web.scale);ignored.handler.advance(500);
    check("No-progress callbacks cannot rearm a spent original observation",ignored.web.zoomCalls==3&&ignored.handler.tasks.isEmpty());
    ChatSession worse=new ChatSession(new ChatSession.Prefs());BrowserReading wr=setup(worse,scale(3.8f),4.2f);three(worse,wr);measure(worse,wr,scale(4.6f));worse.handler.advance(500);
    check("A changed but worse native response cannot authorize fine correction",worse.web.zoomCalls==3&&worse.handler.tasks.isEmpty());
    ChatSession large=new ChatSession(new ChatSession.Prefs());BrowserReading lr=setup(large,scale(3.8f),4.2f);three(large,lr);measure(large,lr,scale(4.4f));large.handler.advance(500);
    check("An improving residual above three percent cannot authorize fine correction",large.web.zoomCalls==3&&large.handler.tasks.isEmpty());
    ChatSession expired=new ChatSession(new ChatSession.Prefs());BrowserReading er=setup(expired,scale(3.8f),4.2f);three(expired,er);SystemClock.time=13001;measure(expired,er,11.12214183807373f);expired.handler.drain();
    check("The three-second first-request window cannot be restarted by a late sample",expired.web.zoomCalls==3&&expired.handler.tasks.isEmpty());
    ChatSession active=new ChatSession(new ChatSession.Prefs());BrowserReading vr=setup(active,scale(3.8f),4.2f);three(active,vr);active.web.nativeZoomActive=true;measure(active,vr,11.12214183807373f);active.handler.advance(500);
    check("An active native pinch cannot overlap or spend the single fine budget",active.web.zoomCalls==3&&!vr.scaleRestore.fineUsed);
    active.web.nativeZoomActive=false;measure(active,vr,active.web.scale);active.handler.advance(120);
    check("A subsequent current native sample can complete the bounded fine admission",active.web.zoomCalls==4&&vr.scaleRestore.fineUsed);
    for(String retirement:new String[]{"touch","document","viewport","choice","width","epoch","url"}){
      ChatSession s=new ChatSession(new ChatSession.Prefs());BrowserReading r=setup(s,scale(3.8f),4.2f);three(s,r);BrowserReading.ScaleRestore old=r.scaleRestore;
      if(retirement.equals("touch")){r.touch(new MotionEvent(MotionEvent.ACTION_DOWN,1,100,100));r.touch(new MotionEvent(MotionEvent.ACTION_UP,1,100,100));}
      if(retirement.equals("document")){s.web.url="https://chatgpt.com/c/new";r.started(s.web.url);r.visible(s.web.url);}
      if(retirement.equals("viewport")){r.viewportMeasured(413);r.viewportMeasured(414);}
      if(retirement.equals("choice")){r.choose(4.3f);s.handler.clear();}
      if(retirement.equals("width")){s.web.size(1000,1600);}
      if(retirement.equals("epoch"))s.navigationEpoch++;
      if(retirement.equals("url"))s.web.url="https://chatgpt.com/c/another";
      measure(s,r,11.12214183807373f);
      if(retirement.equals("choice"))s.handler.clear();else s.handler.advance(500);
      check("Old fine intent cannot survive changed "+retirement,!old.fineUsed&&s.web.zoomCalls==3&&(r.scaleRestore!=old||old.invalid||!old.current(r)));
    }
    ChatSession fresh=new ChatSession(new ChatSession.Prefs());BrowserReading fr=setup(fresh,scale(3.8f),4.2f);three(fresh,fr);BrowserReading.ScaleRestore old=fr.scaleRestore;fr.choose(4.3f);fresh.handler.advance(120);
    check("Explicit new choice owns a fresh primary request rather than reviving old fine",fresh.web.zoomCalls==4&&fr.restoreAttempts==1&&fr.scaleRestore!=old&&!old.fineUsed&&!fr.scaleRestore.fineUsed);
    ChatSession rejected=new ChatSession(new ChatSession.Prefs());BrowserReading rr=setup(rejected,scale(3.8f),4.2f);three(rejected,rr);rejected.web.scale=11.12214183807373f;rejected.web.throwZoom=true;SystemClock.time+=500;
    try{rr.restoreScale();throw new AssertionError("boundary should throw");}catch(IllegalStateException expected){}
    check("A rejected SDK boundary consumes the one fine permission before the call",rejected.web.zoomCalls==4&&rr.scaleRestore.fineUsed&&rr.restoreAttempts==4);
    rejected.web.throwZoom=false;measure(rejected,rr,scale(4.22f));rejected.handler.advance(500);
    check("A failed fine boundary cannot be retried by a callback",rejected.web.zoomCalls==4&&rejected.handler.tasks.isEmpty());
    ChatSession early=new ChatSession(new ChatSession.Prefs());BrowserReading cr=setup(early,scale(3.8f),4.2f);cr.restoreScale();
    SystemClock.time+=300;measure(early,cr,scale(4.2f));
    check("A temporarily precise 300ms callback cannot close or advance the original 500ms observation",!cr.scaleRestore.closed&&cr.precisionAllowed&&early.web.zoomCalls==1&&early.handler.nextDelay()==200);
    early.handler.advance(199);early.web.scale=11.12214183807373f;early.handler.advance(1);
    check("The original 500ms observation reads the latest value instead of the early precise sample",early.web.zoomCalls==2&&cr.restoreAttempts==2&&!cr.scaleRestore.closed);
    early.web.scale=scale(4.2f);early.handler.advance(500);
    check("Observed exact convergence closes the saved restoration intent",cr.scaleRestore.closed&&!cr.precisionAllowed&&early.web.zoomCalls==2);
    SystemClock.time+=30000;measure(early,cr,scale(3.8f));early.handler.drain();
    check("A later non-touch native focus scale cannot revive a closed intent with unused primary budget",early.web.zoomCalls==2&&early.handler.tasks.isEmpty());
    ChatSession same=new ChatSession(new ChatSession.Prefs());BrowserReading sr=setup(same,scale(1.5f)*1.0094f,1.5f);sr.restoreScale();measure(same,sr,scale(1.5f)*1.03f);same.handler.advance(120);
    check("The old manual sample followed by plus-three-percent drift cannot revive without choose",same.web.zoomCalls==0&&!sr.precisionAllowed);
    sr.choose(1.5f);same.handler.advance(120);
    check("The same larger manual residual remains correctable after an explicit new choice",same.web.zoomCalls==1&&sr.restoreAttempts==1);
    ChatSession never=new ChatSession(new ChatSession.Prefs());BrowserReading nr=setup(never,scale(4.2f),4.2f);nr.restoreScale();SystemClock.time+=30000;measure(never,nr,scale(3.8f));never.handler.drain();
    check("An initially precise page does not start an auto-restore window from later focus magnification",never.web.zoomCalls==0&&!nr.precisionAllowed&&never.handler.tasks.isEmpty());
    ChatSession oldWindow=new ChatSession(new ChatSession.Prefs());BrowserReading ow=setup(oldWindow,scale(3.8f),4.2f);ow.restoreScale();SystemClock.time+=30001;measure(oldWindow,ow,scale(4));oldWindow.handler.drain();
    check("The first-request deadline also bounds unused primary requests",oldWindow.web.zoomCalls==1&&ow.restoreAttempts==1&&oldWindow.handler.tasks.isEmpty());
    for(String changed:new String[]{"viewport","choice","width","epoch","url"}){
      ChatSession s=new ChatSession(new ChatSession.Prefs());BrowserReading r=setup(s,scale(3.8f),4.2f);r.restoreScale();BrowserReading.ScaleRestore owner=r.scaleRestore;
      if(changed.equals("viewport"))r.viewportMeasured(413);
      if(changed.equals("choice"))s.prefs.putFloat(BrowserReadingPolicy.ZOOM_KEY,4.3f);
      if(changed.equals("width"))s.web.width=1000;
      if(changed.equals("epoch"))s.navigationEpoch++;
      if(changed.equals("url"))s.web.url="https://chatgpt.com/c/replaced";
      measure(s,r,scale(4));
      if(changed.equals("viewport"))r.viewportMeasured(414);
      if(changed.equals("choice"))s.prefs.putFloat(BrowserReadingPolicy.ZOOM_KEY,4.2f);
      if(changed.equals("width"))s.web.width=1080;
      if(changed.equals("url"))s.web.url="https://chatgpt.com/c/one";
      s.handler.advance(500);r.restoreScale();
      check("An invalidated primary owner cannot revive after changed then returned "+changed,s.web.zoomCalls==1&&r.restoreAttempts==1&&owner.invalid);
    }
    ChatSession geometry=new ChatSession(new ChatSession.Prefs());BrowserReading gg=setup(geometry,scale(3.8f),4.2f);gg.restoreScale();BrowserReading.ScaleRestore prior=gg.scaleRestore;geometry.web.size(1000,1600);gg.viewportMeasured(414);geometry.handler.advance(120);
    check("A genuine physical width change owns a new bounded restoration",geometry.web.zoomCalls==2&&gg.restoreAttempts==1&&gg.scaleRestore!=prior&&gg.scaleRestore.width==1000);
    ChatSession manual=new ChatSession(new ChatSession.Prefs());BrowserReading mr=setup(manual,scale(3.8f),4.2f);mr.restoreScale();mr.touch(new MotionEvent(MotionEvent.ACTION_DOWN,1,100,100));mr.touch(new MotionEvent(MotionEvent.ACTION_POINTER_DOWN,2,100,100));manual.web.scale=scale(4);mr.scaled(manual.web.scale);mr.touch(new MotionEvent(MotionEvent.ACTION_UP,1,100,100));manual.handler.advance(160);float captured=mr.choice();manual.handler.advance(500);manual.web.scale=scale(4.6f);mr.scaled(manual.web.scale);manual.handler.drain();
    check("A real pinch capture retains its original preference save without opening precision restoration",Math.abs(captured-4)<.001&&!mr.precisionAllowed&&manual.web.zoomCalls==1);
    check("Late user APZ after the original 400ms gesture window never pulls back to the intermediate choice",mr.choice()==captured&&manual.web.scale==scale(4.6f)&&manual.web.zoomCalls==1&&manual.handler.tasks.isEmpty());
    ChatSession fit=new ChatSession(new ChatSession.Prefs());BrowserReading fi=setup(fit,2.6332219f,1);fit.web.scrollY=320;fi.fit();fi.restoreScale();fit.handler.advance(500);fit.handler.advance(500);
    check("Original fit ignored pinches still stop after exactly three actual requests",fit.web.zoomCalls==3&&fi.restoreAttempts==3&&fi.alignLeft&&fit.web.alignCalls==0);
    fit.web.scale=1080f/413;fi.viewportMeasured(413);fit.handler.advance(120);
    check("A newly precise viewport still completes the original fit anchor after its three requests",fit.web.zoomCalls==3&&fit.web.alignCalls==1&&!fi.alignLeft&&fit.web.scrollY==320);
    fi.nativeScaleMeasured();fit.handler.advance(500);
    check("Completed fit is not consumed again by a later native measurement",fit.web.zoomCalls==3&&fit.web.alignCalls==1);
    StringBuilder out=new StringBuilder("{\"passed\":"+checks.size()+",\"checks\":[");for(int i=0;i<checks.size();i++){if(i>0)out.append(',');out.append('\"').append(checks.get(i)).append('\"');}System.out.println(out.append("]}"));
  }
}
'''

QUEUE = '''  static class Queue {
    final List<Runnable> tasks=new ArrayList<>();final Map<Runnable,Long> due=new IdentityHashMap<>();
    void removeCallbacks(Runnable r){tasks.removeIf(item->item==r);due.remove(r);}
    void postDelayed(Runnable r,long delay){tasks.add(r);due.put(r,android.os.SystemClock.time+delay);}
    void clear(){tasks.clear();due.clear();}
    long nextDelay(){long result=Long.MAX_VALUE;for(Runnable r:tasks)result=Math.min(result,due.get(r)-android.os.SystemClock.time);return result;}
    void advance(long delay){android.os.SystemClock.time+=delay;drain();}
    void drain(){List<Runnable> pending=new ArrayList<>();for(Runnable r:tasks)if(due.get(r)<=android.os.SystemClock.time)pending.add(r);for(Runnable r:pending)removeCallbacks(r);for(Runnable r:pending)r.run();}
  }
'''


def execute():
    java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:
        raise unittest.SkipTest('Java runtime unavailable')
    javac = Path(java).with_name('javac')
    if not javac.exists():
        raise unittest.SkipTest('Java compiler unavailable')
    original = (HOST / 'local/pocketchat/ChatSession.java').read_text()
    if hashlib.sha256(original.encode()).hexdigest() != '366b6de6e82de8ff8f71226bfb0f15a0125fcb66930f97e82e8c993a222c67ff':
        raise ValueError('Original shared host double changed')
    old_queue = '  static class Queue {final List<Runnable> tasks=new ArrayList<>();void removeCallbacks(Runnable r){tasks.removeIf(item->item==r);}void postDelayed(Runnable r,long delay){tasks.add(r);}void drain(){List<Runnable> pending=new ArrayList<>(tasks);tasks.clear();for(Runnable r:pending)r.run();}}\n'
    if original.count(old_queue) != 1:
        raise ValueError('Original queue boundary changed')
    double = original.replace(old_queue, QUEUE, 1)
    old_zoom = 'zoomCalls++;scale*=factor;scrollY+=37;if(reading!=null)reading.scaled(scale);'
    if double.count(old_zoom) != 1:
        raise ValueError('Original zoom boundary changed')
    double = double.replace(old_zoom, 'zoomCalls++;lastFactor=factor;if(throwZoom)throw new IllegalStateException("Controlled native rejection");', 1)
    double = double.replace('float scale=3,', 'boolean throwZoom;float lastFactor,scale=3,', 1)
    with tempfile.TemporaryDirectory(prefix='reading-precision45-') as temp:
        target = Path(temp)
        sources = []
        for name in ('BrowserReading.java', 'BrowserReadingPolicy.java', 'BrowserDisplay.java'):
            p = target / name
            p.write_bytes((PRODUCTION / name).read_bytes())
            sources.append(p)
        for name, text in [('ChatSession.java', double), ('ReadingPrecision45Host.java', JAVA)]:
            p = target / name
            p.write_text(text)
            sources.append(p)
        sources += [HOST / 'android/os/SystemClock.java', HOST / 'android/view/MotionEvent.java']
        result = subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', temp, *map(str, sources)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return subprocess.run([str(java), '-cp', temp, 'local.pocketchat.ReadingPrecision45Host'], capture_output=True, text=True)


class ReadingPrecision45Tests(unittest.TestCase):
    def test_actual_terminal_and_bounded_late_native_ownership(self):
        result = execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertGreaterEqual(report['passed'], 35)
        report.update(scope='Exact production controller/policy with independent native values and a timed JVM queue; not Android/Gecko', actualAndroidExecution=False, physicalPhoneAcceptance=False)
        output = os.environ.get('READING_PRECISION45_REPORT')
        if output:
            Path(output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
