#!/usr/bin/env python3
"""Execute the actual fixture observer with controlled host UI/IPC adapters."""
import argparse
import json
import pathlib
import subprocess
import tempfile

def run(java_home, json_jar, output):
    root=pathlib.Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='source-route-terminal-') as temp:
        work=pathlib.Path(temp);clock=work/'android/os/SystemClock.java';clock.parent.mkdir(parents=True)
        clock.write_text('package android.os; public final class SystemClock { public static long elapsedRealtimeNanos(){return System.nanoTime();} }\n')
        sources=[root/'tests/gecko/SourceRouteTerminalObserver.java',root/'app/src/main/java/local/pocketchat/J.java',pathlib.Path(__file__).with_name('TerminalObserverTest.java'),clock]
        subprocess.run([str(java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(json_jar),'-d',str(work),*map(str,sources)],check=True)
        output.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(java_home/'bin/java'),'-cp',str(work)+':'+str(json_jar),'local.pocketchat.TerminalObserverTest',str(output)],check=True,timeout=30)
        report=json.loads(output.read_text());assert report['status']=='passed' and report['total']==26 and all(row['pass'] is True for row in report['checks'])
        return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--java-home',type=pathlib.Path,required=True);p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();run(a.java_home,a.json_jar,a.output)
