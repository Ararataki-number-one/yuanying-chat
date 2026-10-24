"""Pure source contract: retain the original UI workload plus owned label evidence.

The constants come from 64be4b4's runner (raw SHA eb44194a...7612b), not a new
whole-file receipt. The only permitted additions are the four reviewed 08f1c19
download-label changes. Each added AST block is checked before normalization;
we never discard arbitrary scene branches or statements. No git history, adb,
runner imports, or device execution is needed in a shallow CI checkout.
"""
import ast
import hashlib


BASELINE = '64be4b4dc5a3ab36f0399412128f8425b71cd9bb'
ORIGINAL_MODULE_AST = '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1'
ORIGINAL_CAPTURE_AST = '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5'
# Complete original functions: transport/readiness/taps, callbacks supplied to
# collapse, and the controlled reload prerequisite. The module check below also
# retains their bindings, CLI/source identity, adb_bytes lambda, call order,
# servers, 111 capture loops, existing assertions, failure and cleanup paths.
ORIGINAL_FUNCTIONS = {
    'adb': 'ce733c48ffcb9d7bf0201a8430adce0ec8d29a7bdbc538e3ef35be83e556643f',
    'dump': '36573a7a814a3ec6484b5925f9a1b0f9b99a175811931f8056a98ad61498afa5',
    'click': '2684472f9af043ca16f5565ecf1f72f45351a51eadac8628630f465d0d924a42',
    'click_editor_tab': '4bb39545238dc9907926e815c2e955f14d8a7187af9d706f00fa951fccf62978',
    'checkpoint': '57d58a5ee75695c7e54a44fbf3a0799022d02767dde3a617ae241ac33a852f3b',
    'chrome_event': 'da73722387fbb0e2c956bc27f79d1039ec280fda10b573a5b7cb5245db7c97a9',
    'focus': '985e91fa8a40db36eba9dae3c36ff2216e155e60bfa1d6f4f0431bb6d9ce0f4c',
    'visible': '513634dfad52319c46a9bba50e114511830076b4d781787f04a59d6fe832ba62',
    'reload_check': '54bf48fcebb09189e358e7bd3ad71a32d121df2206852fec411427269d793c10',
    'reload_command': 'bdfc637b69bb168afd0311d0d3725a278277a754dedf60d0b58ecfb5d58f6713',
    'reload_tap': '1bc2d286f0098cd0dbb9e84b24dad548987eaeb45a5a068fecc2000dacf71707',
    'reload_ready': 'e36ad6d10fabb18970eac03ba1bb86899772d529a9455c6158e067e90d8fbc01',
}
DOWNLOAD_LAUNCH_AST = 'a954b0ab4d47f62d510691507c2d8bd1dd82c0736b570a91d31c73ca6523a214'
DOWNLOAD_EVIDENCE_AST = '48e3a45f0c60cce356412c6f77f1aaf234b22f4b9c375299599d43f6a8bb43e7'
ORIGINAL_LAUNCH = "adb('shell','am','start','-W','-n',package+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction',scene)"


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def exactly_one(nodes, description):
    values = list(nodes)
    assert len(values) == 1, ('Expected one source node', description, len(values))
    return values[0]


def assignment(node, name):
    return (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name)


def verify_shared_ui_source(source):
    # Match Python's parsing of the real UTF-8 file, including coding cookies.
    tree = ast.parse(source.encode('utf-8'))
    for name, expected in ORIGINAL_FUNCTIONS.items():
        function = exactly_one((node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name), name)
        assert digest(function) == expected, ('Original UI helper changed', name)
    capture = exactly_one((node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'capture'), 'capture')
    imports = exactly_one((node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == 'ui_visual_contract'), 'visual contract import')
    additions = [name for name in imports.names if name.name == 'verify_download_location']
    if additions:
        assert len(additions) == 1 and additions[0].asname is None, 'Ambiguous download verifier import'
        imports.names.remove(additions[0])
        start = exactly_one((index for index, node in enumerate(capture.body)
            if assignment(node, 'label_nonce')), 'owned download launch')
        launch = ast.Module(body=capture.body[start:start + 4], type_ignores=[])
        # Exact scene guard, nonce, original launch arguments and one adb call.
        assert digest(launch) == DOWNLOAD_LAUNCH_AST, 'Download launch escaped its reviewed scope'
        capture.body[start:start + 4] = ast.parse(ORIGINAL_LAUNCH).body
        record = exactly_one((index for index, node in enumerate(capture.body)
            if assignment(node, 'record')), 'capture record')
        observation = capture.body[record + 1]
        # Includes strict UTF-8/JSON, owned nonce, one raw payload, persistence and
        # actual verifier invocation. No weakened/extra code is normalized away.
        assert digest(observation) == DOWNLOAD_EVIDENCE_AST, 'Download observation changed'
        del capture.body[record + 1]
        final = exactly_one((node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'verify_captures'), 'public capture verification')
        assert ast.dump(final, include_attributes=False) == ast.dump(
            ast.parse('verify_captures(records,source)').body[0].value,
            include_attributes=False), 'Source-bound capture verification changed'
        final.args.pop()
    assert digest(capture) == ORIGINAL_CAPTURE_AST, 'Original capture actions/readiness/gates changed'
    assert digest(tree) == ORIGINAL_MODULE_AST, 'Original UI workload/bindings/gates changed'
    return {'baselineSourceCommit': BASELINE,
            'selectedSourceSha256': hashlib.sha256(source.encode()).hexdigest(),
            'originalFunctionsAstSha256': dict(ORIGINAL_FUNCTIONS),
            'normalizedCaptureAstSha256': digest(capture),
            'normalizedModuleAstSha256': digest(tree),
            'authorizedDownloadLabelAddition': bool(additions),
            'originalWorkloadSemanticsPreserved': True,
            'actualAndroidExecution': False}
