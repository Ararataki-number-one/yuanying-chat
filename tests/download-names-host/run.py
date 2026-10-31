#!/usr/bin/env python3
"""Count exact catalogue/apply/bind methods; explicit adapters, no Android timing claim."""
import argparse
import hashlib
import json
import importlib.util
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BASELINE='da5004111eaf3e20322ca1fca3f756db82f44c90'

_review_spec=importlib.util.spec_from_file_location('reviewed_download38_inverse',HERE/'reviewed38.py')
_review=importlib.util.module_from_spec(_review_spec);_review_spec.loader.exec_module(_review)
_review46_spec=importlib.util.spec_from_file_location('reviewed_download46_inverse',HERE/'reviewed46.py')
_review46=importlib.util.module_from_spec(_review46_spec);_review46_spec.loader.exec_module(_review46)
def remove_reviewed46(text,name='DesignDownloads.java'):return _review46.invert(text,name)
def remove_reviewed38(text):return _review.invert(remove_reviewed46(text))

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

def remove_reviewed_delete_identity(text):
    """Invert only the separately reviewed 2.0.31 additive deletion APIs.

    The download-name methods and every historical catalogue byte still undergo
    the original whole-file comparison below; this is not a deletion-behaviour
    oracle. The production identity/maintenance suites cover those new APIs.
    """
    start='  /** A confirmation belongs to the exact environment shown in its dialog. */\n'
    end='  void beginDelete(int slot)'
    assert text.count(start)==1 and text.count(end)==1,'Reviewed deletion addition must occur exactly once'
    begin=text.index(start);finish=text.index(end,begin+len(start));raw=text[begin:finish].encode()
    assert len(raw)==1579 and len(raw.splitlines())==22,'Reviewed deletion addition size changed'
    assert digest(raw)=='5e961abfcccae702bc026b4664063afa1a783be04514cdd499b906c8fd7d8811','Reviewed deletion addition bytes changed'
    return text[:begin]+text[finish:]

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
    render_apply=extracts['apply'];reviewed46='DownloadPageWindow.LIMIT' in render_apply
    if reviewed46:render_apply=render_apply.replace('void apply(JSONArray data,','void productionApply(JSONArray data,',1)+'''
    // Controlled worker-preparation boundary. The real asynchronous worker is executed by download46-host/worker.py.
    void apply(JSONArray data,int selected,long now){hostRows=data;hostSelected=selected;hostNow=now;preparedOwners=DownloadDisplaySnapshot.labels(a,data,selected);productionApply(new DownloadPageWindow(data,selected,hostAnchor).rows,selected,now);}
'''
    host=(HERE/'DownloadNamesHost.java.in').read_text().replace('/* CATALOG */','\n'.join(catalog)).replace('/* PROFILES_DISPLAY */',extracts['display']).replace('/* DOWNLOAD_HELPERS */','\n'.join(helpers)).replace('/* CONTROLLER_APPLY */',render_apply).replace('/* ROW_BIND */',extracts['bind']).replace('/* ROW_TEXT */',extracts['text']).replace('/* ROW_VISIBLE */',extracts['visible'])
    owner_method=member((ROOT/'app/src/main/java/local/pocketchat/DownloadDisplaySnapshot.java').read_text(),'static Map<Integer,DownloadOwnerLabels.Owner> owners(')
    host+='\nclass DownloadDisplaySnapshot{'+owner_method+'''static Map<String,String> labels(Context c,JSONArray rows,int filter){Map<String,String> out=new HashMap<>();Map<Integer,DownloadOwnerLabels.Owner> owners=null;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(!DownloadListPolicy.matches(row,filter))continue;if(owners==null)owners=owners(c);out.put(DownloadListPolicy.key(row),DownloadOwnerLabels.label(row,owners));}return out;}}\n'''
    unchanged={}
    if not before:
        baseline=selected('DesignDownloads.java',BASELINE).decode()
        guard_text=remove_reviewed38(text['DesignDownloads.java'])
        guard_apply=member(guard_text,'void apply(JSONArray data,')
        guard_bind=member(guard_text,'void bind(JSONObject row,')
        restored_apply=guard_apply.replace('Map<Integer,String> environmentNames=null;','').replace('if(environmentNames==null)environmentNames=ProfileCatalog.get(a).names();','').replace('row.bind(value,now,ProfileCatalog.displayName(environmentNames,value.optInt("slot")));','row.bind(value,now);')
        unchanged['controllerApplyExceptProjectedNameLookup']=restored_apply==member(baseline,'void apply(JSONArray data,')
        restored_bind=guard_bind.replace('void bind(JSONObject row,long now,String environmentName)','void bind(JSONObject row,long now)').replace('text(status,environmentName+','text(status,Profiles.display(a,row.optInt("slot"))+')
        unchanged['rowBindExceptSuppliedEnvironmentName']=restored_bind==member(baseline,'void bind(JSONObject row,')
        removed=guard_text.replace(guard_apply,member(baseline,'void apply(JSONArray data,')).replace(guard_bind,member(baseline,'void bind(JSONObject row,'))
        unchanged['allOtherDownloadUiBytes']=removed==baseline
        baseline_catalog=selected('ProfileCatalog.java',BASELINE).decode()
        stripped=remove_reviewed46(text['ProfileCatalog.java'],'ProfileCatalog.java').replace('  /** Refresh-local labels only; do not load private drafts/notes or cache across renames. */\n','').replace('  '+extracts['names']+'\n','').replace('  '+extracts['displayName']+'\n','')
        stripped=remove_reviewed_delete_identity(stripped)
        unchanged['allExistingCatalogBytes']=stripped==baseline_catalog
        assert all(unchanged.values()),unchanged
    inputs=[Path(__file__).resolve(),HERE/'DownloadNamesHost.java.in',HERE/'reviewed38.py',HERE/'reviewed38-inverse.json',HERE/'reviewed46.py',HERE/'reviewed46-inverse.json',ROOT/'app/src/main/java/local/pocketchat/DownloadDisplaySnapshot.java',*[ROOT/'app/src/main/java/local/pocketchat'/name for name in ['DownloadMetadataValues.java','DownloadTaskRevisions.java','DownloadPageWindow.java','DownloadOwnerLabels.java']],ROOT/'app/src/main/java/local/pocketchat/DownloadRowBinding.java',*HERE.glob('stubs/**/*.java')];input_hashes={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs}
    with tempfile.TemporaryDirectory(prefix='download-names-host-') as raw:
        temp=Path(raw);package=temp/'local/pocketchat';package.mkdir(parents=True);java=package/'DownloadNamesHost.java';java.write_text(host);policy=package/'DownloadListPolicy.java';policy.write_bytes(sources['DownloadListPolicy.java']);binding=package/'DownloadRowBinding.java';binding.write_bytes(selected('DownloadRowBinding.java'));extras=[]
        for name in ['DownloadMetadataValues.java','DownloadTaskRevisions.java','DownloadPageWindow.java','DownloadOwnerLabels.java']:
            extra=package/name;extra.write_bytes(selected(name));extras.append(str(extra))
        classes=temp/'classes'
        subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar),'-d',str(classes),str(java),str(policy),str(binding),*extras,*map(str,HERE.glob('stubs/**/*.java'))],check=True)
        run=subprocess.run([str(args.java_home/'bin/java'),'-Dbefore='+str(before).lower(),'-Dreviewed46='+str(reviewed46).lower(),'-cp',str(classes)+':'+str(args.json_jar),'local.pocketchat.DownloadNamesHost'],text=True,capture_output=True)
        if not run.stdout:raise RuntimeError(run.stderr)
        result=json.loads(run.stdout);result.update(sourceHead=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),selectedProductionRef=args.before_ref or 'working-tree',selectedProductionSha256={n:digest(raw)for n,raw in sources.items()},extractedMethodSha256={k:digest(v.encode())for k,v in extracts.items()},testSourceSha256=input_hashes,unchangedSourceSections=unchanged,actualAndroidExecution=False,actualSqliteExecution=False,actualPhoneFrameMeasurement=False,applicationSpeedupClaim=False,reviewed46=reviewed46,scope='46 uses a controlled names/page worker boundary before exact current production apply/bind; names remain checked for first/last records and all original fallback/anchor cases. Actual source-bound async worker and all-page equivalence run separately in download46-host. Exact production ProfileCatalog.item/row/name, new projected names/displayName, Profiles.display, DesignDownloads.Controller.apply and Row.bind/text/visible plus complete DownloadListPolicy. Explicit SQL cursor/count and deterministic widget adapters; no Android database/layout/frame performance claim.')
        result['executionInputsUnchanged']=all(digest((ROOT/p).read_bytes())==h for p,h in input_hashes.items()) and (bool(args.before_ref) or all(selected(n)==value for n,value in sources.items()))
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'variant':result['variant'],'passed':result['passed'],'total':result['total'],'measurements':result['measurements'],'output':str(args.output),'sha256':digest(args.output.read_bytes()),'executionInputsUnchanged':result['executionInputsUnchanged']}))
        if run.returncode or result['status']!='passed' or not result['executionInputsUnchanged']:raise SystemExit(1)

if __name__=='__main__':main()
