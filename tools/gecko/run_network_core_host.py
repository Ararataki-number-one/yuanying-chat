#!/usr/bin/env python3
"""Execute verbatim production network transaction methods with bounded JVM doubles.
No Android/Mihomo/browser or real-line acceptance is asserted. --source can replay
an archived NativeNetwork.java against the same fixed behavior expectations.
"""
import argparse, hashlib, json, os, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def block(source, signature):
    start=source.index(signature); opening=source.index('{',start); depth=0; state='code'; escaped=False; i=opening
    while i<len(source):
        c=source[i]; after=source[i:i+2]
        if state=='line':
            if c=='\n':state='code'
        elif state=='comment':
            if after=='*/':state='code';i+=1
        elif state in ('"',"'"):
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c==state:state='code'
        elif after=='//':state='line';i+=1
        elif after=='/*':state='comment';i+=1
        elif c in ('"',"'"):state=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return source[start:i+1]
        i+=1
    raise ValueError('unclosed production method: '+signature)
def main():
    p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--source',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);args=p.parse_args()
    source_path=args.source or ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java';source=source_path.read_text()
    java=str(args.java_home/'bin/java') if args.java_home else os.environ.get('PROFILE_JAVA','java')
    work=ROOT/'work/plan-repairs/network-core/host';work.mkdir(parents=True,exist_ok=True)
    methods=['  void runStartOperation(int mode)','  void scanSubset(', '  void selectNow(', '  void rescan(', '  void health(boolean reuseRecent)', '  static long exitRetryDelayMs(', '  boolean retainVerifiedRoute(']
    added=['  void recoverExistingRoute(', '  RetainedRouteFailure retained(', '  boolean retainedFailure(', '  boolean unchangedVerifiedSelection(', '  void commitSelection(', '  void selectVerifiedRoute(', '  void verifyExitWhenDue(', '  boolean retainedOutcomeCurrent(', '  void stopFailedTransaction(', '  void clearReadyState(']
    classes=block(source,'  static final class ExitRouteReceipt ')
    if '  static final class RetainedRouteFailure ' in source:classes+='\n'+block(source,'  static final class RetainedRouteFailure ')
    for signature in ['  enum RecoveryState ', '  static final class RecoveryOutcome ', '  interface RecoveryCallback ', '  static final class RecoveryAdapter ', '  static final class RouteTransactionFailure ']:
        if signature in source:classes+='\n'+block(source,signature)
    if '  enum RecoveryState ' not in source:classes+='\nenum RecoveryState {RECOVERED,RETAINED,FAILED} static final class RecoveryOutcome {final RecoveryState state; final String message;final ExitRouteReceipt receipt;RecoveryOutcome(RecoveryState s,String m,ExitRouteReceipt r){state=s;message=m;receipt=r;}}'
    bodies=[block(source,m) for m in methods]
    for m in added:
        if m in source:bodies.append(block(source,m))
    if '  void selectVerifiedRoute(' not in source:
        bodies.append('void selectVerifiedRoute(String name,boolean measure)throws Exception{selectNow(name);verifyExit();}')
    if '  boolean retainedOutcomeCurrent(' not in source:bodies.append('boolean retainedOutcomeCurrent(RecoveryOutcome outcome){return false;}')
    template=ROOT/'tests/network-core-host/NativeNetworkHarness.java.txt'
    harness=template.read_text().replace('// PRODUCTION_CLASSES',classes).replace('// PRODUCTION_METHODS','\n'.join(bodies))
    (work/'NativeNetwork.java').write_text(harness)
    (work/'SystemClock.java').write_text('package android.os;public class SystemClock{public static long elapsedRealtime(){return System.nanoTime()/1000000;}}')
    production=[ROOT/'app/src/main/java/local/pocketchat'/name for name in ['NetworkHealthPolicy.java','NetworkOptimizationPolicy.java','NetworkWork.java','NetworkDiagnostics.java']]
    jar=args.json_jar.resolve();classes_path=work/'classes';classes_path.mkdir(exist_ok=True)
    inputs=[*production,template,pathlib.Path(__file__).resolve()];hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
    subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(classes_path),str(work/'NativeNetwork.java'),str(work/'SystemClock.java'),*map(str,production)],check=True,timeout=60)
    run=subprocess.run([java,'-cp',str(classes_path)+os.pathsep+str(jar),'local.pocketchat.NativeNetwork'],capture_output=True,text=True,timeout=30)
    result=json.loads(run.stdout);result['sourceFile']=str(source_path);result['sourceSha256']=hashlib.sha256(source.encode()).hexdigest();result['files']=hashes;result['sourceCommit']=commit;result['sourceDirty']=dirty;result['executionInputsUnchanged']=source_path.read_text()==source and all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in hashes.items());result['extractedMethods']=methods+[m for m in added if m in source];result['harnessSha256']=hashlib.sha256(harness.encode()).hexdigest();result['stderr']=run.stderr
    if not result['executionInputsUnchanged']:result['status']='failed'
    output=args.output or work/'results.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':result['passed'],'total':result['total'],'report':str(output)}));raise SystemExit(run.returncode or (0 if result['executionInputsUnchanged'] else 1))
if __name__=='__main__':main()
