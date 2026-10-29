"""Exact User 0 controlled-IME guard for the new compatibility fixture only.

Host fake-ADB controls exercise this code; only real CI commands establish Android state.
The original 155-case workload must run outside this guard with its stock IME.
"""
from dataclasses import dataclass
import hashlib
import re
import shlex
import time

SERIAL = 'emulator-5554'
COMPONENT = 'local.pocketchat.test/local.pocketchat.ControlledCaretInputMethodService'
KEYS = ('default_input_method', 'enabled_input_methods',
        'selected_input_method_subtype', 'input_methods_subtype_history')
PACKAGE_PART = r'[A-Za-z_][A-Za-z0-9_]*'
CLASS_PART = r'[A-Za-z_$][A-Za-z0-9_$]*'
COMPONENT_RE = PACKAGE_PART + r'(?:\.' + PACKAGE_PART + r')*/(?:\.)?' + CLASS_PART + r'(?:\.' + CLASS_PART + r')*'
METHOD_DUMP_COMMAND = ('shell', 'dumpsys', '--priority', 'CRITICAL', 'input_method')
METHOD_DUMP_BYTES = 4 * 1024 * 1024
IDENTITY_FIELDS = ('sourceCommit', 'sourceTree', 'runId', 'runAttempt',
                   'integrationApkSha256', 'sdkReceiptSha256')


def require(condition, message):
    if not condition:
        raise ValueError('Controlled IME guard: ' + message)


# General diagnostic capture privacy lives here because this already source-bound
# test-only module is copied with the unchanged IME evidence verifier. It never
# changes browser settings or the values sent to Android/the network.
PRIVACY_POLICY = 'known-service-keys-v1'
PRIVACY_REPLACEMENT = '[REDACTED_SERVICE_API_KEY]'
PRIVACY_MAX_BYTES = 16 * 1024 * 1024
PRIVACY_MAX_REPLACEMENTS = 4096
PRIVACY_KINDS = ('gboard', 'mozilla-location', 'google-safebrowsing', 'google-api-key-shape')
_API_KEY_SHAPE = re.compile(r'(?<![A-Za-z0-9_-])AIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])')
_API_KEY_CANDIDATE = re.compile(r'(?<![A-Za-z0-9_%\\-])(?:A|%41|\\u0041)(?:I|%49|\\u0049)(?:z|%7[aA]|\\u007[aA])(?:a|%61|\\u0061)(?:[A-Za-z0-9_-]|%[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}){35}(?![A-Za-z0-9_%-])')
_URL_START = re.compile(r'(?:h|%68)(?:t|%74)(?:t|%74)(?:p|%70)(?:s|%73)(?::|%3a)', re.I)


def _privacy_require(value):
    if not value:
        raise ValueError('Diagnostic capture privacy: rejected bounded capture')


def _privacy_projection(value, positions, percent):
    out, mapping, index = [], [], 0
    while index < len(value):
        width, char = 1, value[index]
        if char == '\\' and index + 1 < len(value) and value[index + 1] == '/':
            width, char = 2, '/'
        elif char == '\\' and index + 5 < len(value) and value[index + 1] == 'u' and re.fullmatch('[0-9a-fA-F]{4}', value[index + 2:index + 6]):
            decoded = chr(int(value[index + 2:index + 6], 16))
            if ord(decoded) < 128:
                width, char = 6, decoded
        elif percent and char == '%' and index + 2 < len(value) and re.fullmatch('[0-9a-fA-F]{2}', value[index + 1:index + 3]):
            width, char = 3, chr(int(value[index + 1:index + 3], 16))
        out.append(char); mapping.append((positions[index][0], positions[index + width - 1][1])); index += width
    return ''.join(out), mapping


