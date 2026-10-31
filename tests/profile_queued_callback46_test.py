"""Actual queuedChangesReady callback fences on explicit JVM boundary doubles.

The real fixture method and its two owner predicates are compiled unchanged.
Bridge delivery, Session mutation, the timer, VPN lifecycle and observer sampling
are declared boundaries. This is neither Android execution nor route acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from profile_resource_retirement_test import method

ROOT = Path(__file__).resolve().parents[1]
JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')
ACTIVITY = ROOT / 'tests/gecko/GeckoIntegrationTestActivity.java'
VPN = ROOT / 'tests/gecko/QueuedChangesVpn46.java'
OBSERVATION = ROOT / 'tests/gecko/GeckoQueuedChangesObservation.java'
OWNER_GUARD = 'if(!vpn.owns()||!observation.ownsUrl(session.web.getUrl())){vpn.abort();return;}'
TIMER_GUARD = 'if(!vpn.owns()){vpn.abort();return;}'

HOST = r'''package local.pocketchat;
import org.json.*;import java.util.*;import java.util.function.Consumer;import android.os.SystemClock;
class Prefs {
 final Map<String,Object> values=new HashMap<>();int edits;
 Prefs(){values.put("proxy","original-route");}
 Prefs edit(){edits++;return this;}Prefs putString(String k,String v){values.put(k,v);return this;}
 boolean commit(){return true;}String getString(String k,String d){return (String)values.getOrDefault(k,d);}
 boolean contains(String k){return values.containsKey(k);}
}
class Privacy {int level(){return 1;}boolean wantsDesktop(){return false;}}
class Web {String url="http://127.0.0.1:8765/fixture?context=2&action=read&command=4";Object current=new Object();final Map<Object,Object> ports=new HashMap<>();Web(){ports.put(current,new Object());}String getUrl(){return url;}}
class Guard {boolean requiresVpn(){return false;}boolean allowed(){return false;}}
class Timer {Runnable callback;long delay;int posts;void postDelayed(Runnable task,long millis){callback=task;delay=millis;posts++;}}
class ChatSession {
 static ChatSession current;static ChatSession peek(){return current;}
 final Prefs prefs=new Prefs();final Privacy privacy=new Privacy();final Web web=new Web();final Guard guard=new Guard();final Timer handler=new Timer();
 JSONObject pending=J.obj("id","preexisting"),state=J.obj("sentinel","initial");
 int environmentGeneration=3,completed,changes;String environmentId="environment-2";long navigationEpoch=7;
 boolean deleted,navigating=true,connecting=true;
 void changed(){changes++;}void completeReply(JSONObject job,JSONObject result){if(job!=pending||job==null)throw new AssertionError("callback replaced the reply identity");completed++;pending=null;prefs.values.remove("pending");}
}
class DeferredBrowserSettings {
 static int saves,cancels;static boolean save(ChatSession s,int level,boolean desktop){saves++;s.prefs.values.put("nextPrivacyLevel",level);return true;}
 static void cancel(ChatSession s){cancels++;s.prefs.values.remove("nextPrivacyLevel");}
}
class NetworkChanges {static String hash(Object c){return "unchanged-route";}static JSONObject pending(Object c){return J.obj("stillPending",true);}}
class ProfileCatalog {static ProfileCatalog get(Object c){return new ProfileCatalog();}JSONObject item(int slot){return J.obj("waiting",false);}}
class NetworkApplyCoordinator {static final String DEFER="defer";}
class NetworkBridge {
 interface Result {void done(boolean ok,String message,JSONObject snapshot);}
 interface Decision {void required(JSONObject choice,Consumer<String> selected);}
 static Result held;static int calls,choices;static String selected;static JSONObject delivered;
 static void run(Object c,int slot,String action,JSONObject candidate,String baseline,Object expected,Decision decision,Result callback){
  if(slot!=1||!"external".equals(action)||!candidate.optBoolean("requireExternalVpn")||!candidate.optString("proxy").isEmpty())throw new AssertionError("original request changed");
  calls++;held=callback;decision.required(J.obj("token","explicit-choice"),value->{choices++;selected=value;});
 }
 static void deliver(){if(held==null)throw new AssertionError("no saved callback");Result callback=held;held=null;delivered=J.obj("candidateIdentity","actual-callback-object");callback.done(true,"saved pending",delivered);}
 static void reset(){held=null;delivered=null;calls=choices=0;selected=null;DeferredBrowserSettings.saves=DeferredBrowserSettings.cancels=0;}
}
class QueuedChangesVpn46 {
 final GeckoIntegrationTestActivity activity;final ChatSession session;final long command;final int environmentGeneration;final String environment,url;final Object sdk;
 boolean aborted;int aborts,stops,attached;JSONObject snapshot;
 QueuedChangesVpn46(GeckoIntegrationTestActivity a){activity=a;session=a.session;command=a.run;environmentGeneration=session.environmentGeneration;environment=session.environmentId;sdk=session.web.current;url=session.web.getUrl();}
 @VPN_OWNS@
 void abort(){aborted=true;aborts++;}void stopWhenApplied(JSONObject actual){if(actual!=NetworkBridge.delivered)throw new AssertionError("actual callback snapshot was discarded");snapshot=actual;stops++;}JSONObject attach(JSONObject value){attached++;return value;}
}
class GeckoQueuedChangesObservation {
 final GeckoIntegrationTestActivity activity;final ChatSession session;final Web view;final long command,epoch,expires;final int generation;final String environment,url;final Object sdk,port;
 boolean failed,retired;int idles,attached;
 GeckoQueuedChangesObservation(GeckoIntegrationTestActivity a){activity=a;session=a.session;view=session.web;command=a.run;epoch=session.navigationEpoch;expires=10000;generation=session.environmentGeneration;environment=session.environmentId;url=view.getUrl();sdk=view.current;port=view.ports.get(sdk);}
 @OBSERVATION_OWNS@
 void idle(){idles++;}JSONObject attach(JSONObject value){attached++;return value;}
}
class GeckoIntegrationTestActivity {
 ChatSession session=new ChatSession();QueuedChangesVpn46 queuedVpn;int slot=1;long run=46;int events;JSONObject eventValue;
 void event(long serial,String kind,JSONObject value){if(serial!=run||!"queuedChanges".equals(kind))throw new AssertionError("foreign event");events++;eventValue=value;}
 @READY@
}
public final class QueuedCallback46Host {
 static final JSONArray checks=new JSONArray();static int n;
 static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);n++;}
 static final class Case {
  final GeckoIntegrationTestActivity activity=new GeckoIntegrationTestActivity();final ChatSession original=activity.session;final QueuedChangesVpn46 vpn;final GeckoQueuedChangesObservation observation;
  Case(){NetworkBridge.reset();ChatSession.current=original;vpn=new QueuedChangesVpn46(activity);activity.queuedVpn=vpn;observation=new GeckoQueuedChangesObservation(activity);}
  void start(){activity.queuedChangesReady(46,observation,vpn);}
 }
 static String state(ChatSession s){return s.prefs.edits+"|"+s.prefs.values+"|"+s.pending+"|"+s.state+"|"+s.completed+"|"+s.changes+"|"+s.navigating+"|"+s.connecting+"|"+s.handler.posts;}
 static void invalidate(Case c,String kind){
  if(kind.equals("command"))c.activity.run++;
  else if(kind.equals("destroyed"))c.original.deleted=true;
  else if(kind.equals("session")){c.activity.session=new ChatSession();ChatSession.current=c.activity.session;}
  else if(kind.equals("port"))c.original.web.ports.put(c.original.web.current,new Object());
  else if(kind.equals("document"))c.original.navigationEpoch++;
  else if(kind.equals("failed-observation"))c.observation.failed=true;
  else if(kind.equals("expired"))android.os.SystemClock.now=10001;
  else if(kind.equals("vpn-owner"))c.activity.queuedVpn=new QueuedChangesVpn46(c.activity);
  else if(kind.equals("url"))c.original.web.url="http://127.0.0.1:8765/fixture?context=2&action=read&command=5";
  else throw new AssertionError(kind);
 }
 static void entry(String kind){Case c=new Case();invalidate(c,kind);String original=state(c.original),live=state(c.activity.session);c.start();check("entry/"+kind+": original and replacement state unchanged",state(c.original).equals(original)&&state(c.activity.session).equals(live));check("entry/"+kind+": no Bridge/save/cancel/completion",NetworkBridge.calls==0&&DeferredBrowserSettings.saves==0&&DeferredBrowserSettings.cancels==0&&c.original.completed==0&&c.vpn.aborts==1);android.os.SystemClock.now=100;}
 static void late(String kind){Case c=new Case();c.start();check("callback/"+kind+": original explicit deferred request",NetworkBridge.calls==1&&NetworkBridge.choices==1&&"defer".equals(NetworkBridge.selected));invalidate(c,kind);String original=state(c.original),live=state(c.activity.session);int cancelled=DeferredBrowserSettings.cancels;NetworkBridge.deliver();check("callback/"+kind+": late result cannot write either session",state(c.original).equals(original)&&state(c.activity.session).equals(live));check("callback/"+kind+": no cancel/complete/idle/stop or timer",DeferredBrowserSettings.cancels==cancelled&&c.original.completed==0&&c.observation.idles==0&&c.vpn.stops==0&&c.original.handler.posts==0&&c.vpn.aborts==1);android.os.SystemClock.now=100;}
 static void timer(String kind){Case c=new Case();c.start();NetworkBridge.deliver();check("timer/"+kind+": original next-poll delay preserved",c.original.handler.posts==1&&c.original.handler.delay==3500);invalidate(c,kind);String original=state(c.original),live=state(c.activity.session);c.original.handler.callback.run();check("timer/"+kind+": stale timer emits no event or state writes",c.activity.events==0&&state(c.original).equals(original)&&state(c.activity.session).equals(live)&&c.vpn.aborts==1);}
 static void normal(){Case c=new Case();c.start();NetworkBridge.deliver();check("normal: original completion statements run",DeferredBrowserSettings.cancels==1&&c.original.completed==1&&c.original.pending==null&&c.original.changes==2&&!c.original.state.optBoolean("busy")&&!c.original.navigating);check("normal: observer and VPN boundaries requested once with the actual callback snapshot",c.observation.idles==1&&c.vpn.stops==1&&c.vpn.snapshot==NetworkBridge.delivered&&c.original.handler.posts==1&&c.original.handler.delay==3500&&c.activity.events==0);c.original.handler.callback.run();JSONObject v=c.activity.eventValue;check("normal: original callback schema and first four native-work predicates retained",c.activity.events==1&&v.optBoolean("savedWhileReplying")&&v.optBoolean("oldRouteKept")&&v.optBoolean("browserSavedWithoutApplying")&&v.optBoolean("replyCleared"));check("normal: route and VPN acceptance deliberately remain false in this host",Boolean.FALSE.equals(v.opt("appliedWhenIdle"))&&Boolean.FALSE.equals(v.opt("vpnGuardBlocksWithoutVpn"))&&c.observation.attached==1&&c.vpn.attached==1);}
 public static void main(String[] args){
  if(args[0].equals("all")){for(String kind:new String[]{"command","destroyed","session","port","document","failed-observation","expired","vpn-owner","url"})entry(kind);for(String kind:new String[]{"command","destroyed","session","port","document","failed-observation","expired","vpn-owner","url"})late(kind);for(String kind:new String[]{"command","destroyed","session"})timer(kind);normal();}
  else if(args[0].equals("entry"))entry("command");else if(args[0].equals("callback"))late("command");else if(args[0].equals("timer"))timer("command");else throw new AssertionError("unknown scenario");
  System.out.println(J.obj("status","passed","passed",n,"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualRouteApplication",false,"scope","Exact queuedChangesReady and owner predicates; declared Bridge, Session, timer, VPN and observer boundaries; route/VPN acceptance remains false"));
 }
}
'''


def execute(ready, scenario='all'):
    java = os.environ.get('PROFILE_JAVA') or (str(JAVA) if JAVA.is_file() else shutil.which('java'))
    if not java:
        raise RuntimeError('JDK17 required for actual queued callback controls')
    fixture = HOST.replace('@READY@', ready).replace('@VPN_OWNS@', method(VPN.read_text(), 'owns')).replace('@OBSERVATION_OWNS@', method(OBSERVATION.read_text(), 'ownsUrl'))
    result = {}
    for runtime in ('json', 'android-json'):
        jar = ROOT / 'work/profile-host' / (runtime + '.jar')
        with tempfile.TemporaryDirectory(prefix='queued-callback46-') as directory:
            work = Path(directory)
            host = work / 'QueuedCallback46Host.java'
            host.write_text(fixture)
            clock = work / 'android/os/SystemClock.java'
            clock.parent.mkdir(parents=True)
            clock.write_text('package android.os;public class SystemClock{public static long now=100;public static long elapsedRealtime(){return now;}}')
            compile_result = subprocess.run([str(Path(java).with_name('javac')), '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(work), str(host), str(clock), str(ROOT / 'app/src/main/java/local/pocketchat/J.java')], text=True, capture_output=True)
            if compile_result.returncode:
                raise AssertionError(compile_result.stdout + compile_result.stderr)
            run = subprocess.run([str(java), '-cp', str(work) + ':' + str(jar), 'local.pocketchat.QueuedCallback46Host', scenario], text=True, capture_output=True)
            result[runtime] = dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr, jarSha256=hashlib.sha256(jar.read_bytes()).hexdigest())
    return result


class QueuedCallback46Test(unittest.TestCase):
    reports = {}

    @classmethod
    def setUpClass(cls):
        cls.ready = method(ACTIVITY.read_text(), 'queuedChangesReady')

    def test_actual_owner_fences_preserve_sessions_and_original_next_poll(self):
        result = execute(self.ready)
        for runtime, row in result.items():
            with self.subTest(runtime=runtime):
                self.assertEqual(row['returncode'], 0, row['stdout'] + row['stderr'])
                value = json.loads(row['stdout'])
                self.assertEqual(value['passed'], 55)
                self.assertTrue(all(check['pass'] for check in value['checks']))
                self.assertFalse(value['actualAndroidExecution'])
                self.assertFalse(value['actualGeckoExecution'])
                self.assertFalse(value['actualRouteApplication'])
        self.reports['actual'] = result

    def test_removing_each_owner_fence_is_observably_unsafe(self):
        self.assertEqual(self.ready.count(OWNER_GUARD), 2)
        self.assertEqual(self.ready.count(TIMER_GUARD), 1)
        variants = {'entry': self.ready.replace(OWNER_GUARD, '', 1),
                    'callback': ''.join(self.ready.rsplit(OWNER_GUARD, 1)),
                    'timer': self.ready.replace(TIMER_GUARD, '', 1)}
        for scenario, source in variants.items():
            result = execute(source, scenario)
            for runtime, row in result.items():
                with self.subTest(scenario=scenario, runtime=runtime):
                    self.assertNotEqual(row['returncode'], 0, 'A missing owner fence did not fail its counterexample')
                    self.assertIn('AssertionError', row['stderr'])
            self.reports[scenario + '-guard-removed'] = result

    @classmethod
    def tearDownClass(cls):
        destination = os.environ.get('QUEUED_CALLBACK46_REPORT')
        if destination:
            paths = (ACTIVITY, VPN, OBSERVATION, Path(__file__))
            value = dict(scope=__doc__, sourceSha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}, methodSha256=hashlib.sha256(cls.ready.encode()).hexdigest(), reports=cls.reports)
            output = Path(destination)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
