"""Reverse exactly the four reviewed bridge-lifecycle lines for the reading oracle.

This is a host-test compatibility adapter, not a runtime policy. The protected
GeckoWebView bytes must equal the complete original pre-42 source afterward.
"""
import hashlib
from native43_source_compatibility import native43_preservation_bytes

FROZEN31_PREVIOUS_SHA256 = '80b24f3e89b8ebd8e798d1841b92d006387c9131b00d467228a737b110db5001'
PREVIOUS_INTENDED_TREE = '12f91afcb24b842a371ad8cdb663ff7af04c7b48'
PREVIOUS_SHA256 = '892af2842f87e20f6cf339f6654ca0651cdef11c9bda9ce0477daeff69ecc9bd'
REVIEWED_SHA256 = '07d027899ad2c4a48d3759fe19080d3aa72027aa75aac6147e470f310bb1a5be'
EXACT_PRE42_SHA256 = frozenset((
    PREVIOUS_SHA256,
    '586076cab2cddc3cc013801a8dc8461df688f2615da93bef1c0491b8511abd1a',
    '231cccc9b77c9b66e16dfeb8b0e45e465aeffc2753ffe6a693058b0b357be4b3',
    FROZEN31_PREVIOUS_SHA256,
    '0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10',
))
DELTAS = (
    (b'if(!(message instanceof JSONObject)||incoming!=ports.get(source))return;',
     b'if(!(message instanceof JSONObject)||incoming!=ports.get(source)||staleAppearanceConnections.contains(incoming))return;'),
    (b'appearanceDocuments.remove(port);staleAppearanceConnections.add(port);return;',
     b'appearanceDocuments.remove(port);staleAppearanceConnections.add(port);callbacks.cancel(port);return;'),
    (b'WebExtension.Port port=ports.get(current);if(port==null){if(callback!=null)callback.onReceiveValue("null");return;}',
     b'WebExtension.Port port=ports.get(current);if(port==null||staleAppearanceConnections.contains(port)){if(callback!=null)callback.onReceiveValue("null");return;}'),
    (b'void runEnvironmentAudit(JSONObject configuration,ValueCallback<String> callback){\n    WebExtension.Port port=ports.get(current);\n    if(destroyed||port==null){callback.onReceiveValue("null");return;}',
     b'void runEnvironmentAudit(JSONObject configuration,ValueCallback<String> callback){\n    WebExtension.Port port=ports.get(current);\n    if(destroyed||port==null||staleAppearanceConnections.contains(port)){callback.onReceiveValue("null");return;}'),
)


def bridge42_preservation_bytes(raw):
    raw = native43_preservation_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if digest in EXACT_PRE42_SHA256:
        return raw
    if digest != REVIEWED_SHA256:
        raise ValueError('Bridge42 delta is not the exact reviewed whole sequential browser source')
    for previous, current in DELTAS:
        if raw.count(current) != 1:
            raise ValueError('Bridge lifecycle inverse requires each exact reviewed line once')
        raw = raw.replace(current, previous, 1)
    if hashlib.sha256(raw).hexdigest() != PREVIOUS_SHA256:
        raise ValueError('Bridge lifecycle inverse changed bytes outside its four reviewed lines')
    return raw