def _privacy_spans(text):
    from urllib.parse import urlsplit, unquote
    spans = []
    # Decode only a bounded candidate projection, retaining offsets into the
    # original capture. Replacement never rewrites non-key URL bytes.
    for match in _URL_START.finditer(text):
        start = match.start()
        preview = text[start:start + 320]
        preview, unused = _privacy_projection(preview, [(i,i+1) for i in range(len(preview))], '%' in match.group(0))
        if re.match(r'https://(?:location\.services\.mozilla\.com|safebrowsing\.googleapis\.com)(?=[:/?#]|$)', preview, re.I) is None:
            continue
        end = start
        while end < len(text) and text[end] not in '\r\n\t \"\'<>':
            end += 1
            _privacy_require(end - start <= 4096)
        while end > start and text[end - 1] == '\\':
            end -= 1
        raw = text[start:end]
        positions = [(start + i, start + i + 1) for i in range(len(raw))]
        projected, positions = _privacy_projection(raw, positions, '%' in match.group(0))
        try:
            url = urlsplit(projected)
        except ValueError:
            _privacy_require(False)
        kind = ('mozilla-location' if url.hostname == 'location.services.mozilla.com' and url.path == '/v1/country'
                else 'google-safebrowsing' if url.hostname == 'safebrowsing.googleapis.com' else None)
        if kind is None or url.scheme.lower() != 'https' or not url.query:
            continue
        query_start = projected.find('?') + 1
        for parameter in re.finditer(r'(?:^|&)([^=&]*?)=([^&#]*)', url.query):
            if unquote(parameter.group(1)).lower() != 'key':
                continue
            first = query_start + parameter.start(2); last = query_start + parameter.end(2)
            if first == last or unquote(projected[first:last]) == PRIVACY_REPLACEMENT:
                continue
            spans.append((positions[first][0], positions[last - 1][1], kind))
            _privacy_require(len(spans) <= PRIVACY_MAX_REPLACEMENTS)
    for match in _API_KEY_CANDIDATE.finditer(text):
        candidate = match.group(0)
        projected, unused = _privacy_projection(candidate, [(i,i+1) for i in range(len(candidate))], True)
        if _API_KEY_SHAPE.fullmatch(projected) is None:
            continue
        if any(first <= match.start() and match.end() <= last for first, last, _ in spans):
            continue
        prefix = text[max(0, match.start() - 160):match.start()]
        kind = 'gboard' if re.search(r'expressive_stickers_api_key[^\r\n]{0,100}$', prefix) else 'google-api-key-shape'
        spans.append((match.start(), match.end(), kind)); _privacy_require(len(spans) <= PRIVACY_MAX_REPLACEMENTS)
    spans.sort()
    _privacy_require(all(spans[i - 1][1] <= spans[i][0] for i in range(1, len(spans))))
    return spans


def service_api_key_findings(text):
    """Return only fixed classifications and hashes; never a credential value."""
    _privacy_require(isinstance(text, str) and len(text.encode('utf-8')) <= PRIVACY_MAX_BYTES)
    return [dict(kind=kind, sha256=hashlib.sha256(text[first:last].encode('utf-8')).hexdigest())
            for first, last, kind in _privacy_spans(text)]


def redact_service_api_keys(text, *, max_bytes=PRIVACY_MAX_BYTES):
    _privacy_require(isinstance(text, str) and type(max_bytes) is int and 0 <= max_bytes <= PRIVACY_MAX_BYTES)
    original = text.encode('utf-8'); _privacy_require(len(original) <= max_bytes)
    spans = _privacy_spans(text); pieces, previous = [], 0
    counts = dict.fromkeys(PRIVACY_KINDS, 0)
    for first, last, kind in spans:
        pieces.extend((text[previous:first], PRIVACY_REPLACEMENT)); previous = last; counts[kind] += 1
    pieces.append(text[previous:]); sanitized = ''.join(pieces); final = sanitized.encode('utf-8')
    _privacy_require(len(final) <= PRIVACY_MAX_BYTES)
    metadata = dict(schema=1, kind='service-api-key-value-redaction', policy=PRIVACY_POLICY,
                    originalBytes=len(original), originalSha256=hashlib.sha256(original).hexdigest(),
                    finalBytes=len(final), finalSha256=hashlib.sha256(final).hexdigest(),
                    changed=bool(spans), replacements=counts)
    return sanitized, metadata


