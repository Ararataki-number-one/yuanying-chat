"""Current Chromium native-layout parser controls; no Android execution claims."""
from pathlib import Path
import ast
import copy
import hashlib
import inspect
import json
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import capture_browser_workspace as capture

ORIGINAL = ROOT/'tests/browser-workspace-capture/c1-api32-initial-browser.xml'


def node(parent, kind, bounds, *, text='', description='', enabled=True, clickable=False, long_clickable=False):
    return ET.SubElement(parent,'node',{'class':'android.widget.'+kind,'package':capture.PACKAGE,
        'bounds':'[%s,%s][%s,%s]' % tuple(bounds),'text':text,'content-desc':description,
        'enabled':str(enabled).lower(),'clickable':str(clickable).lower(),
        'long-clickable':str(long_clickable).lower(),'visible-to-user':'true'})


def layout(width=1236, large=False, omit_empty_slot=False):
    tree=ET.Element('hierarchy');root=node(tree,'LinearLayout',[0,0,width,2600])
    identity=node(root,'FrameLayout',[0,0,width,170])
    node(identity,'Button',[(width-720)//2,6,(width+720)//2,162],text=capture.NAME,
         description=capture.ENVIRONMENT,clickable=True,long_clickable=False)
    network=node(root,'LinearLayout',[0,170,width,316])
    node(network,'Button',[48,170,width-48,314],text='●  '+capture.NETWORK_SUMMARY,
         description=capture.NETWORK,clickable=True)
    node(root,'TextView',[0,320,width,444],text=capture.WAITING)
    if not omit_empty_slot:node(root,'FrameLayout',[0,444,width,2400])
    bar=node(root,'ViewGroup',[0,2400,width,2600])
    top=2424;address_top=top-9 if large else top;address_bottom=top+153 if large else top+144
    rectangles=([12,top,156,top+144],[156,top,300,top+144],[312,address_top,width-312,address_bottom],
                [width-300,top,width-156,top+144],[width-156,top,width-12,top+144])
    for index,(description,rectangle) in enumerate(zip(capture.BOTTOM_CONTROLS,rectangles)):
        node(bar,'EditText' if index==2 else 'Button',rectangle,
             text=capture.URL if index==2 else '',description=description,clickable=True)
    return tree


def xml(tree):return ET.tostring(tree,encoding='unicode')


def compact_layout(width=1236, large=False):
    tree=layout(width,large)
    if not large:
        network=next(n for n in tree.iter('node') if n.get('content-desc')==capture.NETWORK)
        network.set('bounds',f'[48,170][{width-48},254]')
        parent=next(n for n in tree.iter('node') if network in list(n))
        parent.set('bounds',f'[0,170][{width},256]')
    return tree


def native_header(tree, scale=1.0):
    """Synthetic native-reader inputs only; never emitted as device evidence."""
    nodes=list(tree.iter('node'));root=nodes[0];width=capture.shared.bounds(root)[2]
    capsule=list(capture.shared.bounds(next(n for n in nodes if n.get('content-desc')==capture.ENVIRONMENT)))
    network=list(capture.shared.bounds(next(n for n in nodes if n.get('content-desc')==capture.NETWORK)))
    touch=[network[0],network[3]-144,network[2],network[3]]
    if touch[1]<capsule[3]:
        regions=[[touch[0],touch[1],capsule[0],capsule[3]],
                 [capsule[2],touch[1],touch[2],capsule[3]],
                 [touch[0],capsule[3],touch[2],touch[3]]]
    else:regions=[touch.copy()]
    return dict(schema=1,headerContract=5,status='observed',scene='chat',nonce='9'*32,
                sourceCommit='8'*40,actualAndroidLayout=True,engine='chromium',fontScale=scale,density=3,
                windowBounds=[0,0,width,2676],activityClass='local.pocketchat.BrowserActivity',
                activityIdentity=123,delegateIdentity=456,windowFocused=True,layoutRequested=False,
                capsuleAccessibilityBounds=capsule,startedUptimeMs=100,observedUptimeMs=2000,
                layout=dict(headerContract=5,actualAndroidLayout=True,density=3,viewportDp=width/3,
                            toolbar=[0,0,width,network[3]+2],topBounds=[0,0,width,170],
                            webBounds=[0,444,width,2400],networkInHeader=True,networkShown=True,
                            controls=[dict(name='environment',touch=capsule,visible=capsule)],
                            networkMetrics=dict(bounds=network,touchBounds=touch,effectiveTouchRegions=regions,
                                                clickable=True,focusable=True)))


class ChromiumBrowserCaptureContractTests(unittest.TestCase):
    def setUp(self):capture.shared.set_display(1236,2676,480)

    def test_current_five_controls_and_top_capsule_at_both_original_sizes(self):
        for width,large in ((1236,False),(960,True)):
            capture.shared.set_display(width,2676,480)
            observed=capture.browser_geometry(xml(layout(width,large)),3)
            self.assertEqual(observed['navigationContract'],4)
            self.assertEqual([r['description'] for r in observed['controls']],list(capture.BOTTOM_CONTROLS))
            self.assertTrue(observed['addressAtBottom'] and observed['topAddressAbsent'] and observed['environmentCapsuleRetained'])
            self.assertTrue(observed['unverifiedNetworkStateObserved'])
            self.assertGreaterEqual(observed['networkBounds'][1], observed['environmentBounds'][3])
            self.assertLessEqual(observed['networkBounds'][3], observed['contentBounds'][1])
            self.assertGreater(observed['addressBounds'][1],observed['contentBounds'][1])
            self.assertTrue(all(value['enabled']=='true' for value in observed['controls']))

    def test_empty_content_slot_absence_retains_existing_accessibility_limit(self):
        observed=capture.browser_geometry(xml(layout(omit_empty_slot=True)),3)
        self.assertFalse(observed['contentSlotObserved'])
        self.assertIsNone(observed['contentBounds'])

    def test_top_address_old_caption_and_management_dock_cannot_pass(self):
        for kind in ('top-address','old-caption','dock'):
            tree=layout();nodes=list(tree.iter('node'))
            if kind=='top-address':next(n for n in nodes if n.get('content-desc')=='网址或搜索词').set('bounds','[312,180][924,324]')
            elif kind=='old-caption':node(nodes[0],'TextView',[0,180,900,240],text='Chromium · HTTP · 不安全')
            else:node(nodes[0],'Button',[0,2200,150,2350],text='环境',clickable=True)
            with self.subTest(kind=kind),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_overlap_wrong_order_small_target_or_clipped_address_cannot_pass(self):
        for description,rectangle in (('打开当前环境主页','[12,2424][150,2568]'),
                                      ('网页窗口','[140,2424][284,2568]'),
                                      ('网址或搜索词','[312,2424][500,2568]'),
                                      ('浏览器菜单','[780,2424][924,2568]')):
            tree=layout();next(n for n in tree.iter('node') if n.get('content-desc')==description).set('bounds',rectangle)
            with self.subTest(description=description),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_capsule_requires_center_complete_name_and_tap_only(self):
        for key,value in (('text','truncated'),('long-clickable','true'),('enabled','false'),('bounds','[240,6][960,162]')):
            tree=layout();next(n for n in tree.iter('node') if n.get('content-desc')==capture.ENVIRONMENT).set(key,value)
            with self.subTest(key=key),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_network_header_requires_own_unconfigured_state_and_separate_touch_region(self):
        for key,value in (('text','●  127.0.0.1 · 20 ms · 已连接'), ('enabled','false'),
                          ('bounds','[48,150][1188,294]'), ('bounds','[48,300][1188,444]'),
                          ('bounds','[48,170][1188,310]'), ('class','android.widget.TextView')):
            tree=layout();next(n for n in tree.iter('node') if n.get('content-desc')==capture.NETWORK).set(key,value)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_url_duplicate_or_content_overlap_cannot_pass(self):
        for kind in ('wrong-url','duplicate','content'):
            tree=layout();address=next(n for n in tree.iter('node') if n.get('content-desc')=='网址或搜索词')
            if kind=='wrong-url':address.set('text','https://other.example')
            elif kind=='duplicate':tree[0].append(ET.fromstring(ET.tostring(address)))
            else:
                next(n for n in tree[0] if n.get('class')=='android.widget.FrameLayout' and n.get('bounds')=='[0,444][1236,2400]').set('bounds','[0,444][1236,2450]')
            with self.subTest(kind=kind),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_original_failed_capture_has_one_capsule_action_and_two_visual_name_nodes(self):
        raw=ORIGINAL.read_bytes()
        provenance=json.loads(ORIGINAL.with_suffix('.json').read_text())
        self.assertEqual(provenance['status'],'failed')
        self.assertEqual(provenance['sourceCommit'],'9f05ea4ce48d4ccae482b6fcdecb637d3b60cce2')
        self.assertEqual(provenance['sourceTree'],'fd22328ce911a6fc73c7fe95d136da53a824e761')
        self.assertEqual(provenance['runId'],44010184393)
        self.assertEqual(provenance['runAttempt'],1)
        self.assertEqual(provenance['xmlBytes'],len(raw))
        self.assertEqual(provenance['xmlSha256'],hashlib.sha256(raw).hexdigest())
        value=raw.decode('utf-8')
        matches=capture.shared.nodes(value,lambda n:n.get('text')==capture.NAME)
        self.assertEqual([n.get('class') for n in matches],['android.widget.Button','android.widget.TextView'])
        self.assertFalse(len(matches)==1)  # The exact retired readiness condition.
        self.assertTrue(capture.environment_ready(value,3))
        self.assertEqual(capture.browser_geometry(value,3)['navigationContract'],4)

    def test_real_initial_wait_uses_the_capsule_action_without_changing_other_requirements(self):
        # Execute the actual producer's pure local predicate, including present().
        tree=ast.parse(inspect.getsource(capture.main))
        present=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='present')
        call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                  and n.func.id=='wait_for' and len(n.args)>1 and isinstance(n.args[1],ast.BinOp)
                  and isinstance(n.args[1].right,ast.Constant) and n.args[1].right.value=='-browser')
        namespace=dict(capture.__dict__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[present],type_ignores=[])),str(capture.__file__),'exec'),namespace)
        predicate=eval(compile(ast.Expression(body=call.args[0]),str(capture.__file__),'eval'),namespace)
        value=ORIGINAL.read_text()
        self.assertTrue(predicate(value))
        for kind in ('missing-notice','missing-network','missing-capsule'):
            root=ET.fromstring(value)
            for n in root.iter('node'):
                if kind=='missing-notice' and n.get('text')==capture.WAITING:n.set('text','')
                if kind=='missing-network' and n.get('content-desc')==capture.NETWORK:n.set('content-desc','')
                if kind=='missing-capsule' and n.get('content-desc')==capture.ENVIRONMENT:n.set('content-desc','')
            with self.subTest(kind=kind):self.assertFalse(predicate(xml(root)))

    def test_capsule_readiness_rejects_duplicate_foreign_disabled_hidden_or_short_action(self):
        for kind in ('duplicate','foreign','disabled','unclickable','hidden','wrong-name','wrong-description',
                     'text-only','long-click','short-width','short-height','outside-display'):
            tree=ET.fromstring(ORIGINAL.read_bytes())
            action=next(n for n in tree.iter('node') if n.get('content-desc')==capture.ENVIRONMENT)
            if kind=='duplicate':tree.append(ET.fromstring(ET.tostring(action)))
            else:
                key,value={
                    'foreign':('package','foreign.package'), 'disabled':('enabled','false'),
                    'unclickable':('clickable','false'), 'hidden':('visible-to-user','false'),
                    'wrong-name':('text','truncated'), 'wrong-description':('content-desc','当前环境'),
                    'text-only':('class','android.widget.TextView'), 'long-click':('long-clickable','true'),
                    'short-width':('bounds','[330,72][473,216]'), 'short-height':('bounds','[330,72][906,215]'),
                    'outside-display':('bounds','[330,2533][906,2677]'),
                }[kind]
                action.set(key,value)
            with self.subTest(kind=kind):self.assertFalse(capture.environment_ready(xml(tree),3))


