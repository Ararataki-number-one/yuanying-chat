"""Exact historical comparison for the portrait rotation additions only.

The device executes the current runner unchanged; this helper serves older source-oracle tests.
"""
from hashlib import sha256

BEFORE='6eabb43e4adc4d89ae3714f0e4c2dbb0f82debfb9b659bd1550c572c910034f6'
AFTER='6719b45daff6c1a4b90b500a930765a584523cfafb56ae497e7d773912b329a1'
EDITS=(("        assert not any(re.search(r'\\d+\\s*秒后进入',n.get('text','')) for n in tree(xml)),('countdown still "
  "visible',name)\n"
  "        assert dashboard(xml),('dashboard absent',name)\n"
  "        raw=binary('exec-out','screencap','-p');assert raw.startswith(b'\\x89PNG\\r\\n\\x1a\\n')\n"
  "        pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(name,'actual screenshot "
  "viewport differs',pixels,[width*3,height*3])\n"
  "        (directory/(name+'.xml')).write_text(xml);(directory/(name+'.png')).write_bytes(raw)\n"
  '        '
  "records.append(dict(name=name,image='ui-visuals/environment-dashboard/'+name+'.png',xml='ui-visuals/environment-dashboard/'+name+'.xml',imageSha256=hashlib.sha256(raw).hexdigest(),actualPixelSize=list(pixels),**metadata))\n"
  '    try:\n'
  '        for name,width,height,scale,night in '
  "[('light',360,640,1,False),('large-font',360,640,2,False),('landscape',640,360,1,False),('dark',360,640,1,True)]:\n"
  "            adb('shell','am','force-stop',PACKAGE);adb('logcat','-c')\n"
  "            adb('shell','cmd','uimode','night','yes' if night else 'no')\n"
  '            '
  "adb('shell','wm','size',f'{width*3}x{height*3}');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))\n"
  '            '
  "observed=dict(size=adb('shell','wm','size').strip(),density=adb('shell','wm','density').strip(),fontScale=adb('shell','settings','get','system','font_scale').strip())\n"
  "            assert float(observed['fontScale'])==scale,('Requested font scale not applied',observed)\n",
  "        assert not any(re.search(r'\\d+\\s*秒后进入',n.get('text','')) for n in tree(xml)),('countdown still "
  "visible',name)\n"
  "        assert dashboard(xml),('dashboard absent',name)\n"
  '        hold=None\n'
  "        if name.startswith(('portrait-held','portrait-390')):\n"
  '            raw,xml,hold=portrait_frame(adb,binary,dump,PACKAGE,width,height,480)\n'
  '            assert dashboard(xml)\n'
  "            if name.endswith('fingerprint'): assert 'User Agent' in xml\n"
  '            metadata.update(portraitHold=hold,rotationCalibration=calibration)\n'
  '        else:\n'
  "            raw=binary('exec-out','screencap','-p')\n"
  "        assert raw.startswith(bytes.fromhex('89504e470d0a1a0a'))\n"
  "        pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(name,'actual screenshot "
  "viewport differs',pixels,[width*3,height*3])\n"
  "        (directory/(name+'.xml')).write_text(xml);(directory/(name+'.png')).write_bytes(raw)\n"
  '        '
  "records.append(dict(name=name,image='ui-visuals/environment-dashboard/'+name+'.png',xml='ui-visuals/environment-dashboard/'+name+'.xml',imageSha256=hashlib.sha256(raw).hexdigest(),actualPixelSize=list(pixels),**metadata))\n"
  '    from contextlib import ExitStack\n'
  '    from portrait_orientation import rotation_challenge, portrait_frame\n'
  '    rotations=ExitStack()\n'
  '    try:\n'
  '        for name,width,height,scale,night in '
  "[('light',360,640,1,False),('large-font',360,640,2,False),('portrait-held',320,640,1,False),('portrait-390',390,640,1,False),('dark',360,640,1,True)]:\n"
  '            rotations.close()\n'
  "            adb('shell','am','force-stop',PACKAGE);adb('logcat','-c')\n"
  "            adb('shell','cmd','uimode','night','yes' if night else 'no')\n"
  '            '
  "adb('shell','wm','size',f'{width*3}x{height*3}');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))\n"
  "            if name in ('portrait-held','portrait-390'): "
  'calibration=rotations.enter_context(rotation_challenge(adb,PACKAGE))\n'
  '            '
  "observed=dict(size=adb('shell','wm','size').strip(),density=adb('shell','wm','density').strip(),fontScale=adb('shell','settings','get','system','font_scale').strip())\n"
  "            assert float(observed['fontScale'])==scale,('Requested font scale not applied',observed)\n"),
 ('        '
  "(out/'environment-dashboard-results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\\n');(directory/'results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\\n');raise\n"
  '    finally:\n'
  "        adb('shell','cmd','uimode','night','no');adb('shell','settings','put','system','font_scale','1')\n"
  '\n',
  '        '
  "(out/'environment-dashboard-results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\\n');(directory/'results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\\n');raise\n"
  '    finally:\n'
  '        rotations.close()\n'
  "        adb('shell','cmd','uimode','night','no');adb('shell','settings','put','system','font_scale','1')\n"
  '\n'))

def historical(source):
    assert sha256(source.encode()).hexdigest()==AFTER, 'Unreviewed dashboard runner'
    for old,new in reversed(EDITS):
        assert source.count(new)==1, 'Ambiguous portrait change'
        source=source.replace(new,old,1)
    assert sha256(source.encode()).hexdigest()==BEFORE, 'Historic dashboard differs'
    return source
