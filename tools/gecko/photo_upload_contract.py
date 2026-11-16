"""Independent, bounded PNG and HTTP receipts for actual Android photo uploads.

The browser never decides whether its pixels survived. The controlled receiver
decodes the uploaded PNG, and publication decodes the retained bytes again.
"""
import binascii
import hashlib
import json
from pathlib import Path
import re
import struct
import threading
import zlib
from email import policy
from email.parser import BytesParser

WIDTH, HEIGHT = 64, 48
MAX_PNG_BYTES = 131072
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
FIXTURE_SHA256 = 'aed9e99b30d0403a527e20c5d91e0042cd1956405226bf5ecd60254ec6b0b0a5'
ENCODINGS = ('original', 'to-blob', 'to-data-url')
UNSELECTED = ('unselected-to-blob', 'unselected-to-data-url')
CASES = (
    ('standard-external', 0, 1, 'select', 'desktopImage'),
    ('standard-own', 0, 1, 'select', 'desktopOwnImage'),
    ('unselected-protected', 0, 2, 'probe', 'photoProtectionProbe'),
    ('protected-external', 0, 2, 'select', 'desktopImage'),
    ('other-environment', 1, 2, 'probe', 'photoProtectionProbe'),
    ('after-navigation', 0, 2, 'probe', 'photoProtectionProbe'),
    ('protected-own', 0, 2, 'select', 'desktopOwnImage'),
    ('after-own-navigation', 0, 2, 'probe', 'photoProtectionProbe'),
)


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def expected_rgba():
    pixels = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            # One transparent black pixel exercises alpha without lossy
            # premultiplication of partially transparent source channels.
            pixels.extend((0, 0, 0, 0) if x == y == 0 else
                          ((37*x+11*y) % 256, (17*x+43*y) % 256,
                           (5*x+71*y) % 256, 255))
    return bytes(pixels)


def _paeth(a, b, c):
    p = a+b-c
    distances = (abs(p-a), abs(p-b), abs(p-c))
    return (a, b, c)[distances.index(min(distances))]


