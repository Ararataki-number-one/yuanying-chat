#!/usr/bin/env python3
"""Exercise actual SDK queue handoff methods with deterministic thread barriers.

Android dependencies and span copying are controlled doubles. This checks queue
publication ordering, not native composition or physical-keyboard acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = """import java.util.concurrent.*;
public class ReplyRace {
static final boolean DEBUG=false; static final String LOGTAG="test";
interface IBinder {default boolean pingBinder(){return true;}}
interface IGeckoEditableChild {IBinder asBinder();}
static class Action {}
static class Log {static void d(String a,String b){}static void w(String a,String b){}}
static class ThreadUtils {static void assertOnGeckoThread(){}}
static class SessionTextInput {static class EditableListener {static final int NOTIFY_IME_REPLY_EVENT=1,NOTIFY_IME_OF_TOKEN=2,NOTIFY_IME_OPEN_VKB=3,NOTIFY_IME_OF_BLUR=4;}}
static String getConstantName(Class<?> a,String b,int c){return "";}
IBinder mFocusedToken;Object mListener=new Object();boolean mInBatchMode,mNeedSync=true;
Action mOrderedKeyBarrier;
void geckoCancelOrderedKeys(){mOrderedKeyBarrier=null;}
void postToInputConnection(Runnable r){r.run();}
void icCompleteOrderedKey(Action a){throw new AssertionError("Unexpected ordered key in span-only host control");}
final ConcurrentLinkedQueue<Action> mActions=new ConcurrentLinkedQueue<>();
final CountDownLatch entered=new CountDownLatch(1),finishReply=new CountDownLatch(1);
volatile boolean currentComplete,prematureCopy;int copies;
class Text {void syncShadowText(Object listener){copies++;if(!currentComplete)prematureCopy=true;}}
final Text mText=new Text();
class Handler {void post(Runnable r){r.run();}} final Handler mIcPostHandler=new Handler();
boolean binderCheckToken(IBinder token,boolean allowNull){return token==mFocusedToken;}
void onTextChange(IBinder token,String value,int start,int end,boolean composition){}
void geckoActionReply(Action a){if(a==null)return;entered.countDown();try{if(!finishReply.await(5,TimeUnit.SECONDS))throw new AssertionError("barrier");}catch(InterruptedException e){throw new AssertionError(e);}currentComplete=true;}
void icNotifyIME(IGeckoEditableChild child,int type){if(mNeedSync)icSyncShadowText();}
"""

SUFFIX = """
public static void main(String[] args)throws Exception{
 boolean expected=Boolean.parseBoolean(args[0]);
 for(int mode=0;mode<3;mode++){
 ReplyRace r=new ReplyRace();r.mFocusedToken=new IBinder(){};r.mActions.add(new Action());
 Thread reply=new Thread(()->r.notifyIME(()->r.mFocusedToken,1));reply.start();
 if(!r.entered.await(5,TimeUnit.SECONDS))throw new AssertionError("reply not entered");
 r.icSyncShadowText();boolean premature=r.prematureCopy;
 Action next=new Action();
 if(mode==2)r.mActions.clear();
 if(mode>0)r.mActions.add(next);
 r.finishReply.countDown();reply.join(5000);
 if(reply.isAlive())throw new AssertionError("reply did not complete");
 if(premature!=expected)throw new AssertionError("prematureCopy="+premature);
 if(mode>0){
  if(r.mActions.size()!=1||r.mActions.peek()!=next)throw new AssertionError("new action lost");
  if(!expected&&r.copies!=0)throw new AssertionError("synced while next action pending");
  r.notifyIME(()->r.mFocusedToken,1);
 }
 if(!expected&&(r.copies!=1||r.mNeedSync||!r.mActions.isEmpty()))throw new AssertionError("final synchronization missing");
 System.out.println("mode="+mode+", prematureCopy="+premature+", copies="+r.copies);
 }
}
}
"""

def methods(source):
    reply = source[source.index('  public void notifyIME('):source.index('  /* package */ void icNotifyIME(')]
    sync = source[source.index('  /* package */ void icSyncShadowText()'):source.index('  private void setSuppressKeyUp(')]
    return reply.replace('@IMENotificationType ', '') + sync


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-sources', type=Path, required=True)
    args = parser.parse_args()
    official = json.loads((ROOT / 'third-party/sdk/geckoview-157.0.1-official.json').read_text())
    with ZipFile(args.upstream_sources) as archive:
        upstream = archive.read('org/mozilla/geckoview/GeckoEditable.java')
    assert hashlib.sha256(upstream).hexdigest() == official['geckoEditableSourceSha256']
    candidate = (ROOT / 'third-party/gecko/GeckoEditable.java').read_bytes()
    javac = str(Path(os.environ['JAVA_HOME']) / 'bin/javac') if 'JAVA_HOME' in os.environ else 'javac'
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java') if 'JAVA_HOME' in os.environ else 'java'
    results = {}
    with tempfile.TemporaryDirectory(prefix='pocketchat-reply-handoff-') as directory:
        for label, source, early in [('upstream', upstream, True), ('candidate', candidate, False)]:
            output = Path(directory) / label
            output.mkdir()
            (output / 'ReplyRace.java').write_text(PREFIX + methods(source.decode()) + SUFFIX)
            subprocess.run([javac, str(output / 'ReplyRace.java')], check=True)
            result = subprocess.check_output([java, '-cp', str(output), 'ReplyRace', str(early).lower()], text=True)
            results[label] = result.strip()
    print(json.dumps(dict(status='passed', sourceSha256=hashlib.sha256(candidate).hexdigest(),
        originalRaceReproduced=True, candidateEarlySyncBlocked=True, pendingActionPreserved=True, results=results,
        actualAndroidExecution=False, scope='Extracted actual notifyIME/icSyncShadowText; controlled reply barrier only')))


if __name__ == '__main__':
    main()
