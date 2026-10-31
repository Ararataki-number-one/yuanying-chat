"""Finite14 test-input inverses before unchanged UI and sharing oracles.

Real runner bytes have complete pins. The UI AST inverse handles only the
existing optimization-loop acquisition; every original downstream digest still
runs, including legitimate formatting and the old no-preparation variant.
"""
import ast
import functools
import hashlib

UI_PREVIOUS_SHA256 = '2171e979f5071b4cb002e3b2d606ba38d305ef375bc1d90f44f7d07e17974967'
UI_CURRENT_SHA256 = 'e955b67f4e1afefe6a5253875ca527a54b8a72c789e17c0903bc2c395bd3c99d'
UI_BEFORE = """        deadline=time.monotonic()+30
        while True:
            xml=dump()
            if '勾选允许使用的入口' in xml:break
"""
UI_AFTER = UI_BEFORE.replace('xml=dump()', 'xml=dump(deadline=deadline)')
UI_OLD_LOOP_AST = '3a8bf08dc824d5a3e70e8f0ac9b31fab5bf78bfaab5be941807adf708beac42a'
UI_NEW_LOOP_AST = '48cfa7a625b5b1b241a83eb5cc4d0566b824887fe19e4150296e5f6192e28518'
SHARING_PREVIOUS_SHA256 = 'baaae558c646be27cd480fde071fc18dc8b962c43b6c593521b3968751dd538b'
SHARING_CURRENT_SHA256 = '23efd31d1a044ffa0ff46b94d903f664389bd77ff6a33c3a8723ba773566870c'
SHARING_OLD_AST = 'e09acac5878b2b7a37ef07376f315ec05e93bc1f68ee5c4460f920b50782706d'
SHARING_NEW_AST = '0a784116bf10e6502ab7423bf8afcd9b2b5b87a7429590eba2715e1c020581e3'
SHARING_IMPORT = 'from network_sharing_lease14 import prepare as prepare_sharing_lease14, finish as finish_sharing_lease14\n'
SHARING_PREPARE = 'sharing_lease14=prepare_sharing_lease14(root,out,a)\n'
SHARING_FINALLY = 'finally:\n finish_sharing_lease14(sharing_lease14)\n'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_digest(tree):
    return digest(ast.dump(tree, include_attributes=False).encode())


def original_ui13_bytes(raw):
    assert type(raw) is bytes, 'Complete UI runner bytes required'
    value = digest(raw)
    if value == UI_PREVIOUS_SHA256:
        return raw
    assert value == UI_CURRENT_SHA256, 'Unreviewed14 complete UI runner source'
    before, after = UI_BEFORE.encode(), UI_AFTER.encode()
    assert raw.count(after) == 1 and raw.count(before) == 0, 'Bounded UI acquisition missing, moved or repeated'
    old = raw.replace(after, before, 1)
    assert digest(old) == UI_PREVIOUS_SHA256 and old.replace(before, after, 1) == raw, 'Entire13 UI source did not restore'
    return old


def require_current_ui14(raw):
    assert type(raw) is bytes and digest(raw) == UI_CURRENT_SHA256, 'Actual selected14 UI fix required'
    return original_ui13_bytes(raw)


