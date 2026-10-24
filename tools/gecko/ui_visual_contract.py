"""Required native UI captures, shared by Android capture and publication checks."""
import json
import math
import re

LIGHT_SCENES = ('chat', 'environments', 'network', 'proxy', 'entries', 'browser', 'preferences', 'settings', 'network-menu')
LARGE_SCENES = ('proxy', 'entries', 'browser', 'preferences', 'chat', 'settings', 'network-menu', 'environments', 'network')
DARK_SCENES = ('chat', 'environments', 'network', 'settings', 'network-menu')

DETAIL_SCENES = ('environment-picker', 'downloads', 'feedback', 'appearance', 'default-entry',
                 'subscription-form', 'exit-form', 'route-editor', 'import', 'brand', 'templates', 'zoom', 'update', 'audit', 'file-preview', 'delete-file', 'share-preview')
LIGHT_SCENES += DETAIL_SCENES
LARGE_SCENES += DETAIL_SCENES
DARK_SCENES += DETAIL_SCENES
LANDSCAPE_SCENES = ('chat', 'environments', 'settings', 'environment-picker', 'downloads',
                    'feedback', 'exit-form', 'route-editor', 'brand', 'templates', 'file-preview')


def required_captures():
    return {
        ('light', viewport, 1, scene)
        for viewport in ('360x640', '412x640') for scene in LIGHT_SCENES
    } | {('light', '640x360', 1, scene) for scene in LANDSCAPE_SCENES} | {('light', '360x640', 2, scene) for scene in LARGE_SCENES} | {
        ('dark', '360x640', 1, scene) for scene in DARK_SCENES
    }


def verify_captures(records, source=None):
    expected = required_captures()
    assert len(records) == len(expected), 'Missing or duplicate native UI captures'
    assert all(item['variant'] == 'current' for item in records), 'Every capture must use the current application'
    actual = {(item['theme'], item['logicalViewport'], item['fontScale'], item['scene']) for item in records}
    assert actual == expected, ('Native UI coverage differs', expected - actual, actual - expected)

    downloads = [item for item in records if item['scene'] == 'downloads']
    for item in downloads:
        verify_download_location(item, source)
    assert len({item['downloadLocationNonce'] for item in downloads}) == len(downloads), 'Download label captures reused an invocation'


def verify_download_location(record, source=None):
    """Actual native Layout evidence; XML's untruncated text alone is insufficient."""
    def pairs(values):
        result = {}
        for key, value in values:
            assert key not in result, 'Duplicate label evidence field'
            result[key] = value
        return result
    raw = record['downloadLocationRaw']
    assert isinstance(raw, str) and len(raw.encode('utf-8')) <= 3500
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite label evidence')))
    assert type(value['schema']) is int and value['schema'] == 1
    assert value['status'] == 'observed' and value['scene'] == record['scene'] == 'downloads'
    assert re.fullmatch('[0-9a-f]{40}', value['sourceCommit']) and (source is None or value['sourceCommit'] == source)
    assert value['nonce'] == record['downloadLocationNonce'] and re.fullmatch('[0-9a-f]{32}', value['nonce'])
    assert all(value[key] is True for key in ('actualAndroidLayout', 'shown', 'enabled', 'clickable', 'windowFocused'))
    assert value['layoutRequested'] is False and value['text'] == '保存位置' and value['layoutTextLength'] == 4
    assert value['viewClass'] == 'local.pocketchat.DesignUi$ActionButton' and value['layoutClass'].startswith('android.text.')
    number = lambda v: type(v) in (int, float) and math.isfinite(v)
    assert number(value['fontScale']) and value['fontScale'] == record['fontScale']
    assert number(value['density']) and value['density'] > 0 and abs(value['density'] * 160 - record['densityDpi']) < .01
    keys = ('width', 'height', 'contentWidth', 'contentHeight', 'layoutWidth', 'layoutHeight', 'left', 'top', 'visibleWidth', 'visibleHeight', 'scrollX', 'scrollY', 'startedUptimeMs', 'observedUptimeMs')
    assert all(type(value[key]) is int and value[key] >= 0 for key in keys)
    assert value['width'] >= 48 * value['density'] and value['height'] >= 48 * value['density'], 'Download location touch target below 48 dp'
    assert value['visibleWidth'] == value['width'] and value['visibleHeight'] == value['height'], 'Download location button clipped'
    assert value['left'] + value['width'] <= record['actualPixels'][0] and value['top'] + value['height'] <= record['actualPixels'][1]
    assert 0 < value['layoutWidth'] <= value['contentWidth'] <= value['width']
    assert 0 < value['layoutHeight'] <= value['contentHeight'] <= value['height'], 'Download label vertically clipped'
    assert value['scrollX'] == value['scrollY'] == 0 and value['observedUptimeMs'] >= value['startedUptimeMs'] > 0
    lines = value['lines']; assert isinstance(lines, list) and 1 <= len(lines) <= 8
    end, bottom = 0, 0
    for line in lines:
        assert all(type(line[key]) is int for key in ('start', 'end', 'bottom', 'ellipsisCount'))
        assert line['start'] == end < line['end'] <= 4 and line['ellipsisCount'] == 0, 'Download label is incomplete or ellipsized'
        assert number(line['left']) and number(line['right']) and -.5 <= line['left'] < line['right'] <= value['layoutWidth'] + .5, 'Download label horizontally clipped'
        assert bottom < line['bottom'] <= value['layoutHeight']
        end, bottom = line['end'], line['bottom']
    assert end == 4, 'Download label omits trailing text'
    return value
