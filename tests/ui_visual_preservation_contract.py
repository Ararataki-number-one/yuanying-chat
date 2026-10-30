"""Pure source contract: retain the original UI workload plus owned label evidence.

The constants come from 64be4b4's runner (raw SHA eb44194a...7612b), not a new
whole-file receipt. Permitted additions are the four reviewed 08f1c19 download
label changes and the exact CI device-preparation block below. Each added AST
block is checked before normalization;
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
UI_DEVICE_PREPARATION_AST = 'a15fbf39a69774bfdbe021b92ed1906657601ca3f3f58fcde8e6837f81a75c25'
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


def remove_reviewed_ui_device_preparation(tree):
    """Invert exactly two top-level nodes between the original adb and dump.

    The full block digest includes the imported function/alias, report path,
    helper arguments, CI environment mapping, serialization and write call.
    Never normalize unrelated statements or accept a partial/relocated block.
    """
    candidates = [node for node in ast.walk(tree)
                  if isinstance(node, ast.ImportFrom) and node.module == 'ui_test_device']
    if not candidates:
        return
    imported = exactly_one(candidates, 'CI UI device preparation import')
    start = exactly_one((index for index, node in enumerate(tree.body)
                         if node is imported), 'top-level CI UI device preparation')
    block = ast.Module(body=tree.body[start:start + 2], type_ignores=[])
    assert digest(block) == UI_DEVICE_PREPARATION_AST, 'CI UI device preparation changed'
    assert (start > 0 and start + 2 < len(tree.body)
            and isinstance(tree.body[start - 1], ast.FunctionDef)
            and tree.body[start - 1].name == 'adb'
            and isinstance(tree.body[start + 2], ast.FunctionDef)
            and tree.body[start + 2].name == 'dump'), 'CI UI device preparation moved'
    del tree.body[start:start + 2]



DIAGNOSTIC_PRIVACY_IMPORT = 'from diagnostic_capture_privacy import checked_text\n'
DIAGNOSTIC_PRIVACY_WRITES = tuple(
    ("(out/'" + name + "').write_text(adb('logcat','-d'))",
     "(out/'" + name + "').write_text(checked_text(adb('logcat','-d'))[0])")
    for name in ('ui-reload-log.txt', 'ui-visual-log.txt'))


def original_ui_diagnostic_privacy_bytes(raw):
    """Undo only the three exact producer additions before old whole-byte pins."""
    assert isinstance(raw, bytes), 'UI source bytes required'
    text = raw.decode('utf-8')
    if 'diagnostic_capture_privacy' not in text and 'checked_text' not in text:
        return raw
    anchor = 'from ui_visual_capture import UiVisualCapture\n' + DIAGNOSTIC_PRIVACY_IMPORT
    assert text.count(anchor) == 1 and text.count(DIAGNOSTIC_PRIVACY_IMPORT) == 1, 'Diagnostic privacy import changed or moved'
    text = text.replace(anchor, 'from ui_visual_capture import UiVisualCapture\n', 1)
    for previous, added in DIAGNOSTIC_PRIVACY_WRITES:
        assert text.count(added) == 1, 'Diagnostic privacy write changed, missing or duplicated'
        text = text.replace(added, previous, 1)
    return text.encode('utf-8')


def remove_reviewed_diagnostic_privacy(tree):
    """Restore only an exact import and two diagnostic writes, preserving old AST gates.

    Functional adb/capture/readiness/input nodes are never removed or rewritten.
    The original full-module digest below still verifies every remaining node.
    """
    imports = [node for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) and node.module == 'diagnostic_capture_privacy']
    uses = [node for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == 'checked_text']
    if not imports and not uses:
        return
    imported = exactly_one(imports, 'diagnostic privacy import')
    expected_import = ast.parse(DIAGNOSTIC_PRIVACY_IMPORT).body[0]
    assert ast.dump(imported, include_attributes=False) == ast.dump(expected_import, include_attributes=False), 'Diagnostic privacy import changed'
    position = exactly_one((index for index, node in enumerate(tree.body)
                            if node is imported), 'top-level diagnostic privacy import')
    assert (position > 0 and position + 1 < len(tree.body)
            and isinstance(tree.body[position - 1], ast.ImportFrom)
            and tree.body[position - 1].module == 'ui_visual_capture'
            and isinstance(tree.body[position + 1], ast.ImportFrom)
            and tree.body[position + 1].module == 'ui_visual_contract'), 'Diagnostic privacy import moved'
    assert len(uses) == 2, 'Diagnostic privacy helper has unreviewed uses'
    for previous, added in DIAGNOSTIC_PRIVACY_WRITES:
        expected = ast.parse(added).body[0]
        match = exactly_one((node for node in ast.walk(tree)
                             if isinstance(node, ast.Expr)
                             and ast.dump(node, include_attributes=False) == ast.dump(expected, include_attributes=False)),
                            'exact diagnostic write')
        # Only the argument of the exact diagnostic write is restored. The
        # containing statement and all action/control-flow positions stay put.
        match.value.args[0] = ast.parse(previous).body[0].value.args[0]
    del tree.body[position]


def original_ui_privacy_verifier_function(function):
    """Remove one exact normalization call before the old verifier-function pin."""
    expected = ast.parse('remove_reviewed_diagnostic_privacy(tree)').body[0]
    positions = [index for index, node in enumerate(function.body)
                 if ast.dump(node, include_attributes=False) == ast.dump(expected, include_attributes=False)]
    assert positions == [1], 'Diagnostic privacy verifier call missing, duplicated or moved'
    assert ast.dump(function.body[0], include_attributes=False) == ast.dump(
        ast.parse("tree = ast.parse(source.encode('utf-8'))").body[0], include_attributes=False), 'Original UTF8 parser changed'
    assert ast.dump(function.body[2], include_attributes=False) == ast.dump(
        ast.parse('remove_reviewed_ui_device_preparation(tree)').body[0], include_attributes=False), 'Original preparation normalizer changed'
    del function.body[1]
    return function


def verify_shared_ui_source(source):
    # Match Python's parsing of the real UTF-8 file, including coding cookies.
    tree = ast.parse(source.encode('utf-8'))
    remove_reviewed_diagnostic_privacy(tree)
    remove_reviewed_ui_device_preparation(tree)
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
