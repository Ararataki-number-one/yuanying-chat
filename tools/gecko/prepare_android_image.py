#!/usr/bin/env python3
"""Provision the pinned official emulator and Google API 35 r09 from verified complete archives.

Only download/setup can retry. This never boots Android or runs an app workload.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PIN=Path(__file__).with_name('android-system-image.json')
PACKAGE=Path(__file__).with_name('android-35-google-apis-x86_64-package.xml')
EMULATOR_PIN=Path(__file__).with_name('android-emulator.json')
EMULATOR_PACKAGE=Path(__file__).with_name('android-emulator-package.xml')

def digest(path, algorithm):
    h=hashlib.new(algorithm)
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def verified(path, pin):
    return (path.is_file() and path.stat().st_size==pin['bytes'] and digest(path,'sha1')==pin['sha1']
            and (not pin.get('sha256') or digest(path,'sha256')==pin['sha256']))

def download(pin, path, attempts=3):
    if verified(path,pin):return 0
    partial=path.with_suffix('.partial')
    for attempt in range(1,attempts+1):
        try:
            request=urllib.request.Request(pin['url'],headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'})
            count=0
            with urllib.request.urlopen(request,timeout=60) as response,partial.open('wb') as output:
                declared=response.headers.get('Content-Length')
                if declared is not None and int(declared)!=pin['bytes']:raise ValueError('Incomplete image response length')
                while True:
                    data=response.read(1024*1024)
                    if not data:break
                    count+=len(data)
                    if count>pin['bytes']:raise ValueError('Image exceeds official archive size')
                    output.write(data)
            if not verified(partial,pin):raise ValueError('Image size or official checksum differs')
            with zipfile.ZipFile(partial) as archive:
                if not archive.infolist():raise ValueError('Empty image archive')
            partial.replace(path);return attempt
        except (OSError,ValueError,zipfile.BadZipFile) as error:
            partial.unlink(missing_ok=True)
            print(json.dumps({'setupDownloadAttempt':attempt,'status':'failed','reason':str(error)}),flush=True)
            if isinstance(error,urllib.error.HTTPError) and error.code in (401,403,404):raise
            if attempt==attempts:raise

def extract(archive, staging, root):
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            path=PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!=root or stat.S_ISLNK(info.external_attr>>16):
                raise ValueError('Unexpected path in Android package archive')
            destination=staging.joinpath(*path.parts)
            if info.is_dir():destination.mkdir(parents=True,exist_ok=True);continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            # CRC is verified on the complete read, before the staged package
            # can become an installation. Keep the emulator's executable bits.
            with source.open(info) as inp,destination.open('wb') as out:shutil.copyfileobj(inp,out)
            mode=(info.external_attr>>16)&0o777
            if mode:destination.chmod(mode)
    return staging/root

def install(archive, target, package_xml, revision):
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-image-',dir=target.parent) as stage:
        image=extract(archive,Path(stage),'x86_64')
        props=dict(line.split('=',1) for line in (image/'source.properties').read_text().splitlines() if '=' in line)
        if props.get('Pkg.Revision')!=str(revision) or props.get('AndroidVersion.ApiLevel')!='35' or props.get('SystemImage.TagId')!='google_apis' or props.get('SystemImage.Abi')!='x86_64':
            raise ValueError('Extracted image differs from the pinned Google API 35 x86_64 revision')
        # r09 legitimately has no populated userdata.img; the unchanged
        # avdmanager/emulator command creates each fresh AVD's user data.
        for name in ('system.img','ramdisk.img','kernel-ranchu'):
            if not (image/name).is_file() or (image/name).stat().st_size==0:raise ValueError('Incomplete image: '+name)
        (image/'package.xml').write_bytes(package_xml.read_bytes())
        if target.exists():raise FileExistsError('System image target must be provisioned in a clean SDK: '+str(target))
        image.rename(target)
    return props

def install_emulator(archive, target, package_xml, revision):
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-emulator-',dir=target.parent) as stage:
        emulator=extract(archive,Path(stage),'emulator')
        props=dict(line.split('=',1) for line in (emulator/'source.properties').read_text().splitlines() if '=' in line)
        if props.get('Pkg.Revision')!=revision or props.get('Pkg.Desc')!='Android Emulator':raise ValueError('Emulator differs from pinned stable SDK package')
        for name in ('emulator','qemu/linux-x86_64/qemu-system-x86_64'):
            path=emulator/name
            if not path.is_file() or path.stat().st_size==0 or not path.stat().st_mode&stat.S_IXUSR:raise ValueError('Incomplete executable emulator package: '+name)
        (emulator/'package.xml').write_bytes(package_xml.read_bytes())
        # A hosted runner may already contain an older SDK emulator. Updating
        # this tool directory does not touch the separately configured AVDs.
        backup=Path(stage)/'previous'
        if target.exists():
            previous=target/'source.properties'
            if not previous.is_file() or 'Pkg.Desc=Android Emulator' not in previous.read_text():raise ValueError('Refusing to replace a non-SDK emulator directory')
            target.rename(backup)
        try:emulator.rename(target)
        except BaseException:
            if backup.exists():backup.rename(target)
            raise
    return props

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sdk-root',required=True,type=Path);p.add_argument('--cache',required=True,type=Path);p.add_argument('--report',required=True,type=Path);p.add_argument('--component',choices=('image','emulator'),default='image');a=p.parse_args()
    is_image=a.component=='image';pin=json.loads((PIN if is_image else EMULATOR_PIN).read_text());package=PACKAGE if is_image else EMULATOR_PACKAGE;a.cache.mkdir(parents=True,exist_ok=True)
    archive=a.cache/(a.component+'-verified.zip');attempts=download(pin,archive)
    target=a.sdk_root/('system-images/android-35/google_apis/x86_64' if is_image else 'emulator')
    props=(install if is_image else install_emulator)(archive,target,package,pin['revision'])
    report=dict(status='passed',downloadAttempts=attempts,setupOnly=True,actualAndroidExecution=False,workloadExecuted=False,package=pin['package'],revision=pin['revision'],url=pin['url'],bytes=archive.stat().st_size,sha1=digest(archive,'sha1'),sha256=digest(archive,'sha256'),packageXmlSha256=digest(package,'sha256'),properties=props)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n');archive.unlink()
    print(json.dumps({k:report[k] for k in ('status','setupOnly','revision','bytes','sha1','sha256')}),flush=True)

if __name__=='__main__':main()
