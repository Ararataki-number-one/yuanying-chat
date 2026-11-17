"""Current Chromium native-layout parser controls; no Android execution claims."""
from pathlib import Path
import ast
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


if __name__=='__main__':unittest.main(verbosity=2)
