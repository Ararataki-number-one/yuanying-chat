#!/usr/bin/env python3
"""Execute production Blob reader and its exact JavaScript in controlled runtimes."""
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
    parser.add_argument('--json-jar',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'work/browser-blob-host/result.json')
    args=parser.parse_args()
    java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
    javac=str(args.java_home/'bin/javac') if args.java_home else shutil.which('javac')
    classes=[PROD/name for name in ['BrowserBlobDownload.java','GeckoDownloadNavigation.java','BrowserAddressPolicy.java','BrowserDownloadTransfer.java','DownloadFileInfo.java','J.java']]
    extractor=ROOT/'tests/page-recovery-host/run.py'
    spec=importlib.util.spec_from_file_location('production_member',extractor);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    activity=PROD/'BrowserActivity.java';source=activity.read_text()
    sections={
      'DOCUMENT':['static final class BlobDocument'],
      'METHODS':['boolean live(','boolean fingerprintTraffic(','boolean blobDocumentCurrent(','boolean downloadBlobNavigation('],
      'CLIENT':['public boolean shouldOverrideUrlLoading(','public void onPageStarted('],
      'CHROME':['public boolean onCreateWindow('],
    }
    navigation=(HERE/'BlobNavigationHost.java.in').read_text()
    for label,needles in sections.items():navigation=navigation.replace('/* '+label+' */','\n'.join(module.member(source,needle) for needle in needles))
    listener=next(line.strip() for line in source.splitlines() if line.strip().startswith('view.setDownloadListener('))
    navigation=navigation.replace('/* LISTENER */',listener)
    files=classes+[activity,HERE/'BlobDownloadHost.java',HERE/'BlobNavigationHost.java.in',HERE/'scripts.cjs',Path(__file__).resolve(),extractor]
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    with tempfile.TemporaryDirectory(prefix='browser-blob-host-') as directory:
        root=Path(directory);scripts=root/'scripts.json'
        subprocess.run([javac,'-encoding','UTF-8','-cp',str(args.json_jar),'-d',directory,*map(str,classes),str(HERE/'BlobDownloadHost.java')],check=True,cwd=ROOT)
        host=subprocess.run([java,'-cp',directory+':'+str(args.json_jar),'local.pocketchat.BlobDownloadHost',str(scripts)],check=True,capture_output=True,text=True,timeout=30,cwd=ROOT)
        js=subprocess.run(['node',str(HERE/'scripts.cjs'),str(scripts)],check=True,capture_output=True,text=True,timeout=30,cwd=ROOT)
        navdir=root/'navigation';navdir.mkdir();fixture=navdir/'BlobNavigationHost.java';fixture.write_text(navigation)
        subprocess.run([javac,'-encoding','UTF-8','-d',str(navdir),str(fixture),str(PROD/'BrowserAddressPolicy.java'),str(PROD/'GeckoDownloadNavigation.java')],check=True,cwd=ROOT)
        nav=subprocess.run([java,'-cp',str(navdir),'local.pocketchat.BlobNavigationHost'],check=True,capture_output=True,text=True,timeout=30,cwd=ROOT)
        report={'status':'passed','java':json.loads(host.stdout),'javascript':json.loads(js.stdout),'navigation':json.loads(nav.stdout),'navigationProductionMembers':sections,'sourceSha256':hashes,'jsonJarSha256':hashlib.sha256(args.json_jar.read_bytes()).hexdigest()}
    if not all(hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in files):raise AssertionError('Blob test sources changed while executing')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
