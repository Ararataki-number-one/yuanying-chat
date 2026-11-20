#!/usr/bin/env bash
set -euo pipefail

output=${1:?Output directory for the synthetic transcripts}
commit=${SOURCE_COMMIT:?Exact candidate source commit required}
tree=${SOURCE_TREE:?Exact candidate source tree required}
nonce=${NONCE:?Fresh fixture nonce required}
base=${BASE_SHA:?Installed base APK SHA-256 required}
feature=${FEATURE_SHA:?Installed Chromium APK SHA-256 required}
serial=${TEST_SERIAL:?Explicit disposable emulator serial required}
[[ $serial =~ ^emulator-[0-9]+$ && $commit =~ ^[0-9a-f]{40}$ && $tree =~ ^[0-9a-f]{40}$ \
    && $nonce =~ ^[0-9a-f]{32}$ && $base =~ ^[0-9a-f]{64}$ && $feature =~ ^[0-9a-f]{64}$ ]]
adb=(adb)
if [[ -n ${TEST_ADB_PORT:-} ]]; then adb+=(-P "$TEST_ADB_PORT"); fi
adb+=(-s "$serial")
[[ $("${adb[@]}" shell getprop ro.kernel.qemu | tr -d '\r') == 1 ]]
mkdir -p "$output"

for mode in files profile-seed profile-read; do
    if [[ $mode == profile-read ]]; then
        "${adb[@]}" shell am force-stop local.pocketchat.test
    fi
    timeout 420 "${adb[@]}" shell am instrument -w \
        -e fixtureMode "$mode" -e sourceCommit "$commit" -e sourceTree "$tree" \
        -e runNonce "$nonce" -e baseSha256 "$base" -e featureSha256 "$feature" \
        local.pocketchat.chromiumfixture/.RouteFixture | tr -d '\r' | tee "$output/$mode.txt"
    grep -qx 'INSTRUMENTATION_CODE: -1' "$output/$mode.txt"
done

python3 - "$output" "$commit" "$tree" "$nonce" "$base" "$feature" <<'PY'
from pathlib import Path
import re
import sys

output, commit, tree, nonce, base, feature = sys.argv[1:]
expected = dict(scope='integration-clean-source-synthetic-chromium-files-and-profiles',
                package='local.pocketchat.test', sourceCommit=commit, sourceTree=tree, runNonce=nonce,
                baseSha256=base, featureSha256=feature, androidExecution='true',
                noSystemWebViewProvider='true', abi='x86_64', realChatGptAcceptance='false')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def receipt(mode, flags, hashes):
    log = (Path(output) / f'{mode}.txt').read_text()
    require(re.findall(r'^INSTRUMENTATION_CODE:\s*(-?\d+)\s*$', log, re.M) == ['-1'], f'{mode}: unsuccessful run')
    entries = re.findall(r'^INSTRUMENTATION_RESULT: (\w+)=(.*)$', log, re.M)
    fields = dict(entries)
    require(len(entries) == len(fields), f'{mode}: duplicate result field')
    for key, value in dict(expected, fixtureMode=mode, **flags).items():
        require(fields.get(key) == value, f'{mode}: missing or unexpected {key}')
    for key in hashes:
        require(re.fullmatch(r'[0-9a-f]{64}', fields.get(key, '')), f'{mode}: missing {key}')
    for key in ('nativeRenderers', 'fixturePid'):
        require(re.fullmatch(r'[1-9][0-9]*', fields.get(key, '')), f'{mode}: missing positive {key}')
    return fields


receipt('files', dict(androidDocumentsPickerOpened='true', trustedUploadClick='true', uploadUserActivation='true',
                      selectedUploadBytesMatched='true',
                      fileOwnerSlot='1', realPdfAndDocxSavedBytesMatched='true'), ('pdfSha256', 'docxSha256'))
profiles = ('profile0Sha256', 'profile1Sha256')
seed, read = (receipt(mode, dict(twoChromiumProfilesIsolated='true', persistentHttpOnlyCookieRead=done,
                                 persistentLocalStorageRead=done), profiles)
              for mode, done in (('profile-seed', 'false'), ('profile-read', 'true')))
require(seed['fixturePid'] != read['fixturePid'], 'The profile checks did not observe a new Chromium app process')
require(all(seed[key] == read[key] for key in profiles) and read[profiles[0]] != read[profiles[1]],
        'Stable and separate Chromium profile identities were not preserved')
print('Synthetic native Chromium file transfers and two profile states verified across an app process restart.')
PY