def verify_capture_privacy(metadata, sanitized):
    """Validate explicitly derivative stored bytes; source hashes are provenance,
    not independent proof that a discarded original capture was authentic."""
    if not isinstance(metadata, dict) or set(metadata) != {'schema','kind','policy','originalBytes','originalSha256','finalBytes','finalSha256','changed','replacements'} or not isinstance(sanitized, str):
        return False
    if type(metadata['schema']) is not int or metadata['schema'] != 1 or metadata['kind'] != 'service-api-key-value-redaction' or metadata['policy'] != PRIVACY_POLICY or type(metadata['changed']) is not bool:
        return False
    counts = metadata['replacements']
    if not isinstance(counts, dict) or set(counts) != set(PRIVACY_KINDS) or not all(type(v) is int and 0 <= v <= PRIVACY_MAX_REPLACEMENTS for v in counts.values()):
        return False
    total = sum(counts.values())
    if total > PRIVACY_MAX_REPLACEMENTS or metadata['changed'] != (total > 0):
        return False
    if not all(type(metadata[k]) is int and 0 <= metadata[k] <= PRIVACY_MAX_BYTES for k in ('originalBytes','finalBytes')) or not all(isinstance(metadata[k], str) and re.fullmatch('[0-9a-f]{64}', metadata[k]) for k in ('originalSha256','finalSha256')):
        return False
    final = sanitized.encode('utf-8')
    if metadata['finalBytes'] != len(final) or metadata['finalSha256'] != hashlib.sha256(final).hexdigest():
        return False
    if not total and (metadata['originalBytes'] != len(final) or metadata['originalSha256'] != metadata['finalSha256']):
        return False
    if total and (metadata['originalBytes'] == 0 or metadata['originalSha256'] == metadata['finalSha256'] or sanitized.count(PRIVACY_REPLACEMENT) < total):
        return False
    try:
        return not service_api_key_findings(sanitized)
    except ValueError:
        return False


def diagnostic_privacy_summary(captures):
    return dict(schema=1, kind='sanitized-diagnostic-captures', policy=PRIVACY_POLICY,
                captureCount=len(captures), changedCaptureCount=sum(1 for item in captures if item['changed']),
                scope='Complete stored captures with only declared service API-key values removed; not untouched Android raw output.',
                captures=list(captures))


def assert_public_diagnostic_text(path, raw):
    """A public text gate fails closed. Binary APK/PNG callers stay explicit."""
    _privacy_require(isinstance(raw, bytes) and len(raw) <= PRIVACY_MAX_BYTES)
    try:
        # Legacy raw/log/text evidence may contain arbitrary bytes. Its scan
        # projection never replaces stored/archive/hash bytes. Invalid bytes
        # become non-ASCII separators, leaving ASCII API-key shapes visible.
        legacy = getattr(path, 'suffix', '').lower() in ('.raw','.log','.txt')
        legacy = legacy or (getattr(path,'name','') == 'manifest.json' and getattr(getattr(path,'parent',None),'name','') in ('window-network-identity-android-host-results-raw','window-network-identity-desktop-host-results-raw'))
        text = raw.decode('utf-8', errors='replace' if legacy else 'strict')
    except UnicodeDecodeError:
        raise ValueError('Diagnostic publication privacy: text encoding rejected') from None
    if service_api_key_findings(text):
        name = getattr(path, 'name', '')
        if not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,160}', name):
            name = 'diagnostic-text'
        raise ValueError('Diagnostic publication privacy: rejected file=' + name + ' sha256=' + hashlib.sha256(raw).hexdigest())


def canonical_component(value):
    require(isinstance(value, str) and re.fullmatch(COMPONENT_RE, value), 'safe component required')
    package, activity = value.split('/')
    return package + '/' + (package + activity if activity.startswith('.') else activity)


def subtype(value):
    require(isinstance(value, str) and re.fullmatch(r'-?(?:0|[1-9][0-9]*)', value), 'subtype integer required')
    require(-(2**31) <= int(value) < 2**31, 'subtype outside Android integer range')
    return value


