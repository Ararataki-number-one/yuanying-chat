"""Copy exact verified combo bytes; no source-only checker can be replaced."""
import os
from pathlib import Path
from gecko.sdk_identity_contract import source_bytes
from browser.check_gecko_cpu_ip_combo_evidence import (REPORT_NAME,RAW_DIRECTORY,RAW_FILES,
    read_json,verify_gecko_cpu_ip_combo_evidence)

SUMMARY=REPORT_NAME
MAX_SUMMARY_BYTES=2*1024*1024
MAX_RAW_BYTES=262144
MAX_DEVICE_BYTES=524288
COMBO_RELEASE_TOOLS=('tools/browser/cpu_ip_combo_publication.py',)
COMBO_SOURCE_ONLY_TOOLS=(
 'tools/browser/check_gecko_cpu_ip_combo_evidence.py','tools/browser/run_gecko_cpu_ip_combo_integration.py',
 'tools/browser/check_gecko_ip_timezone_evidence.py','tools/browser/ip_timezone_fixture_server.py',
 'tools/browser/fingerprint_fixture_server.py','tools/browser/newworker_fixture_server.py',
 'tools/gecko/profile_invocation_contract.py','tools/gecko/sdk_identity_contract.py')


def require(value,message):
    if not value:raise ValueError('CPU/IP combo publication: '+message)
def capture(directory):
    directory=Path(directory);raw=directory/RAW_DIRECTORY
    require(directory.is_dir() and not any(p.is_symlink() for p in (directory,*directory.parents)) and raw.is_dir() and not raw.is_symlink(),'ordinary evidence roots required')
    require({p.name for p in raw.iterdir()}==set(RAW_FILES),'exact four combo raw JSONs required')
    values={SUMMARY:read_json(directory/SUMMARY,MAX_SUMMARY_BYTES)[0]}
    values.update({RAW_DIRECTORY+'/'+name:read_json(raw/name,MAX_DEVICE_BYTES if name=='combo.json' else MAX_RAW_BYTES)[0] for name in RAW_FILES});return values

def copy_gecko_cpu_ip_combo_evidence(directory,destination,source,expected,reader=source_bytes):
    captured=capture(directory);verify_gecko_cpu_ip_combo_evidence(directory,source,expected,reader=reader)
    require(capture(directory)==captured,'combo inputs changed during actual checker')
    destination=Path(destination);require(destination.is_dir() and not any(p.is_symlink() for p in (destination,*destination.parents)),'ordinary destination root required')
    require(not (destination/SUMMARY).exists() and not (destination/SUMMARY).is_symlink() and not (destination/RAW_DIRECTORY).exists() and not (destination/RAW_DIRECTORY).is_symlink(),'fresh summary/raw destinations required')
    root=os.open(destination,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);child=None
    try:
        os.mkdir(RAW_DIRECTORY,dir_fd=root);child=os.open(RAW_DIRECTORY,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
        for name,data in captured.items():
            parent=root if name==SUMMARY else child
            with os.fdopen(os.open(Path(name).name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=parent),'wb') as stream:stream.write(data)
    finally:
        if child is not None:os.close(child)
        os.close(root)
    require(capture(destination)==captured,'copied original combo bytes differ');return list(captured)

def copy_gecko_cpu_ip_combo_tools(root,destination,source,reader=source_bytes):
    root,destination=Path(root),Path(destination);values={}
    for relative in COMBO_RELEASE_TOOLS+COMBO_SOURCE_ONLY_TOOLS:
        data=read_json_source(root/relative)
        if relative in COMBO_SOURCE_ONLY_TOOLS:require(data==reader(source,relative),'combo source-only dependency differs: '+relative)
        values[relative]=data
    # Resolve fixed subdirectories under retained directory descriptors. A
    # preexisting parent symlink is rejected before mkdir can affect its target.
    require(destination.is_dir() and not any(p.is_symlink() for p in (destination,*destination.parents)),'ordinary code destination required')
    root_fd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for relative,data in values.items():
            parts=Path(relative).parts;descriptor=os.dup(root_fd)
            try:
                for part in parts[:-1]:
                    try:os.mkdir(part,dir_fd=descriptor)
                    except FileExistsError:pass
                    child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor);os.close(descriptor);descriptor=child
                try:fd=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=descriptor)
                except FileExistsError:
                    with os.fdopen(os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=descriptor),'rb') as stream:
                        import stat
                        info=os.fstat(stream.fileno());require(stat.S_ISREG(info.st_mode) and info.st_size==len(data),'staged code type/size differs');require(stream.read(len(data)+1)==data,'staged code differs')
                else:
                    with os.fdopen(fd,'wb') as stream:stream.write(data)
            finally:os.close(descriptor)
    finally:os.close(root_fd)
    for relative,data in values.items():require(read_json_source(destination/relative)==data,'staged combo code changed: '+relative)
    return list(values)
def read_json_source(path):
    import stat
    path=Path(path);require(not any(p.is_symlink() for p in (path,*path.parents)),'ordinary code source required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        info=os.fstat(stream.fileno());require(stat.S_ISREG(info.st_mode) and 0<info.st_size<=2*1024*1024,'bounded code source required');data=stream.read(2*1024*1024+1)
        require(len(data)==info.st_size,'code source changed while reading')
    data.decode('utf-8','strict');require(b'\0' not in data,'binary source refused');return data
