#!/usr/bin/env python3
"""Restore immutable local test baselines without changing the checked-out source."""
import argparse
import hashlib
import json
import os
os.environ['GIT_NO_LAZY_FETCH']='1'
from pathlib import Path
import re
import subprocess
from source_history import prepare_public_history

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=ROOT/'tests/baselines/local-performance-history.json')
    p.add_argument('--output',type=Path,default=ROOT/'work/browser-baselines/results.json')
    args=p.parse_args();manifest=json.loads(args.manifest.read_text());bundle=args.manifest.parent/manifest['bundle']
    def git(*parts):return subprocess.check_output(['git',*parts],cwd=ROOT,text=True).strip()
    def exists(commit):return subprocess.run(['git','cat-file','-e',commit+'^{commit}'],cwd=ROOT,capture_output=True).returncode==0
    if manifest.get('schema')!=1 or not re.fullmatch('[0-9a-f]{40}',manifest['tip']) or not re.fullmatch('[0-9a-f]{40}',manifest['prerequisite']) or manifest['ref']!='refs/baselines/local-performance':raise ValueError('Unsupported baseline identity')
    sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
    if sha!=manifest['bundleSha256'] or bundle.stat().st_size!=manifest['bytes']:raise ValueError('Baseline bundle bytes differ')
    head=git('rev-parse','HEAD');dirty=git('status','--porcelain');public_history=prepare_public_history(ROOT);fetched=manifest['prerequisite'] in public_history['fetchedCommits']
    if not exists(manifest['prerequisite']):raise ValueError('Fixed public prerequisite is unavailable after explicit preparation')
    subprocess.run(['git','bundle','verify',str(bundle.resolve())],cwd=ROOT,check=True)
    heads=git('bundle','list-heads',str(bundle.resolve())).splitlines()
    if heads!=[manifest['tip']+' '+manifest['ref']]:raise ValueError('Unexpected bundle ref')
    subprocess.run(['git','fetch','--no-tags',str(bundle.resolve()),manifest['ref']+':'+manifest['ref']],cwd=ROOT,check=True)
    for short,commit in manifest['requiredCommits'].items():
        if not re.fullmatch('[0-9a-f]{40}',commit) or not exists(commit) or git('rev-parse',short+'^{commit}')!=commit:raise ValueError('Exact baseline is unavailable: '+short)
    subprocess.run(['git','merge-base','--is-ancestor',manifest['prerequisite'],manifest['tip']],cwd=ROOT,check=True)
    unchanged=head==git('rev-parse','HEAD') and dirty==git('status','--porcelain')
    report=dict(status='passed' if unchanged else 'failed',sourceCommit=head,headAndWorkingTreeUnchanged=unchanged,bundleSha256=sha,manifestSha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),requiredCommits=manifest['requiredCommits'],publicSourceHistory=public_history,prerequisiteFetchedFromOrigin=fetched,scope='Restored exact original Git test-baseline objects under refs/baselines only; no checkout, source rewriting, inferred tree equivalence or signing material.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if not unchanged:raise SystemExit(1)


if __name__=='__main__':main()
