"""Exact inverse of the two reviewed test-device lease additions.

The real runner has a whole-byte pin. The existing UI verifier also accepts
nonsemantic formatting and a legacy runner without Wellbeing preparation; its
AST adapter below inverts only the complete, positioned lease nodes, before all
original workload and function digests run unchanged.
"""
import ast
import hashlib

PREVIOUS_SHA256 = 'dd46d6a5d7bf3be70359b635b8597a9f3617d399bfb005dcb0c42db6f700b6e0'
CURRENT_SHA256 = '2171e979f5071b4cb002e3b2d606ba38d305ef375bc1d90f44f7d07e17974967'
PREPARATION = (
    'from ui_settings_services_device11 import prepare_workflow as prepare_settings_services_device11, finish_workflow as finish_settings_services_device11\n'
    "settings_services_device11=prepare_settings_services_device11(adb,serial=args.serial,environment=os.environ,root=root,source=source,record_path=out/'ui-settings-services-isolation.json')\n")
ORIGINAL_FINALLY = (
    "    (out/'ui-visual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\\n')\n"
    "    adb('shell','settings','put','system','font_scale','1');adb('shell','wm','size','reset');adb('shell','wm','density','reset')\n")
LEASED_FINALLY = (
    '    try:\n'
    '        finish_settings_services_device11(settings_services_device11,report)\n'
    '    finally:\n'
    "        (out/'ui-visual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\\n')\n"
    "        adb('shell','settings','put','system','font_scale','1');adb('shell','wm','size','reset');adb('shell','wm','density','reset')\n")


def require_runner_source(raw):
    assert isinstance(raw, bytes), 'Complete real UI runner source bytes required'
    assert hashlib.sha256(raw).hexdigest() == CURRENT_SHA256, 'Unreviewed complete UI runner source'
    text = raw.decode('utf-8')
    for added, previous in ((PREPARATION, ''), (LEASED_FINALLY, ORIGINAL_FINALLY)):
        assert text.count(added) == 1, 'Exact UI device lease addition missing, moved or repeated'
        text = text.replace(added, previous, 1)
    result = text.encode('utf-8')
    assert hashlib.sha256(result).hexdigest() == PREVIOUS_SHA256, 'Original complete UI workload did not restore'
    return result


def original_runner_bytes(raw):
    if b'ui_settings_services_device11' not in raw and b'settings_services_device11' not in raw:
        return raw
    return require_runner_source(raw)


def _dump(node):
    return ast.dump(node, include_attributes=False)


def remove_reviewed_lease(tree):
    """Invert only exact whole AST blocks; original UI gates handle every other node."""
    references = [node for node in ast.walk(tree)
                  if (isinstance(node, ast.ImportFrom) and node.module == 'ui_settings_services_device11')
                  or (isinstance(node, ast.Name) and node.id in
                      {'settings_services_device11', 'prepare_settings_services_device11', 'finish_settings_services_device11'})]
    if not references:
        return
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == 'ui_settings_services_device11']
    assert len(imports) == 1, 'One top-level UI device lease import required'
    position = tree.body.index(imports[0])
    block = ast.Module(body=tree.body[position:position + 2], type_ignores=[])
    assert _dump(block) == _dump(ast.parse(PREPARATION)), 'UI device lease preparation changed'
    assert position > 0 and position + 2 < len(tree.body) and isinstance(tree.body[position + 2], ast.FunctionDef) and tree.body[position + 2].name == 'dump', 'UI device lease preparation moved'
    # The previous statement is the original Wellbeing write, or adb when the
    # original compatibility test deliberately removes that independent block.
    preceding = tree.body[position - 1]
    old_preparation = ast.parse("(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')").body[0]
    assert _dump(preceding) == _dump(old_preparation) or (isinstance(preceding, ast.FunctionDef) and preceding.name == 'adb'), 'UI device lease preparation left its original boundary'
    outer = [node for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
    assert len(outer) == 1, 'Original outer UI workload required'
    expected = ast.parse('try:\n    pass\nfinally:\n' + LEASED_FINALLY).body[0].finalbody
    assert _dump(ast.Module(body=outer[0].finalbody, type_ignores=[])) == _dump(ast.Module(body=expected, type_ignores=[])), 'UI device lease cleanup or original finalizer changed'
    assert len(references) == 5, 'UI device lease references moved or duplicated'
    outer[0].finalbody = ast.parse('try:\n    pass\nfinally:\n' + ORIGINAL_FINALLY).body[0].finalbody
    del tree.body[position:position + 2]
