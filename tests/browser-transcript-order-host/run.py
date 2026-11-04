#!/usr/bin/env python3
"""Source-bound transcript order workload and semantic parity against f43adac."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
ASSETS=('page-driver.js','web-performance.js','web-reply-observer.js')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jsdom-module',default=os.environ.get('JSDOM_MODULE'))
    parser.add_argument('--output',type=Path,default=ROOT/'work/browser-transcript-order-host/results.json')
    args=parser.parse_args()
    env=dict(os.environ)
    if args.jsdom_module:
        env['JSDOM_MODULE']=args.jsdom_module
    baseline=subprocess.check_output(['git','rev-parse','f43adac^{commit}'],cwd=ROOT,text=True).strip()
    sources={name:(ROOT/'app/src/main/assets'/name).read_bytes() for name in ASSETS}
    reports={}
    hashes={}
    with tempfile.TemporaryDirectory(prefix='transcript-order-') as directory:
        for kind in ('before','current'):
            target=Path(directory)/kind
            target.mkdir()
            hashes[kind]={}
            for name in ASSETS:
                content=(subprocess.check_output(['git','show',baseline+':app/src/main/assets/'+name],cwd=ROOT)
                         if kind=='before' else sources[name])
                (target/name).write_bytes(content)
                hashes[kind][name]=hashlib.sha256(content).hexdigest()
            result=subprocess.run(['node',str(Path(__file__).with_name('workload.cjs')),str(target),kind],
                cwd=ROOT,env=env,text=True,capture_output=True,timeout=90)
            if result.returncode:
                raise RuntimeError(kind+' workload failed:\n'+result.stdout+result.stderr)
            reports[kind]=json.loads(result.stdout)
    for name,value in sources.items():
        if (ROOT/'app/src/main/assets'/name).read_bytes()!=value:
            raise RuntimeError('Production asset changed during checks: '+name)
    before,current=reports['before'],reports['current']
    for key in ('topology','runtime'):
        if before[key]!=current[key]:
            raise AssertionError('Complete production observation parity failed: '+key)
    if before['measured']['outputs']!=current['measured']['outputs']:
        raise AssertionError('Streamed transcript payload parity failed')
    if before['measured']['compareDocumentPosition']<=0 or current['measured']['compareDocumentPosition']!=0:
        raise AssertionError('Expected whole-conversation sorting reduction missing')
    for report in reports.values():
        report['measured'].pop('outputs')
    paths=(Path(__file__).resolve(),Path(__file__).with_name('workload.cjs'))
    payload={'schema':1,'status':'passed','baselineCommit':baseline,'productionSourceSha256':hashes,
        'nodeVersion':subprocess.check_output(['node','--version'],text=True).strip(),
        'harnessSha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'sourceUnchangedDuringChecks':True,'fullTranscriptDeltaParity':True,'reports':reports,
        'scope':'Actual prior/current production scripts, deterministic JSDOM DOM operation counts; no Android/Gecko/FPS or real website performance claim',
        'actualAndroidExecution':False,'actualGeckoExecution':False,'actualFrameTiming':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'passed','baselineChecks':before['passed'],'currentChecks':current['passed'],
        'before':before['measured'],'current':current['measured'],'report':str(args.output)},ensure_ascii=False))


if __name__=='__main__':
    main()