def enabled_entries(raw):
    require(isinstance(raw, str) and 0 < len(raw) <= 8192, 'nonempty bounded enabled list required')
    result = []
    for entry in raw.split(':'):
        fields = entry.split(';')
        item = canonical_component(fields[0])
        for value in fields[1:]:
            subtype(value)
        require(item not in result, 'duplicate enabled component')
        result.append(item)
    return tuple(result)


def valid_history(raw):
    require(isinstance(raw, str) and len(raw) <= 8192, 'bounded subtype history required')
    if raw in ('', 'null'):
        return raw
    seen = set()
    for entry in raw.split(':'):
        fields = entry.split(';')
        require(len(fields) == 2, 'history must contain one component/subtype pair')
        name = canonical_component(fields[0])
        require(name not in seen, 'duplicate subtype history component')
        seen.add(name)
        subtype(fields[1])
    return raw


def component_list(raw):
    require(isinstance(raw, str) and len(raw) <= 65536, 'bounded actual IME list required')
    values = tuple(canonical_component(line) for line in raw.splitlines() if line)
    require(len(values) == len(set(values)), 'duplicate actual IME list component')
    return values


def _method_block(raw):
    """Extract only the actual Android 35 service's top-level state.

    AOSP android-15.0.0_r1 InputMethodManagerService.java lines 6085/6113/6114
    prints this exact header/User/current-method format. Its SHA256 is
    3657ba927c0316c53ea39f5090f5c115dce1adeed136595d31e745c36f413264.
    mCurMethodId is getSelectedMethodIdLocked(); mCurId is a separate bound
    method and may temporarily be null. Nested method/client/history dumps must
    never authorize another user's selection. CRITICAL stops before remote IPC.
    """
    require(isinstance(raw, str) and len(raw.encode('utf-8')) <= METHOD_DUMP_BYTES,
            'bounded actual input_method dump required')
    lines = raw.splitlines()
    headers = [index for index, line in enumerate(lines) if line == 'Current Input Method Manager state:']
    require(len(headers) == 1, 'one actual Android 35 service header required')
    block = []
    for line in lines[headers[0] + 1:]:
        if line and not line.startswith(' '):
            break
        block.append(line)
    return block


def current_method(raw):
    block = _method_block(raw)
    users = [match[1] for line in block if (match := re.fullmatch(r'  mCurrentUserId=([0-9]+)', line))]
    values = [match[1] for line in block if (match := re.fullmatch(r'  mCurMethodId=([^ \t\r\n]+)', line))]
    require(users == ['0'] and len(values) == 1, 'one top-level User 0 selected method required')
    return canonical_component(values[0])


def active_method(raw):
    """Observe selected and actually bound identities at the end of the protocol.

    The same AOSP 35 dump prints mCurId/getCurId followed by the actual connection,
    bound and visible flags on one top-level line. A selected IME alone does not
    prove binding. Null remains an observed null, never the selected component.
    """
    selected = current_method(raw)
    values = [match for line in _method_block(raw)
              if (match := re.fullmatch(r'  mCurId=([^ \t\r\n]+) mHaveConnection=(true|false) '
                                       r'mBoundToMethod=(true|false) mVisibleBound=(true|false)', line))]
    require(len(values) == 1, 'one actual top-level bound method and flags required')
    value = values[0]
    return dict(selectedComponent=selected,
                boundComponent=None if value[1] == 'null' else canonical_component(value[1]),
                haveConnection=value[2] == 'true', boundToMethod=value[3] == 'true',
                visibleBound=value[4] == 'true')


@dataclass(frozen=True)
class Snapshot:
    settings: tuple
    selected: str
    enabled: tuple
    actual_enabled: tuple
    registered: tuple
    actual_current: str
    all_raw: str
    enabled_list_raw: str
    method_dump_raw: str

    def report(self):
        return dict(settings=dict(zip(KEYS, self.settings)), selectedComponent=self.selected,
                    enabledComponents=list(self.enabled), actualEnabledComponents=list(self.actual_enabled),
                    registeredComponents=list(self.registered), actualSelectedComponent=self.actual_current,
                    allImeListRaw=self.all_raw, enabledImeListRaw=self.enabled_list_raw,
                    inputMethodDumpRaw=self.method_dump_raw)

    def state(self):
        # Runtime handles, history display and client windows in the dump change.
        # Exact settings and actual selected/enabled/registered identities do not.
        return (self.settings, self.selected, self.enabled, self.actual_enabled,
                self.registered, self.actual_current)


