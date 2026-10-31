"""Bounded, exact controlled-host evidence in existing CI console logs.

Only explicitly named text outputs are read. There is no directory recursion,
workspace archive, environment capture, Android execution, or phone acceptance.
The receiver must verify every manifest/chunk/end before using reconstructed bytes.
"""
import base64
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid

PREFIX = 'EXPERIENCE46_HOST_EVIDENCE '
CHUNK_CHARS = 8192
MAX_FILES = 64
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
TEXT_SUFFIXES = {'.json', '.log', '.tap', '.txt'}
INVOCATION_FILES = ('invocation.command.json', 'invocation.result.json',
                    'invocation.stdout.log', 'invocation.stderr.log')


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON evidence field')
        result[key] = value
    return result


def _integer(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def _relative(value):
    if not isinstance(value, str) or len(value) > 512 or '\\' in value or '\x00' in value:
        raise ValueError('Invalid controlled evidence path')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in ('', '.', '..') for p in path.parts):
        raise ValueError('Evidence path must be a normalized relative path')
    if path.suffix not in TEXT_SUFFIXES:
        raise ValueError('Only controlled text output extensions are allowed')
    return value


def _ordinary(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink evidence ancestry is forbidden')
    return path


def new_attempt(root, label):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', label):
        raise ValueError('Invalid controlled attempt label')
    root = _ordinary(root)
    root.mkdir(parents=True, exist_ok=True)
    attempt = root / (label + '-' + uuid.uuid4().hex)
    attempt.mkdir()
    return attempt


def run_recorded(command, attempt, *, cwd, timeout):
    """Record full subprocess bytes, including partial output on timeout/failure."""
    attempt = _ordinary(attempt)
    if not attempt.is_dir() or not all(isinstance(arg, str) for arg in command):
        raise ValueError('A controlled attempt directory and string command are required')
    (attempt / INVOCATION_FILES[0]).write_text(_json({'command': command}) + '\n')
    stdout = stderr = b''
    result = {'scope': 'Controlled host invocation only; no Android or phone execution.'}
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout)
        stdout, stderr = completed.stdout, completed.stderr
        result.update(returnCode=completed.returncode, timedOut=False)
        return completed
    except subprocess.TimeoutExpired as failure:
        stdout, stderr = failure.stdout or b'', failure.stderr or b''
        result.update(returnCode=None, timedOut=True, errorType=type(failure).__name__)
        raise
    except BaseException as failure:
        result.update(returnCode=None, timedOut=False, errorType=type(failure).__name__)
        raise
    finally:
        (attempt / INVOCATION_FILES[2]).write_bytes(stdout)
        (attempt / INVOCATION_FILES[3]).write_bytes(stderr)
        (attempt / INVOCATION_FILES[1]).write_text(_json(result) + '\n')


def emit_evidence(root, relative_files, *, label, stream=None):
    """Emit one complete archive; absent explicitly listed outputs are ignored."""
    root = _ordinary(root)
    if not root.is_dir() or not isinstance(label, str) or not 1 <= len(label) <= 160:
        raise ValueError('Invalid controlled evidence root or label')
    names = [_relative(name) for name in relative_files]
    if len(names) > MAX_FILES or len(set(names)) != len(names):
        raise ValueError('Duplicate or excessive controlled evidence paths')
    files, payloads, total = [], {}, 0
    for name in names:
        path = _ordinary(root / name)
        if not path.exists():
            continue
        if not path.is_file():
            raise ValueError('Controlled evidence must be an ordinary file')
        size = path.stat().st_size
        if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES:
            raise ValueError('Controlled evidence byte budget exceeded')
        data = path.read_bytes()
        if len(data) != size:
            raise ValueError('Controlled evidence changed while reading')
        total += len(data)
        encoded = base64.b64encode(data).decode('ascii')
        files.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'parts': max(1, math.ceil(len(encoded) / CHUNK_CHARS))})
        payloads[name] = encoded
    begin = {'kind': 'begin', 'schema': 1, 'id': uuid.uuid4().hex, 'label': label,
             'chunkChars': CHUNK_CHARS, 'totalBytes': total, 'files': files,
             'scope': 'Exact controlled host files only; not Android or phone acceptance.'}
    manifest_sha = hashlib.sha256(_json(begin).encode()).hexdigest()
    stream = sys.stdout if stream is None else stream
    def write(value):
        print(PREFIX + _json(value), file=stream, flush=True)
    write(begin)
    for info in files:
        encoded = payloads[info['path']]
        for part in range(info['parts']):
            write({'kind': 'chunk', 'id': begin['id'], 'path': info['path'], 'part': part,
                   'parts': info['parts'], 'data': encoded[part * CHUNK_CHARS:(part + 1) * CHUNK_CHARS]})
    write({'kind': 'end', 'id': begin['id'], 'fileCount': len(files),
           'totalBytes': total, 'manifestSha256': manifest_sha})
    return begin