class ChromiumNativeHeaderCaptureTests(unittest.TestCase):
    def setUp(self):capture.shared.set_display(1236,2676,480)

    def test_compact_row_requires_native_proof_and_keeps_original_bottom_rules(self):
        tree=compact_layout();native=json.loads(json.dumps(native_header(tree)))
        with self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)
        observed=capture.browser_geometry(xml(tree),3,native)
        self.assertEqual(observed['headerContract'],5)
        self.assertEqual(observed['navigationContract'],4)
        self.assertEqual(observed['networkBounds'][3]-observed['networkBounds'][1],84)
        self.assertEqual(observed['networkTouchBounds'][3]-observed['networkTouchBounds'][1],144)
        target=capture.network_extension(native['layout']);point=target['point']
        self.assertLess(point[1],observed['networkBounds'][1])
        self.assertGreaterEqual(target['bounds'][2]-target['bounds'][0],144)
        self.assertGreaterEqual(target['bounds'][3]-target['bounds'][1],144)
        for key,value in (('bounds','[12,2424][150,2568]'),('enabled','false')):
            altered=copy.deepcopy(tree)
            next(n for n in altered.iter('node') if n.get('content-desc')==capture.BOTTOM_CONTROLS[0]).set(key,value)
            with self.subTest(key=key),self.assertRaises(ValueError):capture.browser_geometry(xml(altered),3,native)

    def test_large_font_keeps_full_visible_target_and_all_original_geometry(self):
        capture.shared.set_display(960,2676,480)
        tree=compact_layout(960,True);native=native_header(tree,2)
        observed=capture.browser_geometry(xml(tree),3,native)
        self.assertEqual(observed['headerContract'],5)
        self.assertEqual(list(observed['networkBounds']),observed['networkTouchBounds'])
        self.assertEqual(len(observed['controls']),5)

    def test_native_geometry_cannot_shrink_overlap_capsule_or_disagree_with_xml(self):
        tree=compact_layout();original=native_header(tree)
        for kind in ('short-touch','stolen-capsule','different-visible','different-capsule','different-content','wrong-density','wrong-engine','wrong-activity'):
            value=copy.deepcopy(original);layout=value['layout'];network=layout['networkMetrics']
            if kind=='short-touch':network['touchBounds'][1]+=1
            if kind=='stolen-capsule':network['effectiveTouchRegions']=[network['touchBounds'].copy()]
            if kind=='different-visible':network['bounds'][0]+=1;network['touchBounds'][0]+=1;network['effectiveTouchRegions'][0][0]+=1;network['effectiveTouchRegions'][2][0]+=1
            if kind=='different-capsule':value['capsuleAccessibilityBounds'][0]+=1
            if kind=='different-content':layout['webBounds'][1]+=1
            if kind=='wrong-density':value['density']=2
            if kind=='wrong-engine':value['engine']='gecko'
            if kind=='wrong-activity':value['activityClass']='local.pocketchat.MainActivity'
            with self.subTest(kind=kind),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3,value)

    def test_packet_requires_one_current_owned_native_chromium_observation(self):
        value=native_header(compact_layout());raw=json.dumps(value)
        self.assertEqual(capture.header_packet('I/PocketBrowserHeader: '+raw,'9'*32,'8'*40),(raw,value))
        self.assertIsNone(capture.header_packet(raw,'a'*32,'8'*40))
        with self.assertRaises(ValueError):capture.header_packet(raw+'\n'+raw,'9'*32,'8'*40)
        duplicate=raw[:-1]+',"nonce":"'+('9'*32)+'"}'
        with self.assertRaises(ValueError):capture.header_packet(duplicate,'9'*32,'8'*40)
        for key,replacement in (('sourceCommit','a'*40),('status','failed'),('engine','gecko'),
                                ('activityClass','local.pocketchat.MainActivity'),('delegateIdentity',0),
                                ('windowFocused',False),('layoutRequested',True)):
            changed=copy.deepcopy(value);changed[key]=replacement
            with self.subTest(key=key),self.assertRaises((AssertionError,ValueError)):
                capture.header_packet(json.dumps(changed),'9'*32,'8'*40)

    def test_current_producer_uses_owned_bridge_and_native_proof_for_every_geometry(self):
        tree=ast.parse(inspect.getsource(capture.main));calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        geometry=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='browser_geometry']
        self.assertEqual(len(geometry),6)
        self.assertTrue(all(len(n.args)==3 and isinstance(n.args[2],ast.Name) and n.args[2].id=='native_header' for n in geometry))
        raw=inspect.getsource(capture.main)
        self.assertIn("'visualAction', 'browser-header', '--es', 'visualHeaderNonce', nonce",raw)
        self.assertIn('browser_deadline = time.monotonic()+35',raw)
        self.assertIn('observe_header(nonce, source, browser_deadline)',raw)
        self.assertIn('deadline=browser_deadline',raw)
        self.assertIn('actualNativeNetworkTargetRoundtrip=True',raw)
        self.assertIn("adb('shell', 'input', 'tap', *map(str, point))",raw)
        self.assertIn('nativeNetworkTapOutsideVisibleRow=outside',raw)


if __name__=='__main__':unittest.main(verbosity=2)
