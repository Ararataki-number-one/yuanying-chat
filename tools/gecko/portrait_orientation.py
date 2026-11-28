"""Measure resumed Android Activity configuration while the device requests a turn."""
from contextlib import contextmanager
import hashlib
import re
import struct
import time
import xml.etree.ElementTree as ET

CONTROL = 'local.pocketchat.RotationControlActivity'
TEST_PACKAGE = 'local.pocketchat.test'

try:
    from .ui_visual_contract import verify_observation, verify_challenge
except ImportError:
    from ui_visual_contract import verify_observation, verify_challenge


def _component(value):
    package, name = value.split('/', 1)
    return package + '/' + (package + name if name.startswith('.') else name)


def observe(adb, package, rotation, *, control=False, timeout=14):
    """Measure the real resumed Activity's own bounds, including for a dialog on top."""
    component = package + '/' + CONTROL
    expected = 'landscape' if control and rotation in (1, 3) else 'portrait'
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        activity = adb('shell', 'dumpsys activity activities | grep -E "topResumedActivity|mResumedActivity" || true')
        matches = re.findall(r'(?:topResumedActivity|mResumedActivity)\s*[:=][^\n]*?\bu\d+\s+([\w.$]+/[\w.$]+)', activity)
        top = _component(matches[0]) if matches else ''
        if top.startswith(package + '/') and ((top == component) == control):
            dump = adb('shell', 'dumpsys activity top | grep -E "^ *ACTIVITY |mCurrentConfig=" || true')
            headers = list(re.finditer(r'^\s*ACTIVITY\s+(\S+)[^\n]*', dump, re.M))
            for i, header in enumerate(headers):
                if _component(header.group(1)) != top:
                    continue
                block = dump[header.end():headers[i+1].start() if i+1 < len(headers) else len(dump)]
                config = re.search(r'\bmCurrentConfig=[^\n]+',block)
                if not config:
                    continue
                direction = re.search(r'\s(port|land)\s',config.group())
                rect = re.search(r'\bmBounds=Rect\((-?\d+),\s*(-?\d+)\s*-\s*(-?\d+),\s*(-?\d+)\)',config.group())
                if not direction or not rect:
                    continue
                l,t,r,b = map(int,rect.groups())
                requested = adb('shell','settings','get','system','user_rotation').strip()
                automatic = adb('shell','settings','get','system','accelerometer_rotation').strip()
                last = dict(component=top, orientation={'port':'portrait','land':'landscape'}[direction[1]],
                            bounds=[l,t,r,b], userRotation=requested, accelerometerRotation=automatic,
                            activityConfig=config.group().strip())
                if (requested == str(rotation) and automatic == '0' and last['orientation'] == expected
                        and min(r-l,b-t)>0 and (r-l>b-t if expected=='landscape' else b-t>r-l)):
                    return last
        time.sleep(.2)
    raise ValueError(f'Expected {expected} from live Activity after rotation {rotation}, last observation {last}, resumed {top}')


def wm_command(adb):
    help_text=adb('shell','wm help 2>&1 || :')
    commands=re.findall(r'^\s+(user-rotation|set-user-rotation)\s+\[',help_text,re.M)
    if len(commands)!=1:raise ValueError('Ambiguous Android window rotation command')
    return commands[0]


def previous_mode(settings):
    rotation=settings['user_rotation']
    return ('lock', rotation if rotation in ('0','1','2','3') else '0') if settings['accelerometer_rotation']=='0' else ('free',)


def request(adb, value):
    adb('shell','wm',wm_command(adb),'lock',str(value))


def portrait_frame(adb, binary, read_xml, package, width_dp, height_dp, density, rotation=1):
    """Bracket the real PNG and UI tree with the same foreground window measurement."""
    expected=[width_dp*density//160,height_dp*density//160]
    request(adb,rotation)
    first=observe(adb,package,rotation)
    size=adb('shell','wm','size').strip()
    dpi=adb('shell','wm','density').strip()
    sizes=re.findall(r'(?:Physical|Override) size:\s*(\d+)x(\d+)',size)
    densities=re.findall(r'(?:Physical|Override) density:\s*(\d+)',dpi)
    if not sizes or list(map(int,sizes[-1]))!=expected or not densities or int(densities[-1])!=density:
        raise ValueError(f'Actual Android screen configuration differs from the requested viewport: {size}, {dpi}, {expected}')
    xml=read_xml()
    # Disconnecting Android's hierarchy automation can restore the visible rotation
    # as the user's rotation. Restore the real sideways request before framing the PNG.
    request(adb,rotation)
    before_png=observe(adb,package,rotation)
    raw=binary('exec-out','screencap','-p')
    last=observe(adb,package,rotation)
    pixels=list(struct.unpack('>II',raw[16:24]))
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or pixels!=expected:
        raise ValueError(f'Actual screen PNG dimensions differ: {pixels}, {expected}')
    if any(item['component']!=last['component'] or item['bounds']!=last['bounds'] for item in (first,before_png)) or last['bounds']!=[0,0,*expected]:
        raise ValueError(f'Portrait capture changed Activity or window bounds: {first}, {before_png}, {last}')
    if not any(n.get('package')==package for n in ET.fromstring(xml).iter('node')):
        raise ValueError('Captured hierarchy has no current application window')
    last.update(requestedDp=[width_dp,height_dp],densityDpi=density,wmSize=size,wmDensity=dpi,
                actualPngPixels=pixels,pngSha256=hashlib.sha256(raw).hexdigest(),
                xmlSha256=hashlib.sha256(xml.encode()).hexdigest(),unchangedActivityAndBounds=True)
    return raw,xml,last


@contextmanager
def rotation_challenge(adb, package=TEST_PACKAGE):
    if package != TEST_PACKAGE:
        raise ValueError('Rotation calibration requires the disposable integration package.')
    saved={k:adb('shell','settings','get','system',k).strip() for k in ('user_rotation','accelerometer_rotation')}
    command=wm_command(adb)
    previous_wm=previous_mode(saved)
    try:
        adb('shell','am','start','-W','-n',package+'/'+CONTROL)
        request(adb,0)
        upright=observe(adb,package,0,control=True)
        request(adb,1)
        sideways=observe(adb,package,1,control=True)
        result=dict(controlPortrait=upright,controlLandscape=sideways)
        verify_challenge(result,package)
        yield result
    finally:
        adb('shell','wm',command,*previous_wm)
        for key,value in saved.items():
            if value=='null':adb('shell','settings','delete','system',key)
            else:adb('shell','settings','put','system',key,value)