def reassemble(lines):
    """Verify console archives and return exact bytes; reject incomplete/counterfeit sets."""
    active, closed, archives, aggregate_bytes = {}, set(), [], 0
    for line in lines:
        if PREFIX not in line:
            continue
        raw = line.split(PREFIX, 1)[1].strip()
        if len(raw) > 65536:
            raise ValueError('Evidence event exceeds console budget')
        event = json.loads(raw, object_pairs_hook=_unique_pairs)
        if not isinstance(event, dict):
            raise ValueError('Evidence event must be an object')
        identity = event.get('id')
        if not isinstance(identity, str) or not re.fullmatch('[0-9a-f]{32}', identity) or identity in closed:
            raise ValueError('Invalid or closed evidence identity')
        kind = event.get('kind')
        if kind == 'begin':
            if set(event) != {'kind','schema','id','label','chunkChars','totalBytes','files','scope'}:
                raise ValueError('Unexpected evidence manifest fields')
            if identity in active or type(event.get('schema')) is not int or event['schema'] != 1 or type(event.get('chunkChars')) is not int or event['chunkChars'] != CHUNK_CHARS:
                raise ValueError('Duplicate or unsupported evidence manifest')
            if not isinstance(event.get('label'), str) or not 1 <= len(event['label']) <= 160 or not isinstance(event.get('scope'), str) or len(event['scope']) > 512:
                raise ValueError('Invalid controlled evidence label or scope')
            files = event.get('files')
            if not isinstance(files, list) or len(files) > MAX_FILES:
                raise ValueError('Evidence file budget exceeded')
            if not _integer(event.get('totalBytes'), MAX_TOTAL_BYTES):
                raise ValueError('Evidence total byte budget exceeded')
            known, total = {}, 0
            for info in files:
                if not isinstance(info, dict) or set(info) != {'path','bytes','sha256','parts'}:
                    raise ValueError('Unexpected evidence file fields')
                name = _relative(info['path'])
                size, parts = info.get('bytes'), info.get('parts')
                if name in known or not _integer(size, MAX_FILE_BYTES):
                    raise ValueError('Duplicate path or invalid file size')
                if type(parts) is not int or parts != max(1, math.ceil((4 * math.ceil(size / 3)) / CHUNK_CHARS)):
                    raise ValueError('Invalid chunk count')
                if not isinstance(info.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', info['sha256']):
                    raise ValueError('Invalid file digest')
                total += size
                known[name] = (info, {})
            if total != event['totalBytes']:
                raise ValueError('Manifest total does not match files')
            aggregate_bytes += total
            if len(active) + len(closed) >= 128 or aggregate_bytes > 128 * 1024 * 1024:
                raise ValueError('Console evidence aggregate budget exceeded')
            active[identity] = (event, known)
        elif kind == 'chunk':
            if set(event) != {'kind','id','path','part','parts','data'}:
                raise ValueError('Unexpected evidence chunk fields')
            if identity not in active:
                raise ValueError('Chunk has no manifest')
            known = active[identity][1]
            if event.get('path') not in known:
                raise ValueError('Chunk path was not declared')
            info, chunks = known[event['path']]
            part, data = event.get('part'), event.get('data')
            if type(part) is not int or not 0 <= part < info['parts'] or part in chunks or type(event.get('parts')) is not int or event['parts'] != info['parts']:
                raise ValueError('Duplicate, out-of-range, or inconsistent chunk')
            if not isinstance(data, str) or len(data) > CHUNK_CHARS or (part < info['parts'] - 1 and len(data) != CHUNK_CHARS):
                raise ValueError('Invalid chunk length')
            base64.b64decode(data, validate=True)
            chunks[part] = data
        elif kind == 'end':
            if set(event) != {'kind','id','fileCount','totalBytes','manifestSha256'} or type(event.get('fileCount')) is not int or type(event.get('totalBytes')) is not int:
                raise ValueError('Unexpected evidence final fields')
            if identity not in active:
                raise ValueError('End has no manifest')
            begin, known = active.pop(identity)
            if event.get('fileCount') != len(known) or event.get('totalBytes') != begin['totalBytes'] or event.get('manifestSha256') != hashlib.sha256(_json(begin).encode()).hexdigest():
                raise ValueError('Evidence final manifest mismatch')
            restored = {}
            for name, (info, chunks) in known.items():
                if len(chunks) != info['parts']:
                    raise ValueError('Missing evidence chunk')
                data = base64.b64decode(''.join(chunks[n] for n in range(info['parts'])), validate=True)
                if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
                    raise ValueError('Evidence bytes or digest mismatch')
                restored[name] = data
            archives.append({'id': identity, 'label': begin['label'], 'files': restored})
            closed.add(identity)
        else:
            raise ValueError('Unknown evidence event')
    if active:
        raise ValueError('Incomplete controlled evidence archive')
    return archives
