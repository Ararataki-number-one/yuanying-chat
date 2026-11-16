"""Current Chromium native-layout parser controls; no Android execution claims."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import capture_browser_workspace as capture


def node(parent, kind, bounds, *, text='', description='', enabled=True, clickable=False, long_clickable=False):
    return ET.SubElement(parent,'node',{'class':'android.widget.'+kind,'package':capture.PACKAGE,
        'bounds':'[%s,%s][%s,%s]' % tuple(bounds),'text':text,'content-desc':description,
        'enabled':str(enabled).lower(),'clickable':str(clickable).lower(),
        'long-clickable':str(long_clickable).lower(),'visible-to-user':'true'})


def layout(width=1236, large=False, omit_empty_slot=False):
    tree=ET.Element('hierarchy');root=node(tree,'LinearLayout',[0,0,width,2600])
    identity=node(root,'FrameLayout',[0,0,width,170])
    node(identity,'Button',[(width-720)//2,6,(width+720)//2,162],text=capture.NAME,
         description=capture.ENVIRONMENT,clickable=True,long_clickable=True)
    node(root,'TextView',[0,176,width,300],text=capture.WAITING)
    if not omit_empty_slot:node(root,'FrameLayout',[0,300,width,2400])
    bar=node(root,'ViewGroup',[0,2400,width,2600])
    top=2424;address_top=top-9 if large else top;address_bottom=top+153 if large else top+144
    rectangles=([12,top,156,top+144],[156,top,300,top+144],[312,address_top,width-312,address_bottom],
                [width-300,top,width-156,top+144],[width-156,top,width-12,top+144])
    for index,(description,rectangle) in enumerate(zip(capture.BOTTOM_CONTROLS,rectangles)):
        node(bar,'EditText' if index==2 else 'Button',rectangle,
             text=capture.URL if index==2 else '',description=description,enabled=index!=0,clickable=True)
    return tree


def xml(tree):return ET.tostring(tree,encoding='unicode')


class ChromiumBrowserCaptureContractTests(unittest.TestCase):
    def setUp(self):capture.shared.set_display(1236,2676,480)

    def test_current_five_controls_and_top_capsule_at_both_original_sizes(self):
        for width,large in ((1236,False),(960,True)):
            capture.shared.set_display(width,2676,480)
            observed=capture.browser_geometry(xml(layout(width,large)),3)
            self.assertEqual(observed['navigationContract'],3)
            self.assertEqual([r['description'] for r in observed['controls']],list(capture.BOTTOM_CONTROLS))
            self.assertTrue(observed['addressAtBottom'] and observed['topAddressAbsent'] and observed['environmentCapsuleRetained'])
            self.assertGreater(observed['addressBounds'][1],observed['contentBounds'][1])
            self.assertEqual(observed['controls'][0]['enabled'],'false')

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
        for description,rectangle in (('后退','[12,2424][150,2568]'),
                                      ('打开当前环境主页','[140,2424][284,2568]'),
                                      ('网址或搜索词','[312,2424][500,2568]'),
                                      ('浏览器菜单','[780,2424][924,2568]')):
            tree=layout();next(n for n in tree.iter('node') if n.get('content-desc')==description).set('bounds',rectangle)
            with self.subTest(description=description),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_capsule_requires_center_complete_name_and_long_press(self):
        for key,value in (('text','truncated'),('long-clickable','false'),('enabled','false'),('bounds','[240,6][960,162]')):
            tree=layout();next(n for n in tree.iter('node') if n.get('content-desc')==capture.ENVIRONMENT).set(key,value)
            with self.subTest(key=key),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)

    def test_url_duplicate_or_content_overlap_cannot_pass(self):
        for kind in ('wrong-url','duplicate','content'):
            tree=layout();address=next(n for n in tree.iter('node') if n.get('content-desc')=='网址或搜索词')
            if kind=='wrong-url':address.set('text','https://other.example')
            elif kind=='duplicate':tree[0].append(ET.fromstring(ET.tostring(address)))
            else:
                next(n for n in tree[0] if n.get('class')=='android.widget.FrameLayout' and n.get('bounds')=='[0,300][1236,2400]').set('bounds','[0,300][1236,2450]')
            with self.subTest(kind=kind),self.assertRaises(ValueError):capture.browser_geometry(xml(tree),3)


if __name__=='__main__':unittest.main(verbosity=2)
