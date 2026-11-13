#!/usr/bin/env python3
"""Run current Gecko activation/retirement with real request and route registries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at

ACTIVATE='private void activate('
CLOSE='private boolean closePopup(GeckoSession old,boolean returnNavigation)'
OWNER='private boolean activationCurrent('
FENCE='if(!activationCurrent(previous,session,navigation,wasOpen))return;'
READ_FENCE='if(!activationCurrent(session,session,navigation,wasOpen)||!selectedUrl.equals(url))return;'
MUTATIONS=(
    ('cancel-owner',ACTIVATE,(
        ('if(previousPort!=null)callbacks.cancel(previousPort);\n    '+FENCE,'if(previousPort!=null)callbacks.cancel(previousPort);',1),
    ),'cancellation','Cancellation cannot replace a newer command with an older selected session'),
    ('detach-before-cancel',ACTIVATE,(
        ('WebExtension.Port previousPort=ports.get(previous);\n    if(previousPort!=null)callbacks.cancel(previousPort);\n    '+FENCE+'\n    if(surface.getSession()!=null)surface.releaseSession();\n    if(previous!=null&&previous.isOpen())previous.setActive(false);',
         'if(surface.getSession()!=null)surface.releaseSession();\n    if(previous!=null&&previous.isOpen())previous.setActive(false);\n    WebExtension.Port previousPort=ports.get(previous);\n    if(previousPort!=null)callbacks.cancel(previousPort);\n    '+FENCE,1),
    ),'cancellation','Cancellation cannot replace a newer command with an older selected session'),
    ('auxiliary-owner',ACTIVATE,(
        ('closeExitIpPage();\n    '+FENCE,'closeExitIpPage();',1),
    ),'auxiliary','Auxiliary-page close callback keeps the newer navigation owner'),
    ('popup-action-owner',ACTIVATE,(
        ('blockedPopups.invalidate();\n    '+FENCE,'blockedPopups.invalidate();',1),
    ),'auxiliary','Popup-action invalidation cannot overwrite its synchronous navigation'),
    ('tracked-target',OWNER,(
        ('&&locations.containsKey(target)','',1),
    ),'target','An untracked target is rejected before changing the visible surface'),
    ('open-target',OWNER,(
        ('&&(!wasOpen||target.isOpen())','',1),
    ),'cancellation','Cancellation cannot attach a target that closed during activation'),
    ('configuration-owner',ACTIVATE,(
        ('configure(desktop,owner.privacy.level());\n    if(!activationCurrent(session,session,navigation,wasOpen))return;','configure(desktop,owner.privacy.level());',1),
    ),'selected','Configuration reentry cannot publish reading state for its retired navigation'),
    ('reading-start-owner',ACTIVATE,(
        ('owner.reading.started(selectedUrl);\n      '+READ_FENCE,'owner.reading.started(selectedUrl);',1),
    ),'selected','Reading-start reentry cannot measure or reveal the superseded page'),
    ('reading-measure-owner',ACTIVATE,(
        ('owner.reading.viewportMeasured(viewportWidths.getOrDefault(session,0f)*readingLayout);\n      '+READ_FENCE,'owner.reading.viewportMeasured(viewportWidths.getOrDefault(session,0f)*readingLayout);',1),
    ),'selected','Reading-measurement reentry cannot publish old-page visibility'),
    ('same-epoch-document',ACTIVATE,(
        ('||!selectedUrl.equals(url)','',2),
    ),'selected','A same-epoch URL change during reading start cannot publish old-document measurements'),
    ('close-timezone-owner',CLOSE,(
        ('else if(current==old&&!navigationCurrent(source,closingNavigation))return false;','',1),
    ),'closing','Popup retirement cannot overwrite a newer navigation from its time-zone callback'),
    ('close-reselected-owner',CLOSE,(
        ('if(destroyed||owner.deleted||current==old)return false;','if(destroyed||owner.deleted)return false;',1),
    ),'closing','A return-navigation callback can reclaim the original popup before retirement'),
    ('retirement-request-order',CLOSE,(
        ('locations.remove(old);','',1),
        ('finally{if(port!=null)retireAppearance(port);if(old.isOpen())old.close();}',
         'finally{if(port!=null)retireAppearance(port);if(old.isOpen())old.close();}\n    locations.remove(old);',1),
    ),'closing','Retirement callbacks cannot reactivate an already untracked popup'),
    ('retirement-lease-order',CLOSE,(
        ('locations.remove(old);','',1),
        ('forgetGeneralRoute(old);','forgetGeneralRoute(old);locations.remove(old);',1),
    ),'closing','A real route-lease listener cannot reactivate a retiring popup'),
    ('retirement-finally',CLOSE,(
        ('finally{if(port!=null)retireAppearance(port);if(old.isOpen())old.close();}',
         'finally{if(port!=null)retireAppearance(port);}\n    if(old.isOpen())old.close();',1),
    ),'closing','A retiring consumer exception cannot leak the now-untracked native popup'),
    ('close-all-cancel-owner',CLOSE,(
        ('if(port!=null){callbacks.cancel(port);retireAppearance(port);}\n      if(!navigationCurrent(source,closingNavigation))return false;',
         'if(port!=null){callbacks.cancel(port);retireAppearance(port);}',1),
    ),'closing','Close-all caller preserves its existing navigation ownership gate'),
    ('close-all-return-navigation','boolean closeWebsitePages(',(
        ('closePopup(popup,false)','closePopup(popup,true)',1),
    ),'close-all','Close-all composes real popup activation without claiming a return navigation'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',required=True,type=Path)
    parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    source=ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java'
    registry=ROOT/'app/src/main/java/local/pocketchat/BrowserBridgeRequests.java'
    leases=ROOT/'app/src/main/java/local/pocketchat/ChromiumRouteLease.java'
    utility=ROOT/'app/src/main/java/local/pocketchat/J.java'
    template=HERE/'ActivationHost.java.in'
    paths=[source,registry,leases,utility,template,Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py']
    hashes={str(path.relative_to(ROOT)):digest(path) for path in paths}
    dependency=digest(args.json_jar)
    java_tools={name:args.java_home/'bin'/name for name in ('java','javac')}
    tool_hashes={name:digest(path) for name,path in java_tools.items()}
    text=source.read_text()
    names=['private void activate(','private boolean navigationCurrent(','private boolean closePopup(GeckoSession old,boolean returnNavigation)','boolean closeWebsitePages(','void forgetGeneralRoute(']
    if 'private boolean activationCurrent(' in text:
        names.append('private boolean activationCurrent(')
    for name in names:
        if text.count(name)!=1:raise ValueError('One complete current production declaration required: '+name)
    members={name:member_at(text,text.index(name)) for name in names}
    fixture=template.read_text()
    def generate(selected):return fixture.replace('__METHODS__','\n'.join(selected.values()))
    rendered=generate(members)
    report=dict(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                sourceFiles=hashes,productionMembers=names,
                selectedMethodsSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in members.items()},
                generatedHostSha256=hashlib.sha256(rendered.encode()).hexdigest(),
                jsonJarSha256=dependency,javaHome=str(args.java_home.resolve()),javaToolSha256=tool_hashes,
                actualAndroidExecution=False,actualGeckoExecution=False,
                scope='Complete current GeckoWebView activate/closePopup/closeWebsitePages/forgetGeneralRoute and ownership predicates plus whole production BrowserBridgeRequests, ChromiumRouteLease and J. Explicit session/surface/reopen, navigation claim, auxiliary-page close, time-zone retirement, configuration and reading boundaries. No native Gecko session opening, rendering, real browser navigation or SDK callback timing is claimed.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.unlink(missing_ok=True)
    artifacts=args.output.parent/(args.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='gecko-activation-host-') as temporary:
        work=Path(temporary)

        def build(generated,label):
            folder=artifacts/label;folder.mkdir(exist_ok=True)
            java=folder/'ActivationHost.java';java.write_text(generated)
            classes=work/label
            command=[str(java_tools['javac']),'-encoding','UTF-8','--release','8',
                     '-cp',str(args.json_jar),'-d',str(classes),str(java),str(registry),str(leases),str(utility)]
            compiled=subprocess.run(command,capture_output=True,text=True,timeout=60)
            (folder/'compile.command.json').write_text(json.dumps(command)+'\n')
            (folder/'compile.stdout.log').write_text(compiled.stdout)
            (folder/'compile.stderr.log').write_text(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError(label+' activation host did not compile:\n'+compiled.stderr)
            return classes

        def execute(classes,label,focus='all'):
            folder=artifacts/label;folder.mkdir(exist_ok=True)
            command=[str(java_tools['java']),'-cp',str(classes)+os.pathsep+str(args.json_jar),'local.pocketchat.ActivationHost',focus]
            result=subprocess.run(command,capture_output=True,text=True,timeout=30)
            (folder/'run.command.json').write_text(json.dumps(command)+'\n')
            (folder/'run.stdout.log').write_text(result.stdout)
            (folder/'run.stderr.log').write_text(result.stderr)
            return result

        classes=build(rendered,'current')
        result=execute(classes,'current')
        report.update(compiled=True,returncode=result.returncode,stderr=result.stderr)
        if result.returncode==0:
            report.update(json.loads(result.stdout))
            for label,name,edits,focus,expected in MUTATIONS:
                pristine=execute(classes,'pristine-'+label,focus)
                if pristine.returncode:raise AssertionError('Current focused behavior failed: '+label+'\n'+pristine.stderr)
                changed=dict(members)
                for before,after,count in edits:
                    if changed[name].count(before)!=count:raise ValueError('Current semantic mutation anchor changed: '+label)
                    changed[name]=changed[name].replace(before,after,count)
                mutant=generate(changed)
                mutated_classes=build(mutant,'mutation-'+label)
                failed=execute(mutated_classes,'mutation-'+label,focus)
                if failed.returncode==0 or 'java.lang.AssertionError: '+expected not in failed.stderr:
                    raise AssertionError('Compiled semantic mutation escaped its intended assertion: '+label+'\n'+failed.stderr)
                controls.append(dict(name=label,productionMember=name,focus=focus,compiled=True,pristinePassed=True,
                                     runtimeRejected=True,expectedAssertion=expected,exitCode=failed.returncode,
                                     generatedHostSha256=hashlib.sha256(mutant.encode()).hexdigest(),
                                     stderrSha256=hashlib.sha256(failed.stderr.encode()).hexdigest()))
        else:
            report.update(status='failed',passed=0)
    report.update(executionInputsUnchanged=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in paths),
                  dependencyUnchanged=digest(args.json_jar)==dependency,
                  javaToolsUnchanged=all(digest(path)==tool_hashes[name] for name,path in java_tools.items()),
                  compiledCounterfeits=controls)
    if not report['executionInputsUnchanged'] or not report['dependencyUnchanged'] or not report['javaToolsUnchanged']:
        report['status']='input-changed'
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],compiledCounterfeits=len(controls),output=str(args.output))))
    if report['status']!='passed':
        print(report.get('stderr',''),file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':
    main()
