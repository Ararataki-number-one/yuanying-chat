#!/usr/bin/env python3
"""Execute production draft-policy classes and methods with narrow JVM adapters."""
import argparse, hashlib, json, os, pathlib, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

def member(text, needle):
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
    while i<len(text):
        c=text[i];n=text[i:i+2]
        if line:
            if c=='\n':line=False
        elif block:
            if n=='*/':block=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif n=='//':line=True;i+=1
        elif n=='/*':block=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
        i+=1
    raise ValueError('Unclosed member: '+needle)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json-jar',type=pathlib.Path,required=True);parser.add_argument('--java-home',type=pathlib.Path);parser.add_argument('--output',type=pathlib.Path);parser.add_argument('--before-ref',help='Execute immutable old PageMemory and DraftArchive classes in the narrow disabled-policy reproducer');args=parser.parse_args()
    source=ROOT/'app/src/main/java/local/pocketchat'
    whole=['LocalDraftPolicy.java','PageMemory.java','DraftArchive.java','BrowserSessionStore.java']
    before=subprocess.check_output(['git','rev-parse',args.before_ref+'^{commit}'],cwd=ROOT,text=True).strip() if args.before_ref else None
    partial={'AppPrefs.java':['static boolean enabled(','static void apply('], 'GeckoWebView.java':['void restoreCheckpoint(']}
    if not before:partial['WebReplyObserver.java']=['static boolean webJob(','boolean archiveNavigation(']
    inputs=[source/name for name in whole+list(partial)]+sorted(HERE.rglob('*.java'))+[pathlib.Path(__file__).resolve()]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    selected={name:((subprocess.check_output(['git','show',before+':app/src/main/java/local/pocketchat/'+name],cwd=ROOT)) if before and name in ('PageMemory.java','DraftArchive.java') else (source/name).read_bytes()) for name in whole}
    with tempfile.TemporaryDirectory(prefix='draft-policy-host-') as temporary:
        temp=pathlib.Path(temporary);package=temp/'local/pocketchat';package.mkdir(parents=True)
        for name in whole:(package/name).write_bytes(selected[name])
        template=(HERE/'LocalDraftPolicyHost.java').read_text()
        prefs=(source/'AppPrefs.java').read_text();keys=prefs[prefs.index('static final String[] KEYS='):prefs.index(';',prefs.index('static final String[] KEYS='))+1]
        template=template.replace('/* APPPREFS */',keys+'\n'+'\n'.join(member(prefs,n) for n in partial['AppPrefs.java']))
        template=template.replace('/* RESTORE */',member((source/'GeckoWebView.java').read_text(),'void restoreCheckpoint('))
        if before:
            # Keep the original four-assertion historical workload independent
            # of APIs added to newer archival classes. It never runs this case.
            template=template.replace(member(template,'static void navigationArchive('),'',1)
            assert template.count('restore();navigationArchive();')==1
            template=template.replace('restore();navigationArchive();','restore();',1).replace('/* ARCHIVE_OBSERVER */','')
        else:template=template.replace('/* ARCHIVE_OBSERVER */','\n'.join(member((source/'WebReplyObserver.java').read_text(),n) for n in partial['WebReplyObserver.java']))
        (package/'LocalDraftPolicyHost.java').write_text(template)
        java=[*package.glob('*.java'),*sorted((HERE/'stubs').rglob('*.java'))]
        binary=lambda name:str(args.java_home/'bin'/name) if args.java_home else name
        subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(temp),*map(str,java)],check=True)
        result=subprocess.run([binary('java'),'-Ddraft.before='+str(bool(before)).lower(),'-cp',str(temp)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.LocalDraftPolicyHost'],capture_output=True,text=True)
        if not result.stdout.strip():raise RuntimeError(result.stderr)
        report=json.loads(result.stdout)
        unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
        report.update(sourceCommit=commit,beforeRef=before,selectedProductionClasses={name:{'sourceCommit':before if before and name in ('PageMemory.java','DraftArchive.java') else commit,'sha256':hashlib.sha256(raw).hexdigest(),'workingTree':not (before and name in ('PageMemory.java','DraftArchive.java'))} for name,raw in selected.items()},sourceFiles=hashes,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=unchanged,actualAndroidExecution=False,productionClasses=whole,productionMethods=partial,scope='Complete production policy/PageMemory/archive/session-store classes plus exact AppPrefs and Gecko restore methods. Controlled Android/SQLite/SDK adapters and real JVM workers/files; no actual Android SQLite, AtomicFile durability, Gecko native restore or live webpage claim.')
        if not unchanged:report['status']='invalid-source-changed'
        if result.stderr:report['stderr']=result.stderr
        raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(raw)
        print(raw,end='')
        if result.returncode or report['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
