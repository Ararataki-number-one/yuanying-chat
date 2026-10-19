#!/usr/bin/env python3
"""Run actual candidate key-queue methods with deterministic parent/child doubles.

This checks Java queue ownership and exactly-once release, not APZ completion or
Android editing acceptance. The original Android workloads remain required.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = r'''
import java.util.*;
import java.util.concurrent.*;
public class KeyOrder {
static class View {}
static class KeyEvent {static final int ACTION_DOWN=0,ACTION_UP=1;static int getMaxKeyCode(){return 400;}}
static class RemoteException extends Exception {}
static class Action {static final int TYPE_EVENT=0;Action(int type){}}
interface IGeckoEditableChild {void onImeSynchronize()throws RemoteException;}
static class Handler {
 final Queue<Runnable> tasks=new ArrayDeque<>();boolean reject,awake;
 boolean post(Runnable r){if(reject)return false;tasks.add(r);return true;}
 void drain(){if(this==ThreadUtils.sGeckoHandler&&!awake)return;while(!tasks.isEmpty())tasks.remove().run();}
}
static class ThreadUtils {static Handler sGeckoHandler;}
static class XPCOMEventTarget {
 static int wakes;static XPCOMEventTarget mainThread(){return new XPCOMEventTarget();}
 void execute(Runnable r){wakes++;ThreadUtils.sGeckoHandler.awake=true;r.run();}
}
static class Log {static void e(String a,String b,Exception c){}}
static final String LOGTAG="test";
final Handler ic=new Handler();
final ConcurrentLinkedQueue<Action> mActions=new ConcurrentLinkedQueue<>();
final ConcurrentLinkedQueue<Runnable> mOrderedKeys=new ConcurrentLinkedQueue<>();
volatile Action mOrderedKeyBarrier;IGeckoEditableChild mOrderedKeyChild;
volatile long mOrderedKeyEpoch;IGeckoEditableChild mFocusedChild;Object mListener=new Object();
final List<Integer> sent=new ArrayList<>();int requests,nativeCaret=2,shadowCaret=2;
KeyOrder(){ThreadUtils.sGeckoHandler=new Handler();XPCOMEventTarget.wakes=0;mFocusedChild=()->requests++;}
void postToInputConnection(Runnable r){ic.post(r);}
boolean shouldProcessKey(int code,KeyEvent event){return true;}
void sendKeyEvent(View view,int action,KeyEvent event){sent.add(action);}
void icSyncShadowText(){if(mActions.isEmpty())shadowCaret=nativeCaret;}
void key(int action){processKey(null,action,12,new KeyEvent());}
void parent(){ThreadUtils.sGeckoHandler.drain();ic.drain();}
void reply(Action exact){mActions.remove(exact);ic.post(()->icCompleteOrderedKey(exact));ic.drain();}
static void require(boolean yes,String message){if(!yes)throw new AssertionError(message);}
'''
SUFFIX = r'''
public static void main(String[] args)throws Exception{
 int checks=0;
 {KeyOrder r=new KeyOrder();r.key(0);require(r.sent.isEmpty()&&r.requests==0,"parent gate");checks++;
  require(XPCOMEventTarget.wakes==1,"native event target wakes idle parent without releasing the key");checks++;
  r.nativeCaret=9;r.parent();require(r.requests==1&&r.sent.isEmpty(),"must await child reply");checks++;
  Action a=r.mOrderedKeyBarrier;r.reply(new Action(0));require(r.sent.isEmpty(),"foreign reply");checks++;
  r.reply(a);require(r.sent.equals(List.of(0))&&r.shadowCaret==9,"native state synchronized before one key");checks++;
  r.reply(a);require(r.sent.equals(List.of(0)),"duplicate cannot replay");checks++;}
 {KeyOrder r=new KeyOrder();r.key(0);r.key(1);r.parent();Action down=r.mOrderedKeyBarrier;
  r.reply(down);require(r.sent.equals(List.of(0))&&r.requests==2,"one reply releases one key");checks++;
  Action up=r.mOrderedKeyBarrier;require(up!=down,"each key owns a fresh barrier");checks++;
  r.reply(down);require(r.sent.equals(List.of(0))&&r.mOrderedKeyBarrier==up,"stale reply preserves new head");checks++;
  r.reply(up);require(r.sent.equals(List.of(0,1)),"FIFO down/up exactly once");checks++;}
 {KeyOrder r=new KeyOrder();r.key(0);r.geckoCancelOrderedKeys();r.parent();
  require(r.requests==0&&r.sent.isEmpty(),"parent work invalidated by blur epoch");checks++;}
 {KeyOrder r=new KeyOrder();r.key(0);r.parent();Action old=r.mOrderedKeyBarrier;
  r.geckoCancelOrderedKeys();r.mActions.clear();r.key(1);r.parent();Action fresh=r.mOrderedKeyBarrier;
  r.reply(old);require(r.sent.isEmpty()&&r.mOrderedKeyBarrier==fresh,"blurred child reply cannot release new work");checks++;
  r.reply(fresh);require(r.sent.equals(List.of(1)),"new focus owns new work");checks++;}
 {KeyOrder r=new KeyOrder();r.key(0);r.parent();Action a=r.mOrderedKeyBarrier;r.mFocusedChild=()->{};
  r.reply(a);require(r.sent.isEmpty()&&r.mOrderedKeys.isEmpty(),"no key into a changed child");checks++;}
 {KeyOrder r=new KeyOrder();r.mFocusedChild=()->{throw new RemoteException();};r.key(0);r.parent();
  require(r.sent.isEmpty()&&r.mOrderedKeys.isEmpty()&&r.mActions.isEmpty()&&r.mOrderedKeyBarrier==null,"remote failure cannot submit or retry");checks++;}
 {KeyOrder r=new KeyOrder();ThreadUtils.sGeckoHandler=null;r.key(0);r.ic.drain();
  require(r.sent.equals(List.of(0))&&r.requests==0,"original absent-parent path once");checks++;
  require(XPCOMEventTarget.wakes==0,"no native wake for absent parent");checks++;}
 {KeyOrder r=new KeyOrder();ThreadUtils.sGeckoHandler.reject=true;r.key(0);r.ic.drain();
  require(r.sent.equals(List.of(0))&&r.requests==0,"original closed-parent path once");checks++;
  require(XPCOMEventTarget.wakes==0,"no native wake after parent rejection");checks++;}
 {KeyOrder r=new KeyOrder();r.mFocusedChild=null;r.key(0);r.parent();
  require(r.sent.equals(List.of(0)),"original no-focus path once");checks++;}
 {KeyOrder r=new KeyOrder();r.mListener=null;r.key(0);r.parent();
  require(r.sent.equals(List.of(0)),"original uninitialized-listener path once");checks++;}
 System.out.print("{\"status\":\"passed\",\"checkCount\":"+checks+",\"actualAndroidExecution\":false,\"nativeTouchCompletionProven\":false}");
}
}
'''


def main():
    source = (ROOT / 'third-party/gecko/GeckoEditable.java').read_text()
    methods = source[source.index('  private boolean processKey('):source.index('  private static boolean shouldProcessKey(')]
    methods = methods.replace('@Nullable ', '').replace('@NonNull ', '')
    javac = str(Path(os.environ['JAVA_HOME']) / 'bin/javac') if 'JAVA_HOME' in os.environ else 'javac'
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java') if 'JAVA_HOME' in os.environ else 'java'
    with tempfile.TemporaryDirectory(prefix='pocket-key-order-') as directory:
        p = Path(directory)
        (p / 'KeyOrder.java').write_text(PREFIX + methods + SUFFIX)
        subprocess.run([javac, str(p / 'KeyOrder.java')], check=True)
        result = json.loads(subprocess.check_output([java, '-cp', str(p), 'KeyOrder'], text=True))
        # The same actual source with just its native wake removed must fail
        # while the parent is idle; unconditional Java draining masks this bug.
        no_wake = methods.replace('XPCOMEventTarget.mainThread().execute(() -> {});', '')
        assert no_wake != methods
        (p / 'KeyOrder.java').write_text(PREFIX + no_wake + SUFFIX)
        subprocess.run([javac, str(p / 'KeyOrder.java')], check=True)
        negative = subprocess.run([java, '-cp', str(p), 'KeyOrder'], capture_output=True, text=True)
        assert negative.returncode != 0 and 'native event target wakes idle parent' in negative.stderr
        result['missingNativeWakeRejected'] = True
    assert result['status'] == 'passed' and result['checkCount'] == 21
    print(json.dumps(result))


if __name__ == '__main__':
    main()
