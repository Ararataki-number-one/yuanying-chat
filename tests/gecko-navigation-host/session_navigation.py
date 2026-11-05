#!/usr/bin/env python3
"""Execute actual session navigation, browser-location persistence and restoration."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from run import ROOT,HERE,PROD,digest,member_at

NEEDLES=('void browse(','void rememberBrowserLocation(','void navigate(','void beginNavigation(','void loadNavigation(','String resumeUrl(','static boolean resumable(','boolean targetMatches(','boolean uploading(','boolean fileWorkActive(','boolean resourceFilesActive(')
PREF_NEEDLES=('private static SharedPreferences preferences(','static String home(','static String normalizeHome(')
MUTATIONS=(
 ('transcript-isolation','void navigate(','webStore.current(chat?url:"")','webStore.current(url)','generic','Generic browse has no GPT transcript store binding: http://example.com/article?q=1'),
 ('conversation-isolation','void navigate(','}else{entries=new JSONArray();state=new JSONObject();stateEpoch=-1;}','}else{conversation=url;entries=new JSONArray();state=new JSONObject();stateEpoch=-1;}','generic','Generic browse preserves GPT conversation and saved conversation: http://example.com/article?q=1'),
 ('diagnostic-persistence','void rememberBrowserLocation(','RequestIdentityAudit.diagnosticUrl(url)||','','persistence','Private diagnostic or login location never replaces saved browser URL: https://detector.example.com/pocketchat-identity/v1/document?nonce=0123456789abcdef0123456789abcdef'),
 ('saved-browser-resume','String resumeUrl(','String saved=prefs.getString("geckoBrowserUrl","");if(resumable(saved))return saved;','String saved=prefs.getString("geckoBrowserUrl","");','resume','Saved generic browser location precedes old GPT conversation'),
 ('pending-confirmed','String resumeUrl(','if(resumable(confirmed))return confirmed;','if(false)return confirmed;','pending','Bound pending confirmed GPT URL wins over all browser restoration'),
 ('configured-home','String resumeUrl(','saved=prefs.getString("url",BrowserPreferences.home(context));','saved=prefs.getString("url","https://chatgpt.com/");','home','Fresh session honors configured BrowserPreferences home'),
 ('generic-unknown-file-work','void browse(','MainActivity.chatUrl(web.getUrl())&&fileWorkActive()','fileWorkActive()','busy','Unknown generic website upload does not invent a GPT navigation block'),
 ('cross-origin-target','boolean targetMatches(','return GeckoNavigationPolicy.sameTarget(url,navigationTarget);','return java.util.Objects.equals(URI.create(url).getPath(),URI.create(navigationTarget).getPath());','matching','Same path on another host is never the current navigation target'),
 ('generic-login-save','void rememberBrowserLocation(','MainActivity.chatUrl(url)&&LoginPagePolicy.login(url)','LoginPagePolicy.login(url)','persistence','Ordinary public login saves its browser location independently of GPT: https://accounts.google.com/o/oauth2/v2/auth'),
 ('generic-login-resume','static boolean resumable(','!(MainActivity.chatUrl(url)&&LoginPagePolicy.login(url))','!LoginPagePolicy.login(url)','persistence','Ordinary public login remains a resumable live generic website: https://accounts.google.com/o/oauth2/v2/auth'),
)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 def tool(name):
  result=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
  if not result:p.error('Provide --java-home containing '+name)
  return result
 source=PROD/'ChatSession.java';preferences=PROD/'BrowserPreferences.java';observer=PROD/'WebReplyObserver.java';template=HERE/'SessionNavigationHost.java.in'
 complete=[PROD/name for name in ('J.java','BrowserRuntimePolicy.java','BrowserAddressPolicy.java','GeckoNavigationPolicy.java','LoginPagePolicy.java','RequestIdentityAudit.java','RequestIdentityLanguages.java','ResourceUploadState.java')]
 files=[source,preferences,observer,template,Path(__file__).resolve(),HERE/'run.py']+complete;hashes={str(path.relative_to(ROOT)):digest(path) for path in files};json_hash=digest(a.json_jar)
 raw=source.read_text();selected=[]
 for needle in NEEDLES:
  offset=0;found=[]
  while True:
   at=raw.find(needle,offset)
   if at<0:break
   if not raw[raw.rfind('\n',0,at)+1:at].strip():found.append(member_at(raw,at))
   offset=at+len(needle)
  if not found:raise ValueError('Missing actual navigation declaration: '+needle)
  selected.extend((needle,value) for value in found)
 pref_raw=preferences.read_text();pref_parts=[member_at(pref_raw,pref_raw.index(needle)) for needle in PREF_NEEDLES]
 pref_fields=[line.strip() for line in pref_raw.splitlines() if line.strip().startswith('static final String ')]
 if len(pref_fields)!=3:raise ValueError('Review actual browser preference constants')
 same=member_at(observer.read_text(),observer.read_text().index('static boolean same('))
 def generate(parts):
  body='\n'.join(value for _,value in parts).replace('android.net.Uri.parse(','URI.create(').replace('System.currentTimeMillis()','Clock.wallMillis()')
  pref_body=re.sub(r'\bSharedPreferences\b','PrefsBoundary','\n'.join(pref_parts)).replace('Context context','ContextBoundary context').replace('Context.MODE_PRIVATE','ContextBoundary.MODE_PRIVATE')
  return template.read_text().replace('@PRODUCTION_MEMBERS@',body).replace('@PREFERENCE_MEMBERS@',pref_body).replace('@PREFERENCE_FIELDS@','\n'.join(pref_fields)).replace('@SAME_MEMBER@',same.replace('Uri.parse(','URI.create('))
 a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(parents=True,exist_ok=True);generated=generate(selected);(artifacts/'SessionNavigationHost.java').write_text(generated)
 controls=[]
 with tempfile.TemporaryDirectory(prefix='session-navigation-host-') as temporary:
  work=Path(temporary)
  def run(text,label,focus=None):
   folder=work/label;folder.mkdir(parents=True);java=folder/'SessionNavigationHost.java';java.write_text(text);classes=folder/'classes';logs=artifacts/label;logs.mkdir(parents=True,exist_ok=True);(logs/'SessionNavigationHost.java').write_text(text)
   command=[tool('javac'),'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(classes),str(java)]+[str(path) for path in complete]
   compiled=subprocess.run(command,capture_output=True,text=True,timeout=60);(logs/'compile.command.json').write_text(json.dumps(command)+'\n');(logs/'compile.stdout.log').write_text(compiled.stdout);(logs/'compile.stderr.log').write_text(compiled.stderr)
   if compiled.returncode:raise RuntimeError(compiled.stderr)
   command=[tool('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.SessionNavigationHost']+([] if focus is None else [focus]);ran=subprocess.run(command,capture_output=True,text=True,timeout=30)
   (logs/'run.command.json').write_text(json.dumps(command)+'\n');(logs/'run.stdout.log').write_text(ran.stdout);(logs/'run.stderr.log').write_text(ran.stderr);return ran
  ran=run(generated,'current')
  if ran.returncode:raise RuntimeError(ran.stdout+ran.stderr)
  report=json.loads(ran.stdout)
  for label,needle,before,after,focus,assertion in MUTATIONS:
   pristine=run(generated,'pristine-'+label,focus)
   if pristine.returncode or json.loads(pristine.stdout)['status']!='passed':raise AssertionError('Pristine focused navigation failed: '+label+pristine.stderr)
   matches=[i for i,(name,value) in enumerate(selected) if name==needle and before in value]
   if len(matches)!=1 or selected[matches[0]][1].count(before)!=1:raise ValueError('Review exact navigation negative control: '+label)
   changed=list(selected);i=matches[0];changed[i]=(changed[i][0],changed[i][1].replace(before,after,1));mutant=generate(changed);rejected=run(mutant,'mutation-'+label,focus)
   if rejected.returncode==0 or 'AssertionError: '+assertion not in rejected.stderr:raise AssertionError('Original focused assertion did not reject the intended mutant: '+label+rejected.stderr)
   controls.append(dict(case=label,productionMember=needle,removed=before,replacement=after,pristinePassed=True,mutantRejected=True,expectedAssertion=assertion,mutantGeneratedSha256=hashlib.sha256(mutant.encode()).hexdigest()))
 unchanged=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in files) and digest(a.json_jar)==json_hash
 report.update(status='passed' if unchanged else 'source-changed',sourceFiles=hashes,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),productionMembers=NEEDLES,productionPreferenceMembers=PREF_NEEDLES,selectedMethodsSha256=[dict(member=name,sha256=hashlib.sha256(value.encode()).hexdigest()) for name,value in selected],negativeControls=controls,executionInputsUnchanged=unchanged,jsonJarSha256=json_hash,generatedSourceSha256=hashlib.sha256(generated.encode()).hexdigest(),boundarySubstitutions=['Actual ChatSession browse/navigate overloads/beginNavigation/loadNavigation/remember/resume/resumable/targetMatches/file-work methods run with explicit Web/cache/store/memory/trace/privacy/audit/Handler/Prefs interfaces','Android Uri.parse → JVM URI.create in actual resume path and WebReplyObserver.same','System.currentTimeMillis() → fixed deterministic clock; SystemClock is a controlled elapsed clock','BrowserPreferences actual preferences/home/normalizeHome and constants use declared ContextBoundary/PrefsBoundary types','MainActivity.chatUrl delegates to actual BrowserRuntimePolicy.official with JVM URI','PageMemory.capture completion and document lookup are explicit controlled boundaries; its internal scripts are not executed','45-second navigation timeout is recorded but not executed; navigationTimeout/finishNavigation/wakePolling/resetReplyStability are declared bookkeeping boundaries'],scope='Actual ChatSession navigation and browser-location persistence/restoration consumer methods, actual browser-home preference methods, full actual navigation/login/diagnostic/resource-upload policies and JSON dependency. Controlled JVM browser/cache/store/memory/preferences/scheduler interfaces. No Android, Gecko SDK, actual DOM/SQLite/storage persistence, network, or website acceptance.')
 if not report['checks'] or not all(row['pass'] is True for row in report['checks']):raise AssertionError('Actual navigation checks failed')
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],negativeControls=len(controls),executionInputsUnchanged=unchanged,output=str(a.output)),ensure_ascii=False))
 if not unchanged:raise SystemExit(1)


if __name__=='__main__':main()
