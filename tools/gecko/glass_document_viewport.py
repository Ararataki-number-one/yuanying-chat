"""Reject a ready document whose real Gecko or Android viewport is empty.

Positive dimensions establish layout, not rendered pixels or visual quality.
Original Android PNGs and recordings still require independent inspection.
"""
import math


def require_document_viewport(observation):
    if not isinstance(observation, dict):
        raise ValueError('An actual document observation is required')
    if (observation.get('visibleDocument') is not True
            or type(observation.get('loadingCoverVisibility')) is not int
            or observation['loadingCoverVisibility'] != 8):
        raise ValueError('The production document must be visible without its loading cover')
    dimensions = {}
    for name in ('innerWidth', 'innerHeight', 'webWidth', 'webHeight'):
        value = observation.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('The actual document and native view need positive viewport dimensions: ' + name)
        dimensions[name] = value
    return dict(status='verified', **dimensions,
                scope='Actual page and native layout dimensions only; original PNG/MP4 visual inspection remains required')
