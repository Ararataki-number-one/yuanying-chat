"""Exact read-only43 accessor inverse before the original42/39/37/32 reading chain.

This changes host-test inputs only. Any unknown whole-source bytes remain errors.
"""
import hashlib
from experience46_source_compatibility import experience46_source_bytes

PREVIOUS_INTENDED_TREE = '2b2dc1ee24305e020222941f96f851e365af4d62'
PREVIOUS_SHA256 = '07d027899ad2c4a48d3759fe19080d3aa72027aa75aac6147e470f310bb1a5be'
REVIEWED_SHA256 = '32e06089272bbbaf63ed94449ea208cd2feb930cc05a903ab3e83efb0f140546'
EXACT_PRE43_SHA256 = frozenset((
    PREVIOUS_SHA256,
    '892af2842f87e20f6cf339f6654ca0651cdef11c9bda9ce0477daeff69ecc9bd',
    '586076cab2cddc3cc013801a8dc8461df688f2615da93bef1c0491b8511abd1a',
    '231cccc9b77c9b66e16dfeb8b0e45e465aeffc2753ffe6a693058b0b357be4b3',
    '80b24f3e89b8ebd8e798d1841b92d006387c9131b00d467228a737b110db5001',
    '0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10',
))
EXACT_ACCESSORS = (b'  Object nativeRuntimeIdentity(){return destroyed||!enabled||owner.deleted?null:runtime;}\n', b'  JSONObject nativeRuntimeCapabilities(){\n    JSONObject value=GeckoPolicyAdapter.runtimeCapabilityStatus((GeckoRuntime)nativeRuntimeIdentity(),Build.VERSION.SDK_INT);\n    try{value.put("environmentId",owner.environmentId);value.put("environmentGeneration",owner.environmentGeneration);value.put("configurationRevision",owner.identityAuditAppliedRevision());value.put("identityPolicyRevision",identityPolicyRevision);}catch(JSONException ignored){}\n    return value;\n  }\n')


def native43_preservation_bytes(raw):
    digest = hashlib.sha256(raw).hexdigest()
    if digest in EXACT_PRE43_SHA256:
        return raw
    raw = experience46_source_bytes(raw, 'app/src/main/java/local/pocketchat/GeckoWebView.java')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != REVIEWED_SHA256:
        raise ValueError('Native43 delta is not the exact reviewed whole sequential browser source')
    for addition in EXACT_ACCESSORS:
        if raw.count(addition) != 1:
            raise ValueError('Native43 inverse requires both exact read-only accessors once')
        raw = raw.replace(addition, b'', 1)
    if hashlib.sha256(raw).hexdigest() != PREVIOUS_SHA256:
        raise ValueError('Native43 inverse did not restore the complete intended42 browser source')
    return raw
