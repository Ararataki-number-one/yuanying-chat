"""Copy source-verified original Gecko-web TLS JSON, without a public alias."""
import os
import stat
from pathlib import Path
from gecko.sdk_identity_contract import source_bytes
from browser.check_gecko_tls_evidence import verify_gecko_tls_evidence,CASE_FILES
SUMMARY='gecko-tls-results.json'
RAW_DIRECTORY='gecko-tls-evidence'
RAW_FILES=tuple(CASE_FILES)
MAX_SUMMARY_BYTES=4194304
MAX_RAW_BYTES=262144
TLS_RELEASE_TOOLS=('tools/browser/tls_publication.py',)
TLS_SOURCE_ONLY_TOOLS=('tools/browser/check_gecko_tls_evidence.py','tools/browser/run_gecko_tls_integration.py',
 'tools/gecko/run_gecko_tls_acceptance.py','tools/gecko/tls_acceptance_contract.py','tools/gecko/tls_acceptance_server.py',
 'tools/browser/native_tls_probe_server.py','tools/browser/fingerprint_fixture_server.py',
 'tools/gecko/profile_invocation_contract.py','tools/gecko/sdk_identity_contract.py','tools/gecko/tls_fixture_scope_contract.py','tools/gecko/tls_cpu_ip_combo_contract.py','tools/gecko/tls_cpu_ip_combo_server.py','tools/gecko/run_gecko_tls_cpu_ip_combo.py','tools/browser/ip_timezone_fixture_server.py','tools/browser/newworker_fixture_server.py','tools/browser/check_gecko_ip_timezone_evidence.py','tools/browser/check_gecko_cpu_ip_combo_evidence.py','tools/gecko/check_gecko_tls_package.py','tools/gecko/check_native_tls_package.py')

def require(value,message):
    if not value:raise ValueError('TLS publication: '+message)
def read_regular(path,limit):
    path=Path(path);require(not any(p.is_symlink() for p in (path,*path.parents)),'ordinary source path required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=limit,'bounded regular input required');data=stream.read(limit+1);after=os.fstat(stream.fileno());named=os.stat(path,follow_symlinks=False)
    stamp=lambda value:(value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns)
    require(len(data)==before.st_size and stamp(before)==stamp(after)==stamp(named),'input changed while reading');return data

def capture(directory):
    import json
    directory=Path(directory);raw=directory/RAW_DIRECTORY
    require(directory.is_dir() and raw.is_dir() and not any(p.is_symlink() for p in (raw,*raw.parents)),'ordinary evidence directories required')
    names={p.name for p in raw.iterdir()};require(names in (set(RAW_FILES),set(RAW_FILES)|{'results.json'}),'exact twelve original TLS case files required')
    summary=read_regular(directory/SUMMARY,MAX_SUMMARY_BYTES)
    if 'results.json' in names:require(read_regular(raw/'results.json',MAX_SUMMARY_BYTES)==summary,'raw TLS summary alias differs')
    values={SUMMARY:summary};values.update({RAW_DIRECTORY+'/'+name:read_regular(raw/name,MAX_RAW_BYTES) for name in RAW_FILES});return values

def copy_gecko_tls_evidence(directory,destination,source,expected,reader=source_bytes):
    captured=capture(directory);verify_gecko_tls_evidence(directory,source,expected,reader=reader);require(capture(directory)==captured,'original evidence changed during source checker')
    destination=Path(destination);require(destination.is_dir() and not any(p.is_symlink() for p in (destination,*destination.parents)),'ordinary stage required')
    require(not (destination/SUMMARY).exists() and not (destination/SUMMARY).is_symlink() and not (destination/RAW_DIRECTORY).exists() and not (destination/RAW_DIRECTORY).is_symlink(),'fresh TLS stage paths required')
    parent=os.open(destination,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);child=None
    try:
        os.mkdir(RAW_DIRECTORY,dir_fd=parent);child=os.open(RAW_DIRECTORY,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        for relative,data in captured.items():
            with os.fdopen(os.open(Path(relative).name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=parent if relative==SUMMARY else child),'wb') as stream:stream.write(data)
    finally:
        if child is not None:os.close(child)
        os.close(parent)
    require(capture(destination)==captured and not (destination/RAW_DIRECTORY/'results.json').exists(),'strict public TLS bytes or no-alias rule changed');return list(captured)

def copy_gecko_tls_tools(root,destination,source,reader=source_bytes):
    root,destination=Path(root),Path(destination);values={}
    for name in TLS_RELEASE_TOOLS+TLS_SOURCE_ONLY_TOOLS:
        raw=read_regular(root/name,2*1024*1024);raw.decode('utf-8','strict');require(b'\0' not in raw,'regular Python code required')
        if name in TLS_SOURCE_ONLY_TOOLS:require(raw==reader(source,name),'TLS source-only input differs: '+name)
        values[name]=raw
    require(destination.is_dir() and not any(p.is_symlink() for p in (destination,*destination.parents)),'ordinary code destination required')
    parent=os.open(destination,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for name,data in values.items():
            parts=Path(name).parts;fd=os.dup(parent)
            try:
                for part in parts[:-1]:
                    try:os.mkdir(part,dir_fd=fd)
                    except FileExistsError:pass
                    child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
                try:target=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=fd)
                except FileExistsError:
                    with os.fdopen(os.open(parts[-1],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=fd),'rb') as stream:
                        info=os.fstat(stream.fileno());require(stat.S_ISREG(info.st_mode) and info.st_size==len(data) and stream.read(len(data)+1)==data,'preexisting staged TLS code differs')
                else:
                    with os.fdopen(target,'wb') as stream:stream.write(data)
            finally:os.close(fd)
    finally:os.close(parent)
    require(all(read_regular(destination/name,2*1024*1024)==data for name,data in values.items()),'staged TLS code changed');return list(values)