def optimization_loop(tree):
    outer = [node for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
    assert len(outer) == 1, 'Original outer UI workload required'
    body = outer[0].body
    marker = ast.dump(ast.parse('optimization=[]').body[0], include_attributes=False)
    positions = [i for i, node in enumerate(body) if ast.dump(node, include_attributes=False) == marker]
    assert len(positions) == 1, 'One original optimization initialization required'
    position = positions[0] + 1
    assert position + 1 < len(body) and isinstance(body[position], ast.For), 'Original optimization loop moved'
    assert ast.dump(body[position + 1], include_attributes=False) == ast.dump(ast.parse('compact=[]').body[0], include_attributes=False), 'Original optimization boundary changed'
    return body[position]


def remove_reviewed_ui14_deadline(tree):
    loop = optimization_loop(tree)
    current = tree_digest(loop)
    if current == UI_OLD_LOOP_AST:
        return
    assert current == UI_NEW_LOOP_AST, 'Unreviewed complete optimization-loop AST'
    waits = [node for node in loop.body if isinstance(node, ast.While)]
    assert len(waits) == 1 and waits[0].body, 'Original readiness loop required'
    expected = ast.parse('xml=dump(deadline=deadline)').body[0]
    assert ast.dump(waits[0].body[0], include_attributes=False) == ast.dump(expected, include_attributes=False), 'Existing deadline acquisition moved'
    waits[0].body[0] = ast.parse('xml=dump()').body[0]
    assert tree_digest(loop) == UI_OLD_LOOP_AST, 'Original complete optimization loop did not restore'


def wrap_ui_source_inverse(original):
    @functools.wraps(original)
    def exact14_ui_input(raw):
        return original(original_ui13_bytes(raw))
    return exact14_ui_input


def wrap_ui_ast_inverse(original):
    @functools.wraps(original)
    def exact14_ui_tree(tree):
        remove_reviewed_ui14_deadline(tree)
        return original(tree)
    return exact14_ui_tree


def original_sharing13_bytes(raw):
    assert type(raw) is bytes, 'Complete sharing runner bytes required'
    value = digest(raw)
    if value == SHARING_PREVIOUS_SHA256:
        return raw
    assert value == SHARING_CURRENT_SHA256, 'Unreviewed14 complete sharing runner source'
    text = raw.decode()
    anchor = 'from gecko.network_sources_contract import verify_network_sharing\n'
    assert text.count(anchor + SHARING_IMPORT) == 1 and text.count(SHARING_IMPORT) == 1, 'Sharing lease import moved or repeated'
    assert text.count(' return json.loads(raw)\n' + SHARING_PREPARE + 'try:\n') == 1, 'Sharing preparation left its original boundary'
    assert text.count(SHARING_PREPARE) == 1 and text.count(SHARING_FINALLY) == 1 and text.endswith(SHARING_FINALLY), 'Sharing finally missing, moved or repeated'
    for added in (SHARING_IMPORT, SHARING_PREPARE, SHARING_FINALLY):
        text = text.replace(added, '', 1)
    old = text.encode()
    assert digest(old) == SHARING_PREVIOUS_SHA256, 'Entire original sharing flow did not restore'
    return old


def require_current_sharing14(raw):
    assert type(raw) is bytes and digest(raw) == SHARING_CURRENT_SHA256, 'Actual selected14 sharing lease required'
    return original_sharing13_bytes(raw)


def original_sharing13_tree(tree):
    """Retain exact full semantics while permitting nonsemantic formatting."""
    value = tree_digest(tree)
    if value == SHARING_OLD_AST:
        return tree
    assert value == SHARING_NEW_AST, 'Unreviewed complete sharing AST'
    imported = ast.parse(SHARING_IMPORT).body[0]
    prepared = ast.parse(SHARING_PREPARE).body[0]
    for expected in (imported, prepared):
        positions = [i for i, node in enumerate(tree.body) if ast.dump(node, include_attributes=False) == ast.dump(expected, include_attributes=False)]
        assert len(positions) == 1, 'One positioned sharing lease node required'
        del tree.body[positions[0]]
    outer = [node for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
    assert len(outer) == 1, 'One original sharing workload required'
    expected = ast.parse('try:\n pass\n' + SHARING_FINALLY).body[0].finalbody
    assert ast.dump(ast.Module(body=outer[0].finalbody, type_ignores=[]), include_attributes=False) == ast.dump(ast.Module(body=expected, type_ignores=[]), include_attributes=False), 'Sharing cleanup changed'
    outer[0].finalbody = []
    assert tree_digest(tree) == SHARING_OLD_AST, 'Original sharing AST did not restore'
    return tree
