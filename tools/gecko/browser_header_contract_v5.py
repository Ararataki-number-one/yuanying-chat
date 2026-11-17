"""Read compact visual rows and their actual, nonoverlapping Android hit regions.

This is a new header contract. A v4 observation without the native delegate
regions cannot establish the larger targets of a shortened network strip.
"""
import math


def rect(value):
    assert type(value) is list and len(value) == 4 and all(type(v) is int for v in value)
    left, top, right, bottom = value
    assert 0 <= left < right and 0 <= top < bottom
    return value


def intersection(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))


def area(value):
    return (value[2]-value[0]) * (value[3]-value[1])


def inside(inner, outer):
    assert outer[0] <= inner[0] < inner[2] <= outer[2]
    assert outer[1] <= inner[1] < inner[3] <= outer[3]


def network_extension(layout):
    """Choose a full 48 dp side target and a tap in its upward extension."""
    density = layout['density']
    minimum = int(48*density+.5)
    status = layout['networkMetrics']
    touch = rect(status['touchBounds']); visible = rect(status['bounds'])
    capsule = rect(layout['controls'][0]['touch'])
    if visible[3]-visible[1] >= minimum:
        square = [visible[0], visible[1], visible[0]+minimum, visible[1]+minimum]
        return dict(point=[(square[0]+square[2])//2, (square[1]+square[3])//2], bounds=square)
    candidates = ([touch[0], touch[1], capsule[0], touch[3]],
                  [capsule[2], touch[1], touch[2], touch[3]])
    for candidate in candidates:
        if min(candidate[2]-candidate[0], candidate[3]-candidate[1]) >= minimum:
            square = [candidate[0], candidate[1], candidate[0]+minimum, candidate[1]+minimum]
            return dict(point=[(square[0]+square[2])//2, (touch[1]+visible[1])//2], bounds=square)
    raise AssertionError('Compact network strip has no complete 48 dp side target')


def verify_header(layout):
    assert type(layout.get('headerContract')) is int and layout['headerContract'] == 5
    assert layout.get('actualAndroidLayout') is True
    density = layout['density']
    assert type(density) in (int, float) and math.isfinite(density) and density > 0
    minimum = int(48*density+.5)
    toolbar = rect(layout['toolbar']); top = rect(layout['topBounds']); web = rect(layout['webBounds'])
    assert abs((toolbar[2]-toolbar[0])/density-layout['viewportDp']) < .5
    inside(top, toolbar)
    assert toolbar[3] <= web[1]
    assert [value['name'] for value in layout['controls']] == ['environment']
    environment = layout['controls'][0]
    capsule = rect(environment['touch']); face = rect(environment['visible'])
    inside(capsule, toolbar); inside(face, capsule)
    assert min(capsule[2]-capsule[0], capsule[3]-capsule[1]) >= minimum
    status = layout['networkMetrics']; visible = rect(status['bounds']); touch = rect(status['touchBounds'])
    assert layout['networkInHeader'] is layout['networkShown'] is True
    assert status['clickable'] is status['focusable'] is True
    inside(visible, toolbar); inside(touch, toolbar); inside(visible, touch)
    assert top[3] <= visible[1] and capsule[3] <= visible[1]
    assert touch[0] == visible[0] and touch[2:] == visible[2:]
    assert min(touch[2]-touch[0], touch[3]-touch[1]) >= minimum
    assert touch[3] <= web[1], 'Header hit targets must not extend into webpage pixels'
    assert visible[3]-visible[1] >= int(28*density+.5)
    regions = [rect(value) for value in status['effectiveTouchRegions']]
    assert regions, 'Actual TouchDelegateInfo regions are required'
    for index, region in enumerate(regions):
        inside(region, touch)
        assert intersection(region, capsule) == 0, 'Network region steals capsule pixels'
        assert all(intersection(region, prior) == 0 for prior in regions[:index])
    assert sum(map(area, regions)) == area(touch)-intersection(touch, capsule)
    target = network_extension(layout); square = target['bounds']; point = target['point']
    assert min(square[2]-square[0], square[3]-square[1]) >= minimum
    assert sum(intersection(square, region) for region in regions) == area(square)
    assert square[0] <= point[0] < square[2] and square[1] <= point[1] < square[3]
    assert any(region[0] <= point[0] < region[2] and region[1] <= point[1] < region[3] for region in regions)
    return dict(headerContract=5, minimumTouchPixels=minimum, networkExtension=target,
                effectiveRegionsDisjoint=True, webpagePixelsIntercepted=False)
