#!/usr/bin/env python3
"""Compare production observer control workloads with the exact prior Git source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
BASE='1e3086a'
ASSETS=('page-driver.js','web-performance.js','web-reply-observer.js')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jsdom-module',default=os.environ.get('JSDOM_MODULE'))
    parser.add_argument('--output',type=Path,default=ROOT/'work/browser-controls-performance-host/results.json')
    args=parser.parse_args()
    environment=dict(os.environ)
    if args.jsdom_module:
        environment['JSDOM_MODULE']=args.jsdom_module
    baseline=subprocess.check_output(['git','rev-parse',BASE+'^{commit}'],cwd=ROOT,text=True).strip()
    sources={name:(ROOT/'app/src/main/assets'/name).read_bytes() for name in ASSETS}
    reports={}
    hashes={}
    with tempfile.TemporaryDirectory(prefix='browser-controls-') as directory:
        for kind in ('before','current'):
            target=Path(directory)/kind
            target.mkdir()
            hashes[kind]={}
            for name in ASSETS:
                content=(subprocess.check_output(['git','show',baseline+':app/src/main/assets/'+name],cwd=ROOT)
                         if kind=='before' else sources[name])
                (target/name).write_bytes(content)
                hashes[kind][name]=hashlib.sha256(content).hexdigest()
            result=subprocess.run(['node',str(Path(__file__).with_name('workload.cjs')),str(target),
                'optimized' if kind=='current' else 'baseline'],cwd=ROOT,env=environment,
                text=True,capture_output=True,timeout=90)
            if result.returncode:
                raise RuntimeError(kind+' workload failed:\n'+result.stdout+result.stderr)
            reports[kind]=json.loads(result.stdout)
    for name,content in sources.items():
        if (ROOT/'app/src/main/assets'/name).read_bytes()!=content:
            raise RuntimeError('Production source changed during verification: '+name)
    before,current=reports['before'],reports['current']
    for key in ('controls','fallback','resources'):
        if before[key]!=current[key]:
            raise AssertionError('Observation changed for '+key)
    if before['measured']['outputs']!=current['measured']['outputs']:
        raise AssertionError('Streaming observation parity failed')
    old,new=before['measured']['counters'],current['measured']['counters']
    if not(old['documentControlQueries']>0 and new['documentControlQueries']==0 and
           old['documentControlNodes']>40000 and new['documentControlNodes']==0 and
           new['controlLabelReads']*10<old['controlLabelReads']):
        raise AssertionError('Expected production query/read workload reduction missing')
    for report in reports.values():
        report['measured'].pop('outputs')
    payload={'schema':1,'status':'passed','baselineCommit':baseline,'productionSourceSha256':hashes,
        'harnessSha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__).resolve(),Path(__file__).with_name('workload.cjs'))},
        'observationParity':True,'sourceUnchangedDuringChecks':True,'reports':reports,
        'scope':'Actual prior/current production JavaScript in JSDOM; operation counts only; no Android/Gecko/FPS/real website performance claim',
        'actualAndroidExecution':False,'actualGeckoExecution':False,'actualFrameTiming':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'passed','before':old,'current':new,'checks':current['passed'],
        'baselineChecks':before['passed'],'report':str(args.output)},ensure_ascii=False))


if __name__=='__main__':
    main()
