"""Bounded comparison input only; runtime always executes the current runner."""
import hashlib

BEFORE_IMPORT = b'from network_inactive_label46 import visible_inactive_route\n'
AFTER_IMPORT = b'from network_inactive_card_v2 import visible_inactive_route\n'
BEFORE_SHA256 = '12c74d6158fb3b30034ef472930928a73d85db97c8aad5f71a9f519711cbeb85'
AFTER_SHA256 = 'ade4660d4237ff70e824550d3c5f8dd517a941904a5a3aa8db1ca2f39d8ff0a8'


def historical_runner_input(raw):
    if type(raw) is not bytes:
        raise ValueError('Ordinary exact runner bytes required')
    digest = hashlib.sha256(raw).hexdigest()
    if digest == BEFORE_SHA256 and raw.count(BEFORE_IMPORT) == 1 and AFTER_IMPORT not in raw:
        return raw
    if digest != AFTER_SHA256 or raw.count(AFTER_IMPORT) != 1 or BEFORE_IMPORT in raw:
        raise ValueError('Unknown current network-source UI runner input')
    before = raw.replace(AFTER_IMPORT, BEFORE_IMPORT, 1)
    if hashlib.sha256(before).hexdigest() != BEFORE_SHA256 or before.replace(BEFORE_IMPORT, AFTER_IMPORT, 1) != raw:
        raise ValueError('Network-source UI whole runner inverse differs')
    return before
