#!/usr/bin/env python3
"""Rebuild or verify the source-distributed Mihomo probe and fixed-exit patch.

Normal APK builds only use --verify. Native rebuilds use the exact upstream
archive, Go 1.26.8 and NDK r29-beta1; all caches stay in the supplied workspace.
The JSON receipt binds inputs and installed bytes, not Android runtime claims.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tarfile
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'third-party/source/mihomo-v1.19.31.tar.gz'
PATCH = REPO / 'third-party/patches/mihomo-v1.19.31-probe.patch'
RECEIPT = REPO / 'third-party/patches/mihomo-v1.19.31-probe-build.json'
SOURCE_SHA = '676732158479254de38ea5a78aa32ff650ce2d3a78156a0edc2ff0cb5c2ddfd8'
UPSTREAM_REVISION = 'ab405bad5beeeac8b003bb01f60f134f6df54471'
GO_VERSION = 'go1.26.8'
GO_ARCHIVE = 'go1.26.8.linux-amd64.tar.gz'
GO_SHA = 'd0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b'
NDK_VERSION = '29.0.13113456'
NDK_ARCHIVE = 'android-ndk-r29-beta1-linux.zip'
NDK_SHA = '0bbaf4d0632152dcdcf3d0a5d385c760949898c88488375b18971dd669094388'
NDK_BYTES = 773995428
VERSION = 'v1.19.31-pocket-subscriptions1'
BUILD_TIME = 'source-2026-09-14T11:59:30Z'
FLAGS = ['-mod=readonly', '-p=4', '-tags=with_gvisor', '-trimpath', '-buildvcs=false']
LDFLAGS = ('-X github.com/metacubex/mihomo/constant.Version=' + VERSION +
           ' -X github.com/metacubex/mihomo/constant.BuildTime=' + BUILD_TIME +
           ' -w -s -buildid=')
TARGETS = {
    'android-arm64': ('arm64-v8a', 'arm64', 'aarch64-linux-android26-clang', 183),
    'android-amd64': ('x86_64', 'amd64', 'x86_64-linux-android26-clang', 62),
}
PATCH_FILES = {'adapter/adapter.go', 'adapter/urltest_probe_test.go',
               'component/urltesttrace/trace.go', 'hub/route/proxies.go',
               'adapter/outbound/socks5.go', 'adapter/outbound/socks5_preconnect.go',
               'adapter/outbound/socks5_preconnect_test.go',
               'adapter/outboundgroup/selector.go', 'adapter/outboundgroup/selector_preconnect_test.go',
               'component/proxydialer/pocket_route.go', 'component/proxydialer/pocket_route_test.go',
               'transport/socks5/socks5.go', 'transport/socks5/socks5_preconnect_test.go',
               'tunnel/tunnel.go', 'tunnel/pocket_export_test.go', 'tunnel/pocket_preconnect_test.go',
               'adapter/parser.go', 'adapter/pocket_config_fingerprint.go',
               'adapter/pocket_config_fingerprint_test.go', 'adapter/provider/provider.go',
               'adapter/provider/override.go', 'adapter/provider/pocket_selected_exit_test.go',
               'hub/route/pocket_provider_chain_test.go'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, *, cwd=None, env=None, capture=False, data=None):
    return subprocess.run(args, cwd=cwd, env=env, input=data, check=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def download(url, destination, checksum, size=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and digest(destination) == checksum:
        return
    candidate = destination.with_suffix(destination.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=60) as source, candidate.open('wb') as out:
        while data := source.read(1024 * 1024):
            out.write(data)
    if digest(candidate) != checksum or size is not None and candidate.stat().st_size != size:
        candidate.unlink()
        raise ValueError('Downloaded toolchain did not match its pinned official digest.')
    candidate.replace(destination)


def ndk_extract(archive, destination):
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    prefix = 'android-ndk-r29-beta1/toolchains/llvm/prebuilt/linux-x86_64/'
    links = []
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            if not entry.filename.startswith(prefix) and entry.filename != 'android-ndk-r29-beta1/source.properties':
                continue
            if '..' in Path(entry.filename).parts or Path(entry.filename).is_absolute():
                raise ValueError('Unsafe NDK archive path')
            path = root / entry.filename
            if stat.S_ISLNK(entry.external_attr >> 16):
                links.append((path, z.read(entry).decode('utf-8')))
                continue
            path = Path(z.extract(entry, root))
            if entry.external_attr >> 16 & 0o111:
                path.chmod(path.stat().st_mode | 0o111)
    for path, link in links:
        if not (path.parent / link).resolve().is_relative_to(root):
            raise ValueError('Unsafe NDK link target')
        if path.exists() or path.is_symlink():
            path.unlink()
        path.symlink_to(link)


def elf(path, machine):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected a 64-bit little-endian ELF')
    kind, actual_machine = struct.unpack_from('<HH', data, 16)
    if kind != 3 or actual_machine != machine:
        raise ValueError('Expected the matching Android PIE architecture')
    offset = struct.unpack_from('<Q', data, 32)[0]
    entry_size, count = struct.unpack_from('<HH', data, 54)
    interpreter = ''
    minimum_alignment = 2**63
    for index in range(count):
        pos = offset + index * entry_size
        segment_type = struct.unpack_from('<I', data, pos)[0]
        file_offset, _, _, file_size, _, alignment = struct.unpack_from('<QQQQQQ', data, pos + 8)
        if segment_type == 3:
            interpreter = data[file_offset:file_offset + file_size].rstrip(b'\0').decode('ascii')
        if segment_type == 1:
            minimum_alignment = min(minimum_alignment, alignment)
    if interpreter != '/system/bin/linker64' or minimum_alignment < 16384:
        raise ValueError('Android linker or 16 KiB page alignment is invalid')
    return {'machine': machine, 'type': 'PIE', 'interpreter': interpreter,
            'minimumLoadAlignment': minimum_alignment}


def source_inputs():
    if digest(SOURCE) != SOURCE_SHA:
        raise ValueError('The original upstream archive changed.')
    with tarfile.open(SOURCE) as archive:
        prefix = 'MetaCubeX-mihomo-ab405ba/'
        checksums = {name: hashlib.sha256(archive.extractfile(prefix + name).read()).hexdigest()
                     for name in ['go.mod', 'go.sum']}
    patch_text = PATCH.read_text('utf-8')
    touched = {line[6:] for line in patch_text.splitlines() if line.startswith('+++ b/')}
    if touched != PATCH_FILES:
        raise ValueError('Patch files differ from the reviewed probe, fixed-exit and subscription whitelist.')
    return {'upstreamVersion': 'v1.19.31', 'upstreamRevision': UPSTREAM_REVISION,
            'archive': str(SOURCE.relative_to(REPO)), 'archiveSha256': SOURCE_SHA,
            'patch': str(PATCH.relative_to(REPO)), 'patchSha256': digest(PATCH),
            'goModSha256': checksums['go.mod'], 'goSumSha256': checksums['go.sum']}


def recipe():
    return {'goVersion': GO_VERSION, 'goArchiveSha256': GO_SHA,
            'ndkVersion': NDK_VERSION, 'ndkArchiveSha256': NDK_SHA,
            'androidApi': 26, 'version': VERSION, 'buildTime': BUILD_TIME,
            'fixedExitPreconnect': True,
            'nodeFingerprint': True, 'roleSpecificExitProvider': True,
            'flags': FLAGS, 'ldflags': LDFLAGS,
            'androidExternalLdflags': '-Wl,--build-id=none,-z,max-page-size=16384',
            'cgoFlags': {'CFLAGS': '-O2 -g', 'CPPFLAGS': '', 'CXXFLAGS': '-O2 -g',
                         'FFLAGS': '-O2 -g', 'LDFLAGS': '-O2 -g'},
            'goExperiment': '',
            'goToolchainSelection': 'local', 'goModuleFlags': 'readonly',
            'goModuleVerification': 'go mod verify; original go.mod and go.sum unchanged'}


def verify():
    value = json.loads(RECEIPT.read_text('utf-8'))
    if set(value) != {'schema', 'inputs', 'recipe', 'binaries'} or value['schema'] != 1:
        raise ValueError('Unrecognized native build receipt')
    if value['inputs'] != source_inputs() or value['recipe'] != recipe():
        raise ValueError('Native source or recipe differs from the receipt.')
    if set(value['binaries']) != {spec[0] for spec in TARGETS.values()}:
        raise ValueError('Both Android ABI receipts are required.')
    for target, (abi, arch, compiler, machine) in TARGETS.items():
        item = value['binaries'][abi]
        expected_path = f'app/src/main/jniLibs/{abi}/libmihomo.so'
        if set(item) != {'path', 'sha256', 'bytes', 'goos', 'goarch', 'cgo', 'compiler', 'elf'}:
            raise ValueError('Unrecognized binary receipt fields')
        if (item['path'], item['goos'], item['goarch'], item['cgo'], item['compiler']) != (expected_path, 'android', arch, 1, compiler):
            raise ValueError('Native binary path or architecture changed.')
        binary = REPO / expected_path
        if digest(binary) != item['sha256'] or binary.stat().st_size != item['bytes'] or elf(binary, machine) != item['elf']:
            raise ValueError('Installed native binary differs from the receipt.')
    print(json.dumps({'status': 'passed', 'nativeBuildReceipt': str(RECEIPT.relative_to(REPO)),
                      'patchSha256': value['inputs']['patchSha256'],
                      'binaries': value['binaries']}, indent=2))


def build(args):
    inputs = source_inputs()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    go_archive = work / GO_ARCHIVE
    download('https://go.dev/dl/' + GO_ARCHIVE, go_archive, GO_SHA)
    go_root = work / 'toolchain'
    go = go_root / 'go/bin/go'
    if not go.is_file():
        go_root.mkdir(exist_ok=True)
        with tarfile.open(go_archive) as archive:
            archive.extractall(go_root, filter='data')
    if run([str(go), 'version'], capture=True).stdout.decode().strip() != 'go version ' + GO_VERSION + ' linux/amd64':
        raise ValueError('Unexpected Go compiler version')
    target_names = ['linux-amd64', *TARGETS] if args.target == 'all' else [args.target]
    ndk_bin = work / 'ndk/android-ndk-r29-beta1/toolchains/llvm/prebuilt/linux-x86_64/bin'
    if any(name in TARGETS for name in target_names):
        ndk_archive = work / NDK_ARCHIVE
        download('https://dl.google.com/android/repository/' + NDK_ARCHIVE,
                 ndk_archive, NDK_SHA, NDK_BYTES)
        if not (ndk_bin / 'clang').is_file():
            ndk_extract(ndk_archive, work / 'ndk')
    unpacked = work / ('source-' + inputs['patchSha256'][:16])
    if unpacked.exists():
        shutil.rmtree(unpacked)
    unpacked.mkdir()
    with tarfile.open(SOURCE) as archive:
        archive.extractall(unpacked, filter='data')
    source = unpacked / 'MetaCubeX-mihomo-ab405ba'
    run(['patch', '--batch', '--forward', '-p1'], cwd=source, data=PATCH.read_bytes())
    env = os.environ.copy()
    env.update(GOTOOLCHAIN='local', GOPATH=str(work / 'gopath'),
               GOMODCACHE=str(work / 'modules'), GOCACHE=str(work / 'cache'),
               GOTMPDIR=str(work / 'tmp'), GOFLAGS='', GOPROXY='https://proxy.golang.org,direct',
               GOOS='linux', GOARCH='amd64', GOAMD64='v1', GOARM64='v8.0',
               GOEXPERIMENT='', CGO_ENABLED='0', CGO_CFLAGS='-O2 -g',
               CGO_CPPFLAGS='', CGO_CXXFLAGS='-O2 -g', CGO_FFLAGS='-O2 -g',
               CGO_LDFLAGS='-O2 -g')
    for directory in ['gopath', 'modules', 'cache', 'tmp', 'bin']:
        (work / directory).mkdir(exist_ok=True)
    run([str(go), 'mod', 'download'], cwd=source, env=env)
    run([str(go), 'mod', 'verify'], cwd=source, env=env)
    if args.test:
        run([str(go), 'test', '-mod=readonly', '-p=4', '-tags=with_gvisor',
             './adapter', './adapter/provider', './hub/route', './component/urltesttrace', './adapter/outbound',
             './adapter/outboundgroup', './component/proxydialer', './transport/socks5', './tunnel',
             '-run=Test(Pocket|Preconnect|SelectorPreconnect)', '-count=1', '-v'], cwd=source, env=env)
    built = {}
    for name in target_names:
        if args.clean_cache_between_targets:
            # Only regenerable build cache in the explicitly supplied workspace;
            # source archives, modules, tools and build evidence remain intact.
            cache = work / 'cache'
            if cache.is_symlink():
                raise ValueError('Refusing to clear a symlinked build cache.')
            shutil.rmtree(cache)
            cache.mkdir()
        options = env.copy()
        flags = LDFLAGS
        if name in TARGETS:
            abi, arch, compiler, machine = TARGETS[name]
            options.update(GOOS='android', GOARCH=arch, CGO_ENABLED='1',
                           CC=str(ndk_bin / compiler), GOARM64='v8.0')
            flags += ' -extldflags=-Wl,--build-id=none,-z,max-page-size=16384'
        binary = work / 'bin' / ('mihomo-' + name)
        run([str(go), 'build', *FLAGS, '-ldflags=' + flags, '-o', str(binary), '.'], cwd=source, env=options)
        if name in TARGETS:
            built[abi] = {'path': f'app/src/main/jniLibs/{abi}/libmihomo.so',
                          'sha256': digest(binary), 'bytes': binary.stat().st_size,
                          'goos': 'android', 'goarch': arch, 'cgo': 1, 'compiler': compiler,
                          'elf': elf(binary, machine)}
    if digest(source / 'go.mod') != inputs['goModSha256'] or digest(source / 'go.sum') != inputs['goSumSha256']:
        raise ValueError('Building changed original module checksums.')
    if args.install:
        if set(built) != {spec[0] for spec in TARGETS.values()}:
            raise ValueError('Installing requires both Android ABIs from one build.')
        for name, (abi, _, _, _) in TARGETS.items():
            shutil.copy2(work / 'bin' / ('mihomo-' + name), REPO / built[abi]['path'])
        receipt = {'schema': 1, 'inputs': inputs, 'recipe': recipe(), 'binaries': built}
        RECEIPT.write_text(json.dumps(receipt, indent=2) + '\n', 'utf-8')
        verify()
    else:
        print(json.dumps({'status': 'built', 'version': VERSION, 'binaries': built,
                          'workspaceOutputs': str(work / 'bin')}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify', action='store_true', help='Check installed bytes and source receipt without downloads or rebuilding.')
    action.add_argument('--build', action='store_true', help='Rebuild the pinned source plus the reviewed probe and fixed-exit patch.')
    parser.add_argument('--target', choices=['all', 'linux-amd64', *TARGETS], default='all')
    parser.add_argument('--work-dir', type=Path, default=REPO / 'work/mihomo-build')
    parser.add_argument('--test', action='store_true', help='Run the actual socket/TLS/context-cancellation Go regression before building.')
    parser.add_argument('--clean-cache-between-targets', action='store_true', help='Bound workspace usage by dropping only regenerable object cache before each target.')
    parser.add_argument('--install', action='store_true', help='Install both rebuilt Android binaries and write their receipt.')
    args = parser.parse_args()
    if args.verify:
        if args.install or args.test or args.clean_cache_between_targets or args.target != 'all':
            parser.error('--verify does not accept build, test or install options')
        verify()
    else:
        build(args)


if __name__ == '__main__':
    main()
