"""Exact 2.0.46 visible-label port of the immutable inactive-route predicate.

The captured Android XML is consumed unchanged. This ports only the expected
status text to the user-facing 2.0.46 label; every original predicate byte and
its card, route, count, bounds and read-only checks remain otherwise identical.
The original tool and all other helpers remain unchanged.
"""
import hashlib
from pathlib import Path

ORIGINAL_PATH = Path(__file__).resolve().parents[2] / 'tools/gecko/network_ui_route_contract.py'
ORIGINAL_SHA256 = 'f7a1e1d8b136022604778f7664f6e9df374b64253c0b4045ea9a395c8f2e06b0'
ORIGINAL_CONTEXT = "                for label in ('● 未运行', '当前没有运行线路'):\n".encode()
CURRENT_CONTEXT = "                for label in ('● 未连接', '当前没有运行线路'):\n".encode()


def port_original_source(raw):
    """Reject any whole-source drift before making one exact label change."""
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Inactive-route original module identity differs')
    if raw.count(ORIGINAL_CONTEXT) != 1 or CURRENT_CONTEXT in raw:
        raise ValueError('Inactive-route exact original label context differs')
    current = raw.replace(ORIGINAL_CONTEXT, CURRENT_CONTEXT, 1)
    if current.count(CURRENT_CONTEXT) != 1 or current.replace(CURRENT_CONTEXT, ORIGINAL_CONTEXT, 1) != raw:
        raise ValueError('Inactive-route complete label inverse differs')
    return current


_namespace = {'__name__': 'network_ui_route_contract46_exact_label_port'}
exec(compile(port_original_source(ORIGINAL_PATH.read_bytes()),
             str(ORIGINAL_PATH) + ' [2.0.46 exact inactive-label port]', 'exec'), _namespace)
visible_inactive_route = _namespace['visible_inactive_route']
