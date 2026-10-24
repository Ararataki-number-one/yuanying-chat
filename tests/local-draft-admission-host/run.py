#!/usr/bin/env python3
"""Execute real PageMemory admission and the F04 URL-only fixture adaptation on JVM."""
import argparse, hashlib, json, os, pathlib, re, subprocess, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent

def member(text,needle):
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=pathlib.Path)
    parser.add_argument('--json-jar',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    source=ROOT/'app/src/main/java/local/pocketchat';fixture=ROOT/'tests/gecko/GeckoLocalDraftIntegration.java'
    selections={
      'MEMORY':(source/'PageMemory.java',['String scope(','static String address(','static boolean completeDraft(','static boolean hasDraft(','void remember(']),
      'CHAT_URL':(source/'MainActivity.java',['static boolean chatUrl(']),
      'SAME':(source/'WebReplyObserver.java',['static boolean same(']),
      'POLICY':(source/'LocalDraftPolicy.java',['static boolean enabled(','static long revision(','static boolean mayRestore(','static JSONObject snapshot(Context context,JSONObject value)','static JSONObject snapshot(Context context,JSONObject value,long capturedRevision)']),
      'APP_PREFS':(source/'AppPrefs.java',['static boolean enabled(','static void apply(']),
      'JSON':(source/'J.java',['static JSONObject obj(','static JSONObject parse(']),
      'HASH':(source/'NativeNetwork.java',['static String hash(']),
      'PUT':(source/'NetworkCatalog.java',['static void put(']),
      'BASE':(fixture,['String text(','static String quote(','static String canonical(']),
      'FIXTURE':(fixture,['static String memoryUrl(','static JSONObject memoryInput(','static void verifyMemoryInput(','void rememberCheck(','void retainPartial(','static String sha(','boolean current(','void fail(']),
    }
    inputs={path for path,_ in selections.values()}|{source/'Sha256.java'}|{p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    template=(HERE/'AdmissionHost.java.in').read_text();methods=[]
    for marker,(path,needles) in selections.items():
        raw=path.read_text();chunks=[]
        for needle in needles:
            part=member(raw,needle);chunks.append(part);methods.append(dict(file=str(path.relative_to(ROOT)),signature=needle,startLine=raw[:raw.index(needle)].count('\n')+1,sha256=hashlib.sha256(part.encode()).hexdigest()))
        template=template.replace('/* '+marker+' */','\n'.join(chunks))
    observation_template=(HERE/'RestoreObservationHost.java.in').read_text();observation_parts=[]
    raw=fixture.read_text()
    for needle in ('static JSONObject restoreChecks(','static boolean sameCookies('):
        part=member(raw,needle);observation_parts.append(part)
        methods.append(dict(file=str(fixture.relative_to(ROOT)),signature=needle,startLine=raw[:raw.index(needle)].count('\n')+1,sha256=hashlib.sha256(part.encode()).hexdigest()))
    observation_template=observation_template.replace('/* OBSERVATIONS */','\n'.join(observation_parts))
    constants={
      'MAIN_ORIGIN':(source/'MainActivity.java',r'static final String ORIGIN=[^;]+;'),
      'APP_KEYS':(source/'AppPrefs.java',r'static final String\[\] KEYS=[^;]+;'),
      'FIXTURE_CONSTANTS':(fixture,r'static final String ACTION=[^;]+;'),
    }
    for marker,(path,pattern) in constants.items():template=template.replace('/* '+marker+' */',re.search(pattern,path.read_text()).group())
    baseline=json.loads((HERE/'before-source.json').read_text());before=(HERE/'BeforeRememberCheck.java.in').read_text().rstrip('\n')
    if hashlib.sha256(before.encode()).hexdigest()!=baseline['memberSha256']:raise AssertionError('Immutable baseline method changed')
    template=template.replace('/* BEFORE */',before)
    with tempfile.TemporaryDirectory(prefix='local-draft-admission-') as directory:
        temp=pathlib.Path(directory);package=temp/'local/pocketchat';package.mkdir(parents=True)
        (package/'AdmissionHost.java').write_text(template)
        (package/'RestoreObservationHost.java').write_text(observation_template)
        (package/'Sha256.java').write_bytes((source/'Sha256.java').read_bytes())
        sources=[*package.glob('*.java'),*sorted((HERE/'adapters').rglob('*.java'))]
        binary=lambda name:str(args.java_home/'bin'/name) if args.java_home else name
        subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(temp),*map(str,sources)],check=True)
        execution=subprocess.run([binary('java'),'-cp',str(temp)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.AdmissionHost'],text=True,capture_output=True)
        if not execution.stdout.strip():raise RuntimeError(execution.stderr)
        report=json.loads(execution.stdout)
        observation_execution=subprocess.run([binary('java'),'-cp',str(temp)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.RestoreObservationHost'],text=True,capture_output=True)
        if not observation_execution.stdout.strip():raise RuntimeError(observation_execution.stderr)
        report['restoreObservationControls']=json.loads(observation_execution.stdout)
        if observation_execution.returncode or report['restoreObservationControls'].get('status')!='passed':
            report['status']='failed-restore-observation-controls'
        if observation_execution.stderr:report['restoreObservationStderr']=observation_execution.stderr
    unchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
    report.update(sourceCommit=commit,sourceFiles=hashes,productionMembers=methods,beforeSource=baseline,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=unchanged,actualAndroidExecution=False,actualGeckoExecution=False,realChatGptPageMemoryCapture=False,productionAdmissionExecuted=True,scope='Exact MainActivity.chatUrl, WebReplyObserver.same, PageMemory admission, LocalDraftPolicy and AppPrefs methods with exact F04 fixture adaptation, retainPartial, sha, current and fail methods. java.net.URI is a limited adapter for the explicit absolute URL cases; preferences, event sink and worker shutdown use host adapters. No Android durability, Gecko DOM/SDK capture, cookies, SDK restore or real ChatGPT capture claim.')
    if not unchanged:report['status']='invalid-source-changed'
    if execution.stderr:report['stderr']=execution.stderr
    args.output.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n';args.output.write_text(raw);print(raw,end='')
    if execution.returncode or report['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