def _private_diagnostic_excerpt(value, limit, *, tail=False):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    value = str(value)
    # Filter the bounded complete value before taking either excerpt. Larger
    # captures retain only the existing size/hash evidence and a fixed label.
    try:
        filtered, metadata = redact_service_api_keys(value)
        return filtered[-limit:] if tail else filtered[:limit]
    except ValueError:
        return '[diagnostic excerpt unavailable]'


def _private_diagnostic_exception(error):
    # Preserve the original failure class/object/status while removing only
    # captured service-key values from messages propagated to outer collectors.
    error.args = tuple(_private_diagnostic_excerpt(value,8192) if isinstance(value,(str,bytes)) else value for value in error.args)
    return error


def _privacy_ime_identity_lines(value):
    return tuple(line for line in value.splitlines() if re.match(
        r'^\s*(?:mCurMethodId|mCurId|mCurToken|mCurClient|mBoundToMethod|mBindSequence|mCurrentUserId|mCurFocusedWindow|mHaveConnection|mCurMethod)\s*=', line))


class ControlledImeGuard:
    def __init__(self, *, adb, identity, record, nonce, serial=SERIAL, clock=time.monotonic_ns):
        require(serial == SERIAL, 'only fixed synthetic target permitted')
        require(isinstance(identity, dict), 'source/run identity required')
        for field in ('sourceCommit', 'sourceTree'):
            require(isinstance(identity.get(field), str) and re.fullmatch(r'[0-9a-f]{40}', identity[field]), field)
        for field in ('runId', 'runAttempt'):
            require(isinstance(identity.get(field), str) and re.fullmatch(r'[1-9][0-9]*', identity[field]), field)
        for field in ('integrationApkSha256', 'sdkReceiptSha256'):
            require(isinstance(identity.get(field), str) and re.fullmatch(r'[0-9a-f]{64}', identity[field]), field)
        require(isinstance(nonce, str) and re.fullmatch(r'[0-9a-f]{32}', nonce), 'owned nonce required')
        self.adapter, self.clock, self.record = adb, clock, record
        self.initial, self.changed, self.used = None, False, False
        record.update({field: identity[field] for field in IDENTITY_FIELDS})
        record.update(schema=1, status='failed', identity=dict(identity), runNonce=nonce,
                      serial=SERIAL, user=0, exactFixtureComponent=COMPONENT, commands=[],
                      mutationAttempted=False, restorationVerified=False, physicalPhoneAcceptance=False,
                      vendorKeyboardUiAcceptance=False, applicationAcceptance=False,
                      scope='Exact emulator/User 0 state around unchanged original-SDK compatibility protocol; complete stored capture with only declared service API-key values redacted, not untouched Android raw output; not vendor keyboard or phone acceptance.')

    def command(self, *parts):
        row = dict(parts=list(parts), startedAtMonotonicNanos=self.clock())
        self.record['commands'].append(row)
        try:
            value = self.adapter(*parts)
            row['stdoutType'] = type(value).__name__
            if isinstance(value, str):
                raw = value.encode('utf-8')
                allowed = len(raw) <= METHOD_DUMP_BYTES if parts == METHOD_DUMP_COMMAND else len(value) <= 131072
                if not allowed:
                    row.update(stdoutChars=len(value), stdoutBytes=len(raw), stdoutSha256=hashlib.sha256(raw).hexdigest(),
                               stdoutFirst=_private_diagnostic_excerpt(value,4096),
                               stdoutLast=_private_diagnostic_excerpt(value,4096,tail=True), stdoutTruncated=True)
                require(allowed, 'bounded actual stdout required')
                original = value
                value, privacy = redact_service_api_keys(value)
                if parts == METHOD_DUMP_COMMAND:
                    require(_privacy_ime_identity_lines(original) == _privacy_ime_identity_lines(value), 'native method identity lines changed by capture privacy')
                    require(len(value.encode('utf-8')) <= METHOD_DUMP_BYTES, 'bounded final method stdout required')
                row['capturePrivacy'] = privacy
                raw = value.encode('utf-8')
                row.update(stdoutChars=len(value), stdoutBytes=len(raw), stdoutSha256=hashlib.sha256(raw).hexdigest())
            else:
                row.update(stdoutChars=None, stdoutBytes=None, stdoutSha256=None)
                require(False, 'actual string stdout required')
            row.update(stdout=value, status='passed')
            return value
        except BaseException as error:
            _private_diagnostic_exception(error)
            row.update(status='failed', errorType=type(error).__name__, error=_private_diagnostic_excerpt(error,8192))
            for field in ('stdout', 'output', 'stderr'):
                value = getattr(error, field, None)
                if value is not None:
                    limit = 131072 if field != 'stderr' else 8192
                    if isinstance(value, bytes):
                        value = value[:limit].decode('utf-8', errors='replace')
                    filtered = _private_diagnostic_excerpt(value,limit)
                    row[field] = filtered
                    try:
                        setattr(error,field,filtered)
                    except (AttributeError,TypeError):
                        pass
            raise
        finally:
            row['completedAtMonotonicNanos'] = self.clock()

    def setting(self, name):
        require(name in KEYS, 'setting outside explicit IME allowlist')
        raw = self.command('shell', 'settings', '--user', '0', 'get', 'secure', name)
        value = raw.removesuffix('\n').removesuffix('\r')
        require(not any(char in value for char in ('\n', '\r', '\x00')), 'multiline secure setting rejected')
        return value

    def snapshot(self):
        selected, enabled, selected_subtype, history = (self.setting(key) for key in KEYS)
        selected_name, names = canonical_component(selected), enabled_entries(enabled)
        require(selected_name in names, 'selected method must be enabled')
        if selected_subtype != 'null':
            subtype(selected_subtype)
        valid_history(history)
        all_raw = self.command('shell', 'ime', 'list', '-a', '-s', '--user', '0')
        enabled_list_raw = self.command('shell', 'ime', 'list', '-s', '--user', '0')
        registered, actual_enabled = component_list(all_raw), component_list(enabled_list_raw)
        require(set(names) == set(actual_enabled) and set(names) <= set(registered),
                'secure enabled list differs from actual registered/enabled methods')
        method_dump_raw = self.command(*METHOD_DUMP_COMMAND)
        actual_current = current_method(method_dump_raw)
        require(actual_current == selected_name, 'secure and actual current IME differ')
        value = Snapshot((selected, enabled, selected_subtype, history), selected_name, names,
                         actual_enabled, registered, actual_current, all_raw, enabled_list_raw, method_dump_raw)
        return value

    def prepare(self):
        self.record['prepareStartedAtMonotonicNanos'] = self.clock()
        require(self.command('shell', 'getprop', 'ro.kernel.qemu').strip() == '1', 'confirmed QEMU required')
        require(self.command('shell', 'am', 'get-current-user').strip() == '0', 'current User 0 required')
        require(self.command('shell', 'getprop', 'ro.build.version.sdk').strip() == '35', 'supported Android 35 state format required')
        self.record['confirmedQemu'] = self.record['confirmedUser0'] = True
        self.record['confirmedAndroidSdk'] = 35
        self.initial = self.snapshot()
        self.record['initial'] = self.initial.report()
        require(COMPONENT in self.initial.registered, 'exact owned fixture must already be installed/registered')
        require(self.initial.selected != COMPONENT,
                'already selected fixture may indicate an unrecovered earlier run')
        self.changed = True  # Failed command may already have mutated Android.
        self.record['mutationAttempted'] = True
        if COMPONENT not in self.initial.enabled:
            self.command('shell', 'ime', 'enable', '--user', '0', COMPONENT)
        self.command('shell', 'ime', 'set', '--user', '0', COMPONENT)
        during = self.snapshot()
        expected_raw = self.initial.settings[1]
        if COMPONENT not in self.initial.enabled:
            expected_raw += ':' + COMPONENT
        require(during.settings[1] == expected_raw and during.actual_current == COMPONENT,
                'owned switch altered another enabled entry/subtype or did not become current')
        require(during.registered == self.initial.registered, 'registered IME set changed during switch')
        self.record['during'] = during.report()
        self.record['preparedAtMonotonicNanos'] = self.clock()

    def restore(self):
        self.record['restoreStartedAtMonotonicNanos'] = self.clock()
        if self.changed:
            self.command('shell', 'ime', 'set', '--user', '0', shlex.quote(self.initial.settings[0]))
            if COMPONENT not in self.initial.enabled:
                self.command('shell', 'ime', 'disable', '--user', '0', COMPONENT)
            # ime set changes subtype and history. Restore only these captured keys.
            # Quote history as remote-shell data: semicolons must never become commands.
            for name, expected in (('selected_input_method_subtype', self.initial.settings[2]),
                                   ('input_methods_subtype_history', self.initial.settings[3])):
                if self.setting(name) != expected:
                    if expected == 'null':
                        self.command('shell', 'settings', '--user', '0', 'delete', 'secure', name)
                    else:
                        self.command('shell', 'settings', '--user', '0', 'put', 'secure', name, shlex.quote(expected))
            restored = self.snapshot()
            self.record['restored'] = restored.report()
            # Raw order, subtype suffixes, absent values and semantic state all matter.
            require(restored.state() == self.initial.state(), 'exact initial IME state was not restored')
        self.record['restorationVerified'] = True
        self.record['restoredAtMonotonicNanos'] = self.clock()

    def observe_active(self):
        value = dict(startedAtMonotonicNanos=self.clock(), status='failed',
                     scope='End-of-focused-protocol binding observation only; not every historical IME instant.')
        self.record['activeInputMethod'] = value
        try:
            raw = self.command(*METHOD_DUMP_COMMAND)
            value['inputMethodDumpRaw'] = raw
            value.update(active_method(raw))
            require(value['selectedComponent'] == value['boundComponent'] == COMPONENT
                    and value['haveConnection'] and value['boundToMethod'],
                    'the selected controlled IME was not actually connected/bound at protocol completion')
            value['status'] = 'passed'
        except BaseException as error:
            _private_diagnostic_exception(error)
            value.update(errorType=type(error).__name__, error=_private_diagnostic_excerpt(error,8192))
            raise
        finally:
            value['completedAtMonotonicNanos'] = self.clock()

    def run(self, workload):
        require(not self.used, 'guard cannot replay a workload')
        self.used = True
        failure, result = None, None
        failure_stage = 'prepare'
        try:
            self.prepare()
            self.record['workloadInvocationCount'] = 1
            self.record['workloadStartedAtMonotonicNanos'] = self.clock()
            failure_stage = 'workload'
            try:
                result = workload()
                failure_stage = 'workload-exit'
                require(type(result) is int and 0 <= result <= 255, 'workload terminated or invalid exit status')
                if result == 0:
                    failure_stage = 'active-input-method'
                    self.observe_active()
            finally:
                self.record['workloadCompletedAtMonotonicNanos'] = self.clock()
        except BaseException as error:
            _private_diagnostic_exception(error)
            failure = error
            self.record.update(errorType=type(error).__name__, error=_private_diagnostic_excerpt(error,8192), failureStage=failure_stage,
                               workloadStatus='failed' if failure_stage == 'workload' else 'unaccepted')
        try:
            self.restore()
        except BaseException as error:
            _private_diagnostic_exception(error)
            self.record.update(restoreErrorType=type(error).__name__, restoreError=_private_diagnostic_excerpt(error,8192), fatal=True,
                               failureStage='restore')
            raise RuntimeError('Exact IME restoration failed; later suites must not run') from error
        if failure is not None:
            raise failure
        self.record.update(status='passed', workloadExitCode=result,
                           workloadStatus='passed' if result == 0 else 'failed')
        return result
