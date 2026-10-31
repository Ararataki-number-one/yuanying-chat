#!/usr/bin/env python3
"""Focused production share46 snapshot checks; explicit Android/storage/proof adapters."""
import argparse,hashlib,json,pathlib,subprocess,shutil,sys
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--yaml-jar',type=pathlib.Path);p.add_argument('--ui-only',action='store_true');a=p.parse_args()
javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac');java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java')
if not javac or not java:p.error('Provide JDK via --java-home')
root=pathlib.Path(__file__).resolve().parents[2];prod=root/'app/src/main/java/local/pocketchat';work=root/'work/network-share46-host';classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
names=['J.java','NetworkShareJson.java','NetworkShareSnapshot.java','NetworkSharePreparation.java','NetworkShareSelection.java']
sources=[prod/n for n in names]+list(pathlib.Path(__file__).parent.rglob('*.java'))
if a.ui_only and not a.yaml_jar:p.error('--ui-only requires --yaml-jar')
if not a.ui_only:
    subprocess.run([javac,'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,sources)],check=True)
    r=subprocess.run([java,'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.Share46Host'],capture_output=True,text=True)
    if r.returncode:
        sys.stderr.write(r.stdout+r.stderr);r.check_returncode()
    report=json.loads(r.stdout);report['sourceSha256']={n:hashlib.sha256((prod/n).read_bytes()).hexdigest() for n in names};report['jsonJarSha256']=hashlib.sha256(a.json_jar.read_bytes()).hexdigest();out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if a.yaml_jar:
    ui=(prod/'NetworkShareUi.java').read_text()
    def member(start):
        at=ui.index(start);brace=ui.index('{',at);depth=1;i=brace+1;quote=None;escape=False;line=False;block=False
        while depth:
            c=ui[i];n=ui[i+1:i+2]
            if line:
                if c=='\n':line=False
            elif block:
                if c=='*' and n=='/':block=False;i+=1
            elif quote:
                if escape:escape=False
                elif c=='\\':escape=True
                elif c==quote:quote=None
            elif c=='/' and n=='/':line=True;i+=1
            elif c=='/' and n=='*':block=True;i+=1
            elif c in ['"',"'"]:quote=c
            elif c=='{':depth+=1
            elif c=='}':depth-=1
            i+=1
        return ui[at:i]
    needles=['static final class Prepared','static String side(','static NetworkSharePreparation.Failure problem(','static void chooseEntry(','static void prepare(Activity a,NetworkSharePreparation.Request request)','static void extract(','static boolean alive(','static void verifyPrepared(','static void failure(Activity a,ReferenceUi.Modal wait,NetworkSharePreparation.Failure f)','static void show(Activity a,Prepared p)','static void retry(','static String title(']
    fixture=work/'Share46UiHost.java';fixture.write_text((pathlib.Path(__file__).parent/'Share46UiHost.java.in').read_text().replace('@PRODUCTION_MEMBERS@','\n'.join(member(n) for n in needles)))
    # Partial-route retry buttons are meaningful only for a frozen request.
    text=fixture.read_text().replace('NetworkShareUi.side','Share46UiHost.side').replace('Prepared p=new Prepared("Route","route");','Prepared p=new Prepared("Route","route");p.frozen=new NetworkSharePreparation.Frozen(new NetworkSharePreparation.Request(ProfileCatalog.identity,"saved","route","a".repeat(32),""),"Route");')
    fixture.write_text(text)
    cp=str(a.json_jar)+':'+str(a.yaml_jar)
    subprocess.run([javac,'-encoding','UTF-8','-cp',cp,'-d',str(classes),*map(str,sources),str(prod/'NetworkShareCodec.java'),str(prod/'NetworkShareSchema.java'),str(fixture)],check=True)
    result=subprocess.run([java,'-cp',str(classes)+':'+cp,'local.pocketchat.Share46UiHost'],capture_output=True,text=True)
    if result.returncode:
        sys.stderr.write(result.stdout+result.stderr);result.check_returncode()
    ui_report=json.loads(result.stdout);ui_report['sourceSha256']=hashlib.sha256((prod/'NetworkShareUi.java').read_bytes()).hexdigest();ui_report['productionMembers']=needles;(work/'ui-results.json').write_text(json.dumps(ui_report,indent=2)+'\n');print(json.dumps(ui_report))
