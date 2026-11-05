#!/usr/bin/env python3
"""Execute the complete production popup helper at declared JVM application/UI boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at

SUBSTITUTIONS={
    'MainActivity':'ActivityBoundary','Activity':'ActivityBoundary','Application':'ApplicationBoundary',
    'Context':'ContextBoundary','Bundle':'BundleBoundary','ViewTreeObserver':'TreeBoundary',
    'View':'ViewBoundary','Button':'ButtonBoundary','FrameLayout':'FrameBoundary','Gravity':'GravityBoundary',
    'GeckoSession':'SessionBoundary','GeckoWebView':'WebBoundary','ChatSession':'OwnerBoundary',
    'ReferenceUi':'UiBoundary','GeckoTimeZoneUi':'TimezoneBoundary','DesignUi':'DesignBoundary',
    'PageMemory':'MemoryBoundary','LocalDraftPolicy':'DraftPolicyBoundary','AppPrefs':'AppPrefsBoundary',
    'Profiles':'ProfilesBoundary','ProfileCatalog':'CatalogBoundary','DraftArchive':'ArchiveBoundary',
    'EnvironmentSpec':'EnvironmentSpecBoundary','Uri':'UriBoundary',
}
MUTATIONS=(
    ('route-fence','&&route.equals(view.ipRouteStamp())','', 'fence:route','Changed popup capability never navigates: route'),
    ('paused-lifecycle','public void onActivityPaused(Activity activity){if(activity==lifecycleActivity)invalidate();}','public void onActivityPaused(Activity activity){}','focus','Pause then resume cannot resurrect the old confirmation'),
    ('changed-input','&&saved.optString("draft").equals(current.optString("draft"))','','inputs','Changed GPT input is never replaced after its old copy was archived'),
    ('disabled-draft-save','if(!value.manual&&PageMemory.hasDraft(value.page)){','if(PageMemory.hasDraft(value.page)){','gpt','Disabled saving never archives while still rereading the exact GPT input'),
    ('environment-writer-lease','ProfileCatalog.get(owner.context).withIdentity(identity,()->DraftArchive.get(owner.context).save(value.target.source,value.page.optString("draft"),"打开被拦截链接前草稿",value.draftRevision))','DraftArchive.get(owner.context).save(value.target.source,value.page.optString("draft"),"打开被拦截链接前草稿",value.draftRevision)','inputs','A stale environment cannot publish an archived draft into its replacement'),
    ('unknown-final-task','!idle(guard,web.owner,true)||','','inputs','Unknown final task guard cannot authorize page replacement'),
    ('own-operation-deadlock','(!value.operation||ownCapture)','!value.operation','gpt','GPT rereads twice and rechecks tasks before one normal browse'),
)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def member(text,needle):
    if text.count(needle)!=1:raise ValueError('Unique complete production member required: '+needle)
    return member_at(text,text.index(needle))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--json-jar',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    def java(name):
        result=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not result:parser.error('An existing JDK is required')
        return result

    pure=['J.java','TaskGuardSnapshot.java','BrowserSettingsPolicy.java','BrowserRuntimePolicy.java','BrowserAddressPolicy.java','GeckoNavigationPolicy.java','RequestIdentityAudit.java','RequestIdentityLanguages.java']
    selected=['GeckoPopupNavigationUi.java','GeckoTimeZoneUi.java','MainActivity.java','PageMemory.java','LocalDraftPolicy.java','EnvironmentSpec.java']
    files=[PROD/name for name in pure+selected]+[HERE/'PopupHost.java.in',Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py']
    contents={path:path.read_bytes() for path in files};hashes={str(path.relative_to(ROOT)):sha(raw) for path,raw in contents.items()};jar_hash=sha(args.json_jar.read_bytes())
    sources={name:contents[PROD/name].decode() for name in selected}
    production=sources['GeckoPopupNavigationUi.java']
    bodies={
        '@TIMEZONE_MEMBERS@':member(sources['GeckoTimeZoneUi.java'],'static final class Fence')+'\n'+member(sources['GeckoTimeZoneUi.java'],'static String busy('),
        '@MEMORY_METHODS@':member(sources['PageMemory.java'],'static boolean completeDraft(')+'\n'+member(sources['PageMemory.java'],'static boolean hasDraft('),
        '@DRAFT_METHODS@':member(sources['LocalDraftPolicy.java'],'static boolean enabled(')+'\n'+member(sources['LocalDraftPolicy.java'],'static long revision('),
        '@CHAT_METHOD@':member(sources['MainActivity.java'],'static boolean chatUrl('),
        '@IDENTITY@':member(sources['EnvironmentSpec.java'],'static final class Identity'),
    }
    template=contents[HERE/'PopupHost.java.in'].decode()
    def generate(actual):
        actual=re.sub(r'^(?:package |import ).*\n','',actual,flags=re.MULTILINE)
        result=template.replace('@UI_SOURCE@',actual)
        for marker,body in bodies.items():result=result.replace(marker,body)
        for before,after in SUBSTITUTIONS.items():result=re.sub(r'\b'+re.escape(before)+r'\b',after,result)
        return result

    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.unlink(missing_ok=True)
    artifacts=args.output.parent/(args.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='gecko-popup-host-') as temporary:
        temporary=Path(temporary)
        def build(actual,label):
            folder=artifacts/label;folder.mkdir(exist_ok=True);source=folder/'PopupHost.java';source.write_text(generate(actual));classes=temporary/label
            command=[java('javac'),'--release','17','-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),str(source)]+[str(PROD/name) for name in pure]
            run=subprocess.run(command,text=True,capture_output=True,timeout=60);(folder/'compile.command.json').write_text(json.dumps(command)+'\n');(folder/'compile.stdout.log').write_text(run.stdout);(folder/'compile.stderr.log').write_text(run.stderr)
            if run.returncode:raise RuntimeError(label+' compile failed:\n'+run.stderr)
            return classes
        def execute(classes,label,focus=None):
            folder=artifacts/label;folder.mkdir(exist_ok=True);command=[java('java'),'-cp',str(classes)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.PopupHost']+([focus] if focus else [])
            run=subprocess.run(command,text=True,capture_output=True,timeout=30);(folder/'run.command.json').write_text(json.dumps(command)+'\n');(folder/'run.stdout.log').write_text(run.stdout);(folder/'run.stderr.log').write_text(run.stderr);return run
        classes=build(production,'current');current=execute(classes,'current')
        if current.returncode:raise AssertionError('Actual popup workflow failed:\n'+current.stderr)
        report=json.loads(current.stdout)
        if report['status']!='passed' or not report['checks'] or not all(row['pass'] is True for row in report['checks']):raise AssertionError('Incomplete actual popup workload')
        for name,before,after,focus,expected in MUTATIONS:
            pristine=execute(classes,'pristine-'+name,focus)
            if pristine.returncode:raise AssertionError('Pristine focused popup check failed: '+name+pristine.stderr)
            if production.count(before)!=1:raise ValueError('Exact one-hunk popup mutation anchor changed: '+name)
            mutant=production.replace(before,after,1);changed=build(mutant,'mutation-'+name);denied=execute(changed,'mutation-'+name,focus)
            if denied.returncode==0 or 'AssertionError: '+expected not in denied.stderr:raise AssertionError('Intended popup boundary was not rejected: '+name+'\n'+denied.stderr)
            controls.append(dict(case=name,before=before,after=after,focus=focus,expectedAssertion=expected,pristinePassed=True,mutantRejected=True,exitCode=denied.returncode))
    changed=[name for name,value in hashes.items() if sha((ROOT/name).read_bytes())!=value]
    if sha(args.json_jar.read_bytes())!=jar_hash:changed.append(str(args.json_jar))
    result=dict(schema=1,status='passed' if not changed else 'failed',passed=report['passed'],total=report['total'],checks=report['checks'],mutationControls=controls,files=hashes,selectedMemberHashes={name:sha(body.encode()) for name,body in bodies.items()},wholePopupSourceExtracted=True,declaredSubstitutions=SUBSTITUTIONS,jsonJar=dict(path=str(args.json_jar.resolve()),sha256=jar_hash),javaHome=str(args.java_home.resolve()) if args.java_home else None,executionInputsUnchanged=not changed,changedInputs=changed,actualAndroidExecution=False,actualGeckoExecution=False,actualSqliteExecution=False,scope=report['scope'])
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],passed=result['passed'],total=result['total'],mutants=len(controls),executionInputsUnchanged=result['executionInputsUnchanged'],output=str(args.output))))
    if changed:raise ValueError('Popup execution inputs changed; final receipt rejected')


if __name__=='__main__':main()
