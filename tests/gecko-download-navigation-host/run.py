#!/usr/bin/env python3
"""Exercise the actual Blob admission method at explicit JVM native boundaries."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/gecko-download-navigation/result.json')
    args=parser.parse_args()
    javac=str(args.java_home/'bin/javac') if args.java_home else shutil.which('javac')
    java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
    scanner_path=ROOT/'tests/gecko-navigation-host/run.py'
    spec=importlib.util.spec_from_file_location('navigation_scanner',scanner_path)
    scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
    files=[PROD/'GeckoWebView.java',PROD/'GeckoDownloadNavigation.java',PROD/'BrowserAddressPolicy.java',HERE/'DownloadNavigationHost.java.in',Path(__file__).resolve(),scanner_path]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    source=files[0].read_text()
    method=scanner.member_at(source,source.index('boolean downloadBlobPopup('))
    generated=files[3].read_text().replace('@PRODUCTION_METHOD@',method)
    # The actual popup branch must reach this method before rejecting non-HTTP
    # windows; otherwise a correct helper would never fix the original bug.
    popup=scanner.member_at(source,source.index('@Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target)'))
    if popup.index('downloadBlobPopup(s,target)')>popup.index('popups.size()>=8'):
        raise AssertionError('Blob downloads must not consume or depend on a popup slot')
    if 'if(!owner.timeZone.popupAllowed())' not in popup:
        raise AssertionError('Existing general-popup timezone boundary is required')
    with tempfile.TemporaryDirectory(prefix='gecko-download-navigation-') as directory:
        root=Path(directory);host=root/'DownloadNavigationHost.java';host.write_text(generated)
        subprocess.run([javac,'-encoding','UTF-8','-d',directory,str(host),str(files[1]),str(files[2])],check=True,cwd=ROOT)
        result=subprocess.run([java,'-cp',directory,'local.pocketchat.DownloadNavigationHost'],capture_output=True,text=True,check=True,timeout=30,cwd=ROOT)
        report=json.loads(result.stdout)
    if not all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p.relative_to(ROOT))] for p in files):
        raise AssertionError('Source changed while running download admission checks')
    report.update(sourceSha256=hashes,scope='Actual GeckoDownloadNavigation and exact GeckoWebView.downloadBlobPopup method with controlled native-session, lifecycle, bridge and network-admission boundaries. No Android, Gecko engine, real website, Blob fetch, or user-file execution.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    main()
