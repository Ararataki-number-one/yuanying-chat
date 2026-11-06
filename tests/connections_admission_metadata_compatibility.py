"""Exact historical metadata closure for the reviewed internal-admission fixture.

No device fixture, runtime source, compiler or behavior host uses this module.
The current callback sidecar remains unchanged on disk. Only retained metadata
oracles receive its complete pre-admission version. The existing root manifest
keeps its original bytes; one declared helper row presents the combined exact
wiring context so every original raw/forward/inverse assertion still executes.
"""
import copy
import hashlib
import json

CALLBACK_PATH = 'tests/fixtures/network-settings-callback-source-deltas.json'
CALLBACK_PREVIOUS_SHA256 = '8f4157350dc8eb9bf2b6c8e6d6345b4383f67c5585198ca4299b0134ae56e21c'
CALLBACK_PREVIOUS_BYTES = 13257
CALLBACK_CURRENT_SHA256 = '232bb1fea99a27287a048771e78d10d47d94802e002db2097c82a12274b2a916'
CALLBACK_CURRENT_BYTES = 17142
JAVA_ROW = 'tests/gecko/NetworkSettingsInternalApplication.java'
JAVA_PREVIOUS_SHA256 = '186200bb223bae81827d1601e71a404fb0b1f784d7e946e560ecd0dcbe535f31'
JAVA_CURRENT_SHA256 = '7c021d415831f3f2651455b9e704f43eca9e51aade247c512240c5fe28d5db55'
ROOT_MANIFEST_SHA256 = 'edad6886ab8867e8d76249de55f9ed23d1b664f830039eaf8e04caf9f9f19e1a'
ROOT_MANIFEST_BYTES = 11333
FINAL_HELPER_PATH = 'tests/final_browser_source_compatibility.py'
FINAL_PREVIOUS_SHA256 = '118fcc1063e93ca7bd96e9fb5e49580c65541faaed0bf7d017ca88c26fe1f1f7'
FINAL_PREVIOUS_BYTES = 16294
FINAL_CURRENT_SHA256 = 'd3e21698222ababe5daffb1286badc4555d01fd4eb5cc12d802d8f2e11a5d221'
FINAL_CURRENT_BYTES = 16519
FINAL_BRANCH = "    if relative == 'tests/fixtures/network-settings-callback-source-deltas.json':\n        from connections_admission_metadata_compatibility import callback_metadata_input\n        return callback_metadata_input(raw, relative)\n"
FINAL_OLD_CONTEXT = 'def metadata_input(raw, relative):\n    """Finite left inputs only; unowned bytes still face the original golden."""\n    _metadata_path(raw, relative)\n    from profile_fixture_root_source_compatibility import PATHS as fixture_root_paths, source_input as fixture_root_input\n    if relative in fixture_root_paths:\n        raw = fixture_root_input(raw, relative)\n    if relative in PATHS:\n        return source_input(raw, relative)\n    if relative in TEMPLATE_PATHS:\n'
ADMISSION_DELTAS = (('64b3e0b0bcc07672ee3f59a0bf989a73acc8de242b2f83fd0092ea0aa5792bf3', 'c95b6e0ee433b76334c35f457eefac2f98724d5195a97663c45ed883c0c478e8'), ('0a3d6920566466b761a51ac8a1f4dd5dc7c231638293fc2a72ea18c852814aaa', '63366f0a417fe03d54d308068a7e9658261ae1e2da9080160a6544a4c7cbc656'), ('36c257f50a40d7c8ebd4251dc85bf56f22519cc43598ad644121900edb506daf', 'abad7f7ee12b7955a335e6d0beda5fedd9dc03f425acee6b9b74dc9aa6e13b3b'), ('2c3a5205ee7b20e7c787e35089e2db629a229a5fe170b00a2c89ee091f1e76c9', '4646ce4c6eadc8942267eb20003bcfb8be8b03ce5f77db00e8f7d7e336292368'))
MAX_METADATA_BYTES = 128 * 1024


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate connections metadata member')
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError('Non-finite connections metadata member')


def callback_metadata_input(raw, relative):
    """One complete reviewed JSON image only; no current Java is projected."""
    if (type(raw) is not bytes or type(relative) is not str or relative != CALLBACK_PATH
            or not 0 < len(raw) <= MAX_METADATA_BYTES):
        raise ValueError('Connections metadata requires its exact bounded path and bytes')
    identity = (_sha(raw), len(raw))
    if identity == (CALLBACK_PREVIOUS_SHA256, CALLBACK_PREVIOUS_BYTES):
        return raw
    if identity != (CALLBACK_CURRENT_SHA256, CALLBACK_CURRENT_BYTES):
        raise ValueError('Connections metadata rejects unknown complete callback bytes')
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    if (type(value) is not dict or type(value.get('files')) is not dict
            or type(value['files'].get(JAVA_ROW)) is not dict):
        raise ValueError('Connections metadata has no exact Java metadata row')
    row = value['files'][JAVA_ROW]
    if (row.get('reviewedSha256') != JAVA_CURRENT_SHA256
            or type(row.get('deltas')) is not list or len(row['deltas']) != 5):
        raise ValueError('Connections metadata has an undeclared Java-row shape')
    for delta, (before, after) in zip(row['deltas'][1:], ADMISSION_DELTAS):
        if (type(delta) is not dict or set(delta) != {'previous', 'current'}
                or any(type(delta.get(key)) is not str for key in ('previous', 'current'))
                or (_sha(delta['previous'].encode()), _sha(delta['current'].encode())) != (before, after)):
            raise ValueError('Connections metadata requires all four exact admission additions')
    row['deltas'] = row['deltas'][:1]
    row['reviewedSha256'] = JAVA_PREVIOUS_SHA256
    restored = _encode(value)
    if (_sha(restored), len(restored)) != (CALLBACK_PREVIOUS_SHA256, CALLBACK_PREVIOUS_BYTES):
        raise ValueError('Connections metadata did not restore the complete old sidecar')
    return restored


def profile_manifest_input(value):
    """Keep five rows/seven contexts; combine only the exact helper wiring row."""
    if (type(value) is not dict or (_sha(_encode(value)), len(_encode(value)))
            != (ROOT_MANIFEST_SHA256, ROOT_MANIFEST_BYTES)):
        raise ValueError('Connections metadata requires the exact prior root manifest')
    view = copy.deepcopy(value)
    row = view['files'][FINAL_HELPER_PATH]
    if ((row['reviewedSha256'], row['reviewedBytes'])
            != (FINAL_PREVIOUS_SHA256, FINAL_PREVIOUS_BYTES)
            or len(row['deltas']) != 1 or row['deltas'][0]['current'] != FINAL_OLD_CONTEXT
            or _sha(FINAL_OLD_CONTEXT.encode()) != row['deltas'][0]['currentSha256']):
        raise ValueError('Connections metadata root helper row differs from its reviewed predecessor')
    anchor = '    _metadata_path(raw, relative)\n'
    if FINAL_OLD_CONTEXT.count(anchor) != 1:
        raise ValueError('Connections metadata requires the unique helper wiring context')
    row['deltas'][0]['current'] = FINAL_OLD_CONTEXT.replace(anchor, anchor + FINAL_BRANCH, 1)
    row['deltas'][0]['currentSha256'] = _sha(row['deltas'][0]['current'].encode())
    row['reviewedSha256'], row['reviewedBytes'] = FINAL_CURRENT_SHA256, FINAL_CURRENT_BYTES
    return view