def decode_png(raw):
    """Decode complete 8-bit RGB/RGBA PNGs without browser or Pillow helpers."""
    require(type(raw) is bytes and len(PNG_SIGNATURE) < len(raw) <= MAX_PNG_BYTES,
            'PNG byte count is outside the controlled image bound')
    require(raw.startswith(PNG_SIGNATURE), 'Uploaded image is not a PNG')
    at, chunks, compressed, header, ended = len(PNG_SIGNATURE), [], bytearray(), None, False
    while at < len(raw):
        require(at+12 <= len(raw), 'Truncated PNG chunk')
        size = struct.unpack('>I', raw[at:at+4])[0]
        kind = raw[at+4:at+8]
        require(size <= MAX_PNG_BYTES and at+12+size <= len(raw), 'Invalid PNG chunk length')
        data = raw[at+8:at+8+size]
        crc = struct.unpack('>I', raw[at+8+size:at+12+size])[0]
        require(binascii.crc32(kind+data) & 0xffffffff == crc, 'PNG chunk CRC differs')
        require(re.fullmatch(b'[A-Za-z]{4}', kind) is not None, 'Invalid PNG chunk type')
        if not chunks:
            require(kind == b'IHDR' and size == 13, 'PNG must start with one IHDR')
            header = struct.unpack('>IIBBBBB', data)
            width, height, depth, color, compression, filtering, interlace = header
            require((width, height) == (WIDTH, HEIGHT), 'Uploaded PNG dimensions changed')
            require(depth == 8 and color in (2, 6) and (compression, filtering, interlace) == (0, 0, 0),
                    'Unsupported controlled PNG encoding')
        elif kind == b'IHDR':
            raise AssertionError('Duplicate PNG IHDR')
        elif kind == b'IDAT':
            require(not ended and (not compressed or chunks[-1] == b'IDAT'), 'PNG IDAT chunks must be contiguous')
            compressed.extend(data)
        elif kind == b'IEND':
            require(size == 0 and compressed and at+12 == len(raw), 'Incomplete PNG or trailing data')
            ended = True
        elif kind[0] & 32 == 0:
            # PLTE may accompany a truecolor image but cannot affect its RGB.
            require(kind == b'PLTE' and not compressed and 0 < size <= 768 and size % 3 == 0,
                    'Unknown or misplaced critical PNG chunk')
        else:
            require(kind != b'tRNS', 'Controlled transparent images must carry explicit RGBA')
        chunks.append(kind)
        at += size+12
    require(ended and chunks[-1] == b'IEND', 'PNG IEND is missing')
    channels = 4 if header[3] == 6 else 3
    stride = WIDTH*channels
    expected_size = HEIGHT*(stride+1)
    inflater = zlib.decompressobj()
    try:
        inflated = inflater.decompress(bytes(compressed), expected_size+1)
    except zlib.error as error:
        raise AssertionError('Invalid PNG zlib stream') from error
    require(len(inflated) == expected_size and inflater.eof and not inflater.unconsumed_tail
            and not inflater.unused_data, 'PNG decompressed bytes differ from the exact dimensions')
    previous = bytearray(stride)
    rgba = bytearray()
    for y in range(HEIGHT):
        kind = inflated[y*(stride+1)]
        require(kind in range(5), 'Unknown PNG filter')
        row = bytearray(inflated[y*(stride+1)+1:(y+1)*(stride+1)])
        for i in range(stride):
            left = row[i-channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i-channels] if i >= channels else 0
            add = (0, left, up, (left+up)//2, _paeth(left, up, upper_left))[kind]
            row[i] = (row[i]+add) & 255
        if channels == 4:
            rgba.extend(row)
        else:
            for i in range(0, stride, 3):
                rgba.extend(row[i:i+3]); rgba.append(255)
        previous = row
    return bytes(rgba)


def inspect_png(raw, *, expected_match, original=False):
    require(type(expected_match) is bool and type(original) is bool, 'Explicit image expectations required')
    pixels = decode_png(raw)
    expected = expected_rgba()
    matched = pixels == expected
    require(matched is expected_match, 'Full uploaded RGBA pixels do not match the required selection/privacy state')
    if original:
        require(digest(raw) == FIXTURE_SHA256, 'Selected original file bytes changed')
    colors = len({pixels[i:i+4] for i in range(0, len(pixels), 4)})
    return dict(bytes=len(raw), sha256=digest(raw), width=WIDTH, height=HEIGHT,
                rgbaSha256=digest(pixels), expectedRgbaSha256=digest(expected),
                pixelCount=WIDTH*HEIGHT, distinctRgbaColors=colors,
                exactPixels=matched, originalBytesVerified=original)


def multipart_image(content_type, body):
    require(type(content_type) is str and '\r' not in content_type and '\n' not in content_type
            and len(content_type) <= 200, 'Invalid multipart content type')
    require(type(body) is bytes and 0 < len(body) <= MAX_PNG_BYTES+4096, 'Invalid multipart byte count')
    message = BytesParser(policy=policy.default).parsebytes(
        b'MIME-Version: 1.0\r\nContent-Type: '+content_type.encode('ascii')+b'\r\n\r\n'+body)
    require(message.get_content_type() == 'multipart/form-data' and not message.defects,
            'Expected one well-formed multipart form')
    parts = list(message.iter_parts())
    require(len(parts) == 1, 'Photo upload must contain exactly one part')
    part = parts[0]
    require(not part.defects and part.get_content_disposition() == 'form-data'
            and part.get_param('name', header='Content-Disposition') == 'file'
            and part.get_filename() == 'photo-123.png' and part.get_content_type() == 'image/png'
            and not part.is_multipart(), 'Photo part identity or MIME differs')
    raw = part.get_payload(decode=True)
    require(type(raw) is bytes and len(raw) <= MAX_PNG_BYTES, 'Invalid photo body')
    return raw


def phases(mode):
    require(mode in ('select', 'probe'), 'Unknown photo invocation mode')
    return UNSELECTED+(ENCODINGS if mode == 'select' else ())


def verify_native_events(identity, owner, native, records):
    if __package__:
        from .integration_event_contract import EventTransfer, event_uri
    else:
        from integration_event_contract import EventTransfer, event_uri
    require(type(records) is list and 1 <= len(records) <= 64,
            'Original native photo event payloads are required')
    payloads = {}
    for row in records:
        require(type(row) is dict and set(row) == {'receipt', 'rawUtf8'} and type(row['rawUtf8']) is str,
                'Complete raw native photo event records are required')
        uri = event_uri(row['receipt'])
        require(uri not in payloads, 'Duplicate native photo event receipt')
        payloads[uri] = row['rawUtf8'].encode('utf-8')
    reader = EventTransfer(identity=identity, nonce=owner['runNonce'], slot=owner['processSlot'],
                           action=owner['fixtureAction'], command=owner['command'], fetch=lambda uri: payloads[uri])
    events = [reader.read(row['receipt']) for row in records]
    kind = 'desktopImage' if owner['mode'] == 'select' else 'photoProtectionProbe'
    complete = [event for event in events if event['kind'] == kind]
    require(len(complete) == 1 and events[-1] == complete[0] and complete[0]['result'] == native,
            'Photo receipt must join the exact terminal native result')
    require(all(event['kind'] != 'error' for event in events), 'Native photo invocation contains a failure')


class PhotoUploadLedger:
    """Only runner-registered invocations may create owned receiver evidence."""
    def __init__(self, directory, identity):
        self.directory = Path(directory)
        self.identity = dict(identity)
        self.lock = threading.Lock()
        self.cases = {}

    def register(self, name, nonce, slot, level, mode, action):
        require((name, slot, level, mode, action) in CASES, 'Unknown predeclared photo case')
        require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce), 'Photo invocation requires a nonce')
        with self.lock:
            require(nonce not in self.cases and name not in {c['name'] for c in self.cases.values()},
                    'Duplicate photo invocation')
            self.cases[nonce] = dict(name=name, runNonce=nonce, processSlot=slot, privacyLevel=level,
                                     mode=mode, fixtureAction=action, command=None, receipts=[], errors=[])

    def document(self, nonce, command, level, mode):
        with self.lock:
            owner = self.cases.get(nonce)
            require(owner is not None and owner['privacyLevel'] == level and owner['mode'] == mode,
                    'Photo page belongs to no registered invocation')
            require(type(command) is int and 0 < command < 2**63, 'Invalid native photo command')
            require(owner['command'] in (None, command), 'Photo document changed native command')
            require(owner['command'] is None, 'Photo fixture must load exactly one document per invocation')
            owner['command'] = command
            return dict(owner)

    def receive(self, nonce, command, phase, content_type, body):
        with self.lock:
            owner = self.cases.get(nonce)
            require(owner is not None and owner['command'] is not None and owner['command'] == command,
                    'Photo upload is stale or belongs to another invocation')
            sequence = phases(owner['mode'])
            raw, filename, stored = None, None, False
            try:
                require(len(owner['receipts']) < len(sequence) and sequence[len(owner['receipts'])] == phase,
                        'Missing, duplicated, or out-of-order photo encoding')
                raw = multipart_image(content_type, body)
                expected_match = phase not in UNSELECTED or owner['privacyLevel'] < 2
                filename = 'photo-upload-'+nonce+'-'+phase+'.png'
                self.directory.mkdir(parents=True, exist_ok=True)
                path = self.directory/filename
                require(not path.exists() and not path.is_symlink(), 'Photo evidence file already exists')
                path.write_bytes(raw)
                stored = True
                # Preserve the actual bad image as a diagnostic if decoding or
                # pixel comparison fails. It never becomes a passed receipt.
                observed = inspect_png(raw, expected_match=expected_match, original=phase == 'original')
                receipt = dict(schema=1, runNonce=nonce, command=command, processSlot=owner['processSlot'],
                               fixtureAction=owner['fixtureAction'], phase=phase, file=filename,
                               expectedMatch=expected_match, **observed)
                owner['receipts'].append(receipt)
                return dict(receipt)
            except Exception as error:
                failure = dict(phase=phase, error=type(error).__name__+': '+str(error))
                if stored:
                    failure.update(file=filename, bytes=len(raw), sha256=digest(raw))
                owner['errors'].append(failure)
                raise

    def complete(self, nonce, native, records):
        with self.lock:
            owner = self.cases[nonce]
            require(not owner['errors'] and [r['phase'] for r in owner['receipts']] == list(phases(owner['mode'])),
                    'Actual photo receiver evidence is incomplete')
            evidence = native.get('photoEvidence')
            require(type(evidence) is dict and evidence.get('schema') == 1
                    and evidence.get('runNonce') == nonce and evidence.get('command') == owner['command']
                    and evidence.get('privacyLevel') == owner['privacyLevel'] and evidence.get('mode') == owner['mode']
                    and evidence.get('receipts') == owner['receipts'], 'Native page result differs from receiver bytes')
            require(native.get('nativePrivacyReady') is True and native.get('nativePrivacyLevel') == owner['privacyLevel']
                    and native.get('nativeFingerprintingProtected') is (owner['privacyLevel'] == 2),
                    'Native image privacy policy was not acknowledged')
            if owner['mode'] == 'select':
                for key in ('productionChooserOpened', 'imageMimeAndMultiple', 'pendingPreserved', 'noPhantomUpload', 'desktop'):
                    require(native.get(key) is True, 'Original image chooser regression: '+key)
                require(native.get('upload') == 'ok:photo-123.png:image/png:64x48', 'Original photo identity differs')
            else:
                require(native.get('chooserOpened') is False and native.get('upload') == 'protected:no-selection',
                        'A privacy boundary probe cannot open a chooser')
            verify_native_events(self.identity, owner, native, records)
            owner['native'] = dict(native)
            owner['nativeEvents'] = json.loads(json.dumps(records))
            owner['complete'] = True
            return json.loads(json.dumps(owner))

    def report(self):
        with self.lock:
            rows = json.loads(json.dumps(list(self.cases.values())))
        return dict(schema=1, status='passed' if len(rows) == len(CASES) and all(r.get('complete') for r in rows) else 'incomplete',
                    sourceCommit=self.identity['sourceCommit'], sourceTree=self.identity['sourceTree'],
                    buildIdentity=self.identity, actualAndroidExecution=True, actualGeckoExecution=True,
                    actualHttpImageUpload=True, independentReceiverPixelDecode=True,
                    fixtureSha256=FIXTURE_SHA256, expectedRgbaSha256=digest(expected_rgba()), cases=rows)


