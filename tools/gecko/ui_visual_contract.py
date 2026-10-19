"""Required native UI captures, shared by Android capture and publication checks."""

LIGHT_SCENES = ('chat', 'environments', 'network', 'proxy', 'entries', 'browser', 'preferences', 'settings', 'network-menu')
LARGE_SCENES = ('proxy', 'entries', 'browser', 'preferences', 'chat', 'settings', 'network-menu')
DARK_SCENES = ('chat', 'environments', 'network', 'settings', 'network-menu')


def required_captures():
    return {
        ('light', viewport, 1, scene)
        for viewport in ('360x640', '412x640') for scene in LIGHT_SCENES
    } | {('light', '360x640', 2, scene) for scene in LARGE_SCENES} | {
        ('dark', '360x640', 1, scene) for scene in DARK_SCENES
    }


def verify_captures(records):
    expected = required_captures()
    assert len(records) == len(expected), 'Missing or duplicate native UI captures'
    assert all(item['variant'] == 'current' for item in records), 'Every capture must use the current application'
    actual = {(item['theme'], item['logicalViewport'], item['fontScale'], item['scene']) for item in records}
    assert actual == expected, ('Native UI coverage differs', expected - actual, actual - expected)
