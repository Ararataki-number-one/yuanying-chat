#!/usr/bin/env python3
"""Run actual Gecko generic-route helper methods with the real lease registry."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from run import ROOT, HERE, PROD, digest, member_at

MEMBERS = ('static final class ProtectionRestore', 'boolean generalRouteReady(',
           'boolean retainGeneralRoute(', 'void forgetGeneralRoute(',
           'void releaseGeneralRoutes(', 'void routeAdmissionChanged(',
           'void queueGeneralRouteRetry(', 'void retryGeneralRoutes(',
           'public GeckoResult<GeckoSession> onNewSession(', 'boolean hasWebsitePages(')
FIELDS = ('final Set<GeckoSession> generalSessions=',
          'final Map<GeckoSession,ChromiumRouteLease.Handle> generalRoutes=',
          'final Map<GeckoSession,String> deferredGeneralLoads=',
          'final Runnable routeLeaseChanged=',
          'final Map<GeckoSession,String> locations=',
          'final Set<GeckoSession> crashed=',
          'final ArrayList<GeckoSession> popups=')
MUTATIONS = (
    ('identity', 'return generalRoutes.keySet().containsAll(generalSessions);',
     'return generalRoutes.size()>=generalSessions.size();',
     'Readiness requires the exact desired session keys, not matching map sizes'),
    ('barrier', 'if(lease==null)return false;', 'if(lease==null)return true;',
     'Held change barrier permits zero generic page admission'),
    ('release', 'if(owner.guard.blocked||!owner.guard.routeProtected())releaseGeneralRoutes();',
     'if(owner.guard.blocked||!owner.guard.routeProtected())generalRoutes.size();',
     'Blocked admission releases actual held routes before callback work'),
    ('destroyed', 'if(session==null||destroyed||failed||crashed.contains(session))return false;', 'if(session==null||failed||crashed.contains(session))return false;', 'Unavailable existing lease cannot authorize another admission: destroyed'),
    ('failed', 'if(session==null||destroyed||failed||crashed.contains(session))return false;', 'if(session==null||destroyed||crashed.contains(session))return false;', 'Unavailable page acquires no route lease: failed'),
    ('crashed', 'if(session==null||destroyed||failed||crashed.contains(session))return false;', 'if(session==null||destroyed||failed)return false;', 'Unavailable page acquires no route lease: crashed'),
    ('popup-failure', 'catch(RuntimeException unavailable){if(lease!=null)lease.close();',
     'catch(RuntimeException unavailable){',
     'Popup constructor failure releases its unregistered acquired lease'),
    ('popup-failed', 'if(destroyed||failed||crashed.contains(s)||s!=current',
     'if(destroyed||crashed.contains(s)||s!=current',
     'Late unavailable opener cannot construct or acquire a popup: failed'),
    ('popup-crashed', 'if(destroyed||failed||crashed.contains(s)||s!=current',
     'if(destroyed||failed||s!=current',
     'Late unavailable opener cannot construct or acquire a popup: crashed'),
    ('private-retention', 'if(GeckoNavigationPolicy.publicWeb(target)&&!MainActivity.chatUrl(target))generalSessions.add(session);',
     'if(allowedUrl(target)&&!MainActivity.chatUrl(target))generalSessions.add(session);',
     'Extended private admission is not a public retained surface'),
    ('private-popup', 'if(GeckoNavigationPolicy.publicWeb(target)&&!MainActivity.chatUrl(target)){lease=ChromiumRouteLease.acquireSurface();',
     'if(allowedUrl(target)&&!MainActivity.chatUrl(target)){lease=ChromiumRouteLease.acquireSurface();',
     'Extended private popup admission does not retain a public route'),
    ('private-pages', 'return !generalSessions.isEmpty()||GeckoNavigationPolicy.publicWeb(getUrl())&&!MainActivity.chatUrl(getUrl());',
     'return !generalSessions.isEmpty()||allowedUrl(getUrl())&&!MainActivity.chatUrl(getUrl());',
     'Extended private current URL is not a public website page'),
    ('guard-release', 'session.web.routeAdmissionChanged();',
     'session.web.getSettings();',
     'Blocked admission releases actual held routes before callback work'),
    ('popup-timezone', 'if(!owner.timeZone.popupAllowed())',
     'if(false)',
     'Unconfirmed or custom timezone rejects the unopened popup before construction'),
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--json-jar',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    def tool(name):
        value=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not value:parser.error('Provide --java-home containing '+name)
        return value
    production=PROD/'GeckoWebView.java';template=HERE/'RouteHoldHost.java.in'
    complete=[PROD/name for name in ('ChromiumRouteLease.java','BrowserRuntimePolicy.java',
              'BrowserAddressPolicy.java','GeckoNavigationPolicy.java','J.java')]
    guard=PROD/'BrowserNetworkGuard.java'
    files=[production,guard,template,Path(__file__).resolve(),HERE/'run.py']+complete
    hashes={str(path.relative_to(ROOT)):digest(path) for path in files};json_hash=digest(args.json_jar)
    source=production.read_text();selected=[]
    for needle in MEMBERS:
        positions=[source.index(needle)]
        if source.count(needle)!=1:raise ValueError('Review actual helper declaration: '+needle)
        selected.append(member_at(source,positions[0]))
    field_lines=[]
    for needle in FIELDS:
        lines=[line.strip() for line in source.splitlines() if line.strip().startswith(needle)]
        if len(lines)!=1:raise ValueError('Review actual identity-map field: '+needle)
        field_lines.append(lines[0])
    body='\n'.join(selected);fields='\n'.join(field_lines)
    guard_source=guard.read_text();guard_needle='void setBlocked('
    if guard_source.count(guard_needle)!=1:raise ValueError('Review actual process request gate setter')
    guard_body=member_at(guard_source,guard_source.index(guard_needle))
    def generate(members,guard_members=guard_body):
        return template.read_text().replace('@PRODUCTION_MEMBERS@',members.replace('GeckoSession','SessionBoundary').replace('GeckoResult','ResultBoundary')).replace('@PRODUCTION_FIELDS@',fields.replace('GeckoSession','SessionBoundary')).replace('@GUARD_MEMBERS@',guard_members)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    artifacts=args.output.parent/(args.output.stem+'-artifacts');artifacts.mkdir(parents=True,exist_ok=True)
    generated=generate(body);(artifacts/'RouteHoldHost.java').write_text(generated)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='gecko-route-hold-host-') as temporary:
        work=Path(temporary)
        def compile_and_run(text,label,focus=None):
            selected_work=work/label;selected_work.mkdir(parents=True)
            java=selected_work/'RouteHoldHost.java';java.write_text(text);classes=selected_work/'classes'
            evidence=artifacts/label;evidence.mkdir(parents=True,exist_ok=True)
            (evidence/'RouteHoldHost.java').write_text(text)
            compile_command=[tool('javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),str(java)]+[str(path) for path in complete]
            compiled=subprocess.run(compile_command,capture_output=True,text=True,timeout=60)
            (evidence/'compile.command.json').write_text(json.dumps(compile_command)+'\n');(evidence/'compile.stdout.log').write_text(compiled.stdout);(evidence/'compile.stderr.log').write_text(compiled.stderr)
            if compiled.returncode:raise RuntimeError(compiled.stderr)
            command=[tool('java'),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.RouteHoldHost']+([] if focus is None else [focus])
            ran=subprocess.run(command,capture_output=True,text=True,timeout=30)
            (evidence/'run.command.json').write_text(json.dumps(command)+'\n');(evidence/'run.stdout.log').write_text(ran.stdout);(evidence/'run.stderr.log').write_text(ran.stderr)
            return ran
        ran=compile_and_run(generated,'current')
        if ran.returncode:raise RuntimeError(ran.stdout+ran.stderr)
        report=json.loads(ran.stdout)
        for index,(case,before,after,assertion) in enumerate(MUTATIONS):
            if body.count(before)+guard_body.count(before)!=1:raise ValueError('Review one-hunk negative control: '+case)
            pristine=compile_and_run(generated,'pristine-'+case,case)
            if pristine.returncode or json.loads(pristine.stdout)['status']!='passed':raise AssertionError('Pristine focused schedule failed: '+case+pristine.stderr)
            mutant=generate(body.replace(before,after,1),guard_body.replace(before,after,1))
            rejected=compile_and_run(mutant,'mutation-'+case,case)
            if rejected.returncode==0 or 'AssertionError: '+assertion not in rejected.stderr:raise AssertionError('Missing exact expected mutated-guard failure: '+case+rejected.stderr)
            controls.append(dict(case=case,removed=before,replacement=after,pristinePassed=True,mutantRejected=True,expectedAssertion=assertion,mutantGeneratedSha256=hashlib.sha256(mutant.encode()).hexdigest()))
    unchanged=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in files) and digest(args.json_jar)==json_hash
    report.update(status='passed' if unchanged else 'source-changed',sourceFiles=hashes,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),jsonJarSha256=json_hash,generatedSourceSha256=hashlib.sha256(generated.encode()).hexdigest(),productionMembers=MEMBERS,productionFields=FIELDS,guardProductionMembers=['BrowserNetworkGuard.setBlocked'],negativeControls=controls,executionInputsUnchanged=unchanged,boundarySubstitutions=['GeckoSession type tokens → explicitly declared SessionBoundary, with controlled isOpen/loadUri/state interfaces','GeckoResult type tokens → ResultBoundary; newSession constructor success/failure and posted activate are explicit controlled JVM interfaces','Owner/protection/handler/Looper and routeProtected/allowed reads are declared controlled JVM boundaries','TimeZoneBoundary.popupAllowed is an explicit prepared-system versus denied-custom-or-unknown permission input, not execution of the timezone controller','loadSessionUri is the explicit already-prepared routing boundary; actual timezone loading/restoration is separately exercised by gecko-timezone-routing-host','BrowserNetworkGuard.setBlocked is extracted unchanged; WebSettings.setBlockNetworkLoads is an explicitly counted app boundary, not an Android or SDK execution','MainActivity.chatUrl delegates to actual BrowserRuntimePolicy.official with JVM URI','allowedUrl delegates to actual GeckoNavigationPolicy.publicWeb plus an explicit fixture admission set; public route classification still executes actual GeckoNavigationPolicy.publicWeb','Constructor listener registration and teardown are explicit fixture lifecycle boundaries; actual Gecko construction/destroy are not executed'],scope='Actual Gecko generic-route retention/admission/retry/release/current-page methods, actual BrowserNetworkGuard.setBlocked and actual process lease registry with controlled JVM sessions, settings and callback queue. No Android, Gecko SDK, native protection API, website or network execution.')
    if not report['checks'] or not all(row['pass'] is True for row in report['checks']):raise AssertionError('Route helper workload failed')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],negativeControls=len(controls),executionInputsUnchanged=unchanged,output=str(args.output)),ensure_ascii=False))
    if not unchanged:raise SystemExit(1)


if __name__=='__main__':main()