def verify_photo_upload_evidence(directory, source, report=None):
    """Re-read original PNG bytes; JSON booleans alone can never pass this gate."""
    directory = Path(directory)
    if report is None:
        report = json.loads((directory/'photo-upload-results.json').read_text())
    require(report.get('schema') == 1 and report.get('status') == 'passed' and report.get('sourceCommit') == source,
            'Source-bound photo evidence is required')
    require(all(report.get(k) is True for k in ('actualAndroidExecution', 'actualGeckoExecution',
                'actualHttpImageUpload', 'independentReceiverPixelDecode')), 'Actual independent photo execution is required')
    require(report.get('fixtureSha256') == FIXTURE_SHA256 and report.get('expectedRgbaSha256') == digest(expected_rgba()),
            'Photo fixture identity differs')
    rows = report['cases']
    require(len(rows) == len(CASES), 'Every photo source and privacy boundary is required')
    require([(r['name'], r['processSlot'], r['privacyLevel'], r['mode'], r['fixtureAction']) for r in rows] == list(CASES),
            'Photo cases are missing, reordered, or changed')
    require(len({r['runNonce'] for r in rows}) == len(rows), 'Photo invocations must be independent')
    files = []
    for row in rows:
        nonce = row['runNonce']
        require(re.fullmatch('[0-9a-f]{32}', nonce) is not None and row.get('complete') is True and not row['errors'],
                'Invalid complete photo invocation')
        require(type(row['command']) is int and 0 < row['command'] < 2**63, 'Invalid photo command')
        require([r['phase'] for r in row['receipts']] == list(phases(row['mode'])), 'Photo encoding coverage differs')
        for receipt in row['receipts']:
            phase = receipt['phase']
            filename = 'photo-upload-'+nonce+'-'+phase+'.png'
            require(receipt['file'] == filename and receipt['runNonce'] == nonce and receipt['command'] == row['command']
                    and receipt['processSlot'] == row['processSlot'] and receipt['fixtureAction'] == row['fixtureAction'],
                    'Photo receipt ownership differs')
            path = directory/filename
            require(path.is_file() and not path.is_symlink(), 'Original uploaded image is missing')
            expected_match = phase not in UNSELECTED or row['privacyLevel'] < 2
            decoded = inspect_png(path.read_bytes(), expected_match=expected_match, original=phase == 'original')
            require(receipt.get('expectedMatch') is expected_match and all(receipt.get(k) == v for k, v in decoded.items()),
                    'Photo receipt differs from independently decoded bytes')
            files.append(filename)
        # Run the same complete native/receiver join without creating files.
        ledger = PhotoUploadLedger(directory, report['buildIdentity'])
        ledger.cases[nonce] = json.loads(json.dumps(row))
        ledger.complete(nonce, row['native'], row['nativeEvents'])
    identity = report['buildIdentity']
    require(identity.get('sourceCommit') == source and identity.get('sourceTree') == report['sourceTree'],
            'Photo installed APK identity differs')
    return dict(status='passed', sourceCommit=source, cases=len(rows), images=len(files),
                independentReceiverPixelDecode=True, fixtureSha256=FIXTURE_SHA256, files=files)
