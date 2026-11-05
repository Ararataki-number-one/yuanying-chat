"""Bind old bridge negative controls to the actual current audit method.

Only mutation fragments are produced. The runtime host still compiles its raw
current production members; this module never returns an old source image.
"""
import hashlib

ORIGINAL_DELTAS_SHA256 = '5623e6cee60c5064ea01b7dbde6a463c99b8162c85b53284c0a3b2c496b0b599'
AUDIT_METHOD_SHA256 = '235674ddcfab37d54dc276d2333714fd110a60e7cbfe56d5785e2b817ee6e503'
AUDIT_METHOD = b'void runEnvironmentAudit(JSONObject configuration,ValueCallback<String> callback){\n    int budget=14000;\n    if(configuration==null){callback.onReceiveValue("null");return;}\n    if(configuration.has("budgetMillis")){Object value=configuration.opt("budgetMillis");if(!(value instanceof Integer||value instanceof Long)||((Number)value).longValue()<1||((Number)value).longValue()>14000){callback.onReceiveValue("null");return;}budget=((Number)value).intValue();}\n    WebExtension.Port port=ports.get(current);\n    if(destroyed||port==null||staleAppearanceConnections.contains(port)){callback.onReceiveValue("null");return;}\n    int request=callbacks.add(port,callback::onReceiveValue,budget);\n    try{port.postMessage(J.obj("kind","audit","id",request,"configuration",configuration));}\n    catch(Exception error){callbacks.complete(port,request,"null");}\n  }'


def current_deltas(raw, legacy):
    if type(raw) is not bytes or type(legacy) is not tuple or len(legacy) != 4 or any(
            type(pair) is not tuple or len(pair) != 2 or any(type(value) is not bytes for value in pair)
            for pair in legacy):
        raise ValueError('Complete current bridge bytes and original four mutation pairs required')
    if hashlib.sha256(b'\0'.join(value for pair in legacy for value in pair)).hexdigest() != ORIGINAL_DELTAS_SHA256:
        raise ValueError('Original four bridge protections differ')
    if hashlib.sha256(AUDIT_METHOD).hexdigest() != AUDIT_METHOD_SHA256 or raw.count(AUDIT_METHOD) != 1:
        raise ValueError('Current complete audit method is missing, duplicated or changed')
    current = AUDIT_METHOD.split(b'\n    int request=', 1)[0]
    lines = current.splitlines(keepends=True)
    if lines[0] + b''.join(lines[4:]) != legacy[3][1] or current.count(b'||staleAppearanceConnections.contains(port)') != 1:
        raise ValueError('Audit budget/null additions do not preserve the original stale-port predicate')
    previous = current.replace(b'||staleAppearanceConnections.contains(port)', b'', 1)
    pairs = legacy[:3] + ((previous, current),)
    if any(raw.count(after) != 1 for _, after in pairs):
        raise ValueError('Each actual current protection must be independently observable once')
    return pairs
