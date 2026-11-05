#!/usr/bin/env python3
"""Compile and execute the complete current production AuditReport."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    def tool(name):return str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
    sources=[ROOT/'app/src/main/java/local/pocketchat'/name for name in ['AuditReport.java','J.java']]+[HERE/'GeckoTimeZoneReportHost.java']
    inputs=sources+[Path(__file__).resolve()];hashes={str(v.relative_to(ROOT)):sha(v) for v in inputs}
    with tempfile.TemporaryDirectory(prefix='gecko-timezone-report-') as temp:
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar.resolve()),'-d',temp,*map(str,sources)],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        r=subprocess.run([tool('java'),'-cp',temp+':'+str(a.json_jar.resolve()),'local.pocketchat.GeckoTimeZoneReportHost'],capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stderr)
        report=json.loads(r.stdout)
    report.update(schema=1,sourceFiles=hashes,executionInputsUnchanged=all(sha(v)==hashes[str(v.relative_to(ROOT))] for v in inputs),jsonJarSha256=sha(a.json_jar),actualAndroidExecution=False,actualGeckoNativeSettingExecution=False,scope='Full current AuditReport against explicit synthetic native-ACK eligibility and timestamped public page signal inputs; actual java.time TZDB/DST. IP classification is an unused boundary adapter. No BC, Android Date, page, Worker or device execution is claimed.')
    if not report['executionInputsUnchanged']:raise RuntimeError('Source changed during execution')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['schema','status','passed','total','executionInputsUnchanged']}))
if __name__=='__main__':main()
