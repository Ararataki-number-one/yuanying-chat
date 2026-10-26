#!/usr/bin/env python3
"""Count exact catalogue/apply/bind methods; explicit adapters, no Android timing claim."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BASELINE='da5004111eaf3e20322ca1fca3f756db82f44c90'

def member(text,needle):
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
    while i<len(text):
        c=text[i];pair=text[i:i+2]
        if line:
            if c=='\n':line=False
        elif block:
            if pair=='*/':block=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif pair=='//':line=True;i+=1
        elif pair=='/*':block=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
        i+=1
    raise ValueError(needle)

def digest(raw):return hashlib.sha256(raw).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--java-home',type=Path,required=True);parser.add_argument('--json-jar',type=Path,required=True);parser.add_argument('--before-ref');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    names=['ProfileCatalog.java','Profiles.java','DesignDownloads.java','DownloadListPolicy.java']
    def selected(name,ref=None):
        relative='app/src/main/java/local/pocketchat/'+name
        return subprocess.check_output(['git','show',ref+':'+relative],cwd=ROOT) if ref else (ROOT/relative).read_bytes()
    sources={name:selected(name,args.before_ref) for name in names};text={name:raw.decode()for name,raw in sources.items()};before=bool(args.before_ref)
    extracts={}
    for key,name,needle in [('item','ProfileCatalog.java','JSONObject item('),('row','ProfileCatalog.java','static JSONObject row('),('name','ProfileCatalog.java','String name(int slot)'),('display','Profiles.java','static String display('),('apply','DesignDownloads.java','void apply(JSONArray data,'),('bind','DesignDownloads.java','void bind(JSONObject row,'),('text','DesignDownloads.java','static void text(TextView'),('visible','DesignDownloads.java','static void visible(View')]:extracts[key]=member(text[name],needle)
    catalog=[extracts[k]for k in ['item','row','name']]
    if not before:
        extracts['names']=member(text['ProfileCatalog.java'],'Map<Integer,String> names()')
        extracts['displayName']=member(text['ProfileCatalog.java'],'static String displayName(')
        catalog.extend([extracts['names'],extracts['displayName']])
    helpers=[member(text['DesignDownloads.java'],needle)for needle in ['static String key(','static boolean busy(','static boolean matches(','static String timeLabel(']]
    host=(HERE/'DownloadNamesHost.java.in').read_text().replace('/* CATALOG */','\n'.join(catalog)).replace('/* PROFILES_DISPLAY */',extracts['display']).replace('/* DOWNLOAD_HELPERS */','\n'.join(helpers)).replace('/* CONTROLLER_APPLY */',extracts['apply']).replace('/* ROW_BIND */',extracts['bind']).replace('/* ROW_TEXT */',extracts['text']).replace('/* ROW_VISIBLE */',extracts['visible'])
    unchanged={}
    if not before:
        baseline=selected('DesignDownloads.java',BASELINE).decode()
        restored_apply=extracts['apply'].replace('Map<Integer,String> environmentNames=null;','').replace('if(environmentNames==null)environmentNames=ProfileCatalog.get(a).names();','').replace('row.bind(value,now,ProfileCatalog.displayName(environmentNames,value.optInt("slot")));','row.bind(value,now);')
        unchanged['controllerApplyExceptProjectedNameLookup']=restored_apply==member(baseline,'void apply(JSONArray data,')
        restored_bind=extracts['bind'].replace('void bind(JSONObject row,long now,String environmentName)','void bind(JSONObject row,long now)').replace('text(status,environmentName+','text(status,Profiles.display(a,row.optInt("slot"))+')
        unchanged['rowBindExceptSuppliedEnvironmentName']=restored_bind==member(baseline,'void bind(JSONObject row,')
        removed=text['DesignDownloads.java'].replace(extracts['apply'],member(baseline,'void apply(JSONArray data,')).replace(extracts['bind'],member(baseline,'void bind(JSONObject row,'))
        unchanged['allOtherDownloadUiBytes']=removed==baseline
        baseline_catalog=selected('ProfileCatalog.java',BASELINE).decode()
        stripped=text['ProfileCatalog.java'].replace('  /** Refresh-local labels only; do not load private drafts/notes or cache across renames. */\n','').replace('  '+extracts['names']+'\n','').replace('  '+extracts['displayName']+'\n','')
        unchanged['allExistingCatalogBytes']=stripped==baseline_catalog
        assert all(unchanged.values()),unchanged
    inputs=[Path(__file__).resolve(),HERE/'DownloadNamesHost.java.in',*HERE.glob('stubs/**/*.java')];input_hashes={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs}
    with tempfile.TemporaryDirectory(prefix='download-names-host-') as raw:
        temp=Path(raw);package=temp/'local/pocketchat';package.mkdir(parents=True);java=package/'DownloadNamesHost.java';java.write_text(host);policy=package/'DownloadListPolicy.java';policy.write_bytes(sources['DownloadListPolicy.java']);classes=temp/'classes'
        subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(classes),str(java),str(policy),*map(str,HERE.glob('stubs/**/*.java'))],check=True)
        run=subprocess.run([str(args.java_home/'bin/java'),'-Dbefore='+str(before).lower(),'-cp',str(classes)+':'+str(args.json_jar),'local.pocketchat.DownloadNamesHost'],text=True,capture_output=True)
        if not run.stdout:raise RuntimeError(run.stderr)
        result=json.loads(run.stdout);result.update(sourceHead=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),selectedProductionRef=args.before_ref or 'working-tree',selectedProductionSha256={n:digest(raw)for n,raw in sources.items()},extractedMethodSha256={k:digest(v.encode())for k,v in extracts.items()},testSourceSha256=input_hashes,unchangedSourceSections=unchanged,actualAndroidExecution=False,actualSqliteExecution=False,actualPhoneFrameMeasurement=False,applicationSpeedupClaim=False,scope='Exact production ProfileCatalog.item/row/name, new projected names/displayName, Profiles.display, DesignDownloads.Controller.apply and Row.bind/text/visible plus complete DownloadListPolicy. Explicit SQL cursor/count and deterministic widget adapters; no Android database/layout/frame performance claim.')
        result['executionInputsUnchanged']=all(digest((ROOT/p).read_bytes())==h for p,h in input_hashes.items()) and (bool(args.before_ref) or all(selected(n)==value for n,value in sources.items()))
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'variant':result['variant'],'passed':result['passed'],'total':result['total'],'measurements':result['measurements'],'output':str(args.output),'sha256':digest(args.output.read_bytes()),'executionInputsUnchanged':result['executionInputsUnchanged']}))
        if run.returncode or result['status']!='passed' or not result['executionInputsUnchanged']:raise SystemExit(1)

if __name__=='__main__':main()
