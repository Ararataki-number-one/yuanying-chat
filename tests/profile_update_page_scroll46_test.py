"""Synthetic XML/ADB-call controls for the actual update-page scrolling driver.

These cases do not run Android; the next independent files CI must run it.
"""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('update_scroll46_controls', ROOT/'tests/gecko/update_page_scroll.py')
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)
PACKAGE = 'local.pocketchat.test'


def xml(labels, package=PACKAGE):
    root = ET.Element('hierarchy')
    ET.SubElement(root, 'node', {'package':package, 'class':'android.widget.TextView', 'text':'应用更新', 'bounds':'[100,20][900,100]'})
    scroll = ET.SubElement(root, 'node', {'package':package, 'class':'android.widget.ScrollView', 'scrollable':'true', 'bounds':'[0,150][1000,1600]'})
    for index,label in enumerate(labels):
        kind = 'android.widget.TextView' if label == '当前安装版本' else 'android.widget.Switch' if label in DRIVER.LABELS[-2:] else 'android.widget.Button'
        text = label+' 2.0.46' if label == '当前安装版本' else label
        ET.SubElement(scroll, 'node', {'package':package, 'class':kind, 'text':text, 'enabled':'true', 'clickable':'true', 'bounds':f'[50,{200+index*140}][950,{300+index*140}]'})
    return ET.tostring(root, encoding='unicode')


class FakeAdb:
    def __init__(self, snapshots):
        self.snapshots=list(snapshots);self.calls=[];self.last=None
    def __call__(self,*parts):
        self.calls.append(parts)
        if parts == ('shell','cat','/sdcard/update-ui-scroll.xml'):
            if self.snapshots:self.last=self.snapshots.pop(0)
            if isinstance(self.last,Exception):raise self.last
            if self.last is None:raise AssertionError('No synthetic Android snapshot')
            return self.last
        if parts == ('shell','uiautomator','dump','/sdcard/update-ui-scroll.xml'):return 'UI hierarchy dumped'
        if parts[:3] == ('shell','input','swipe'):return ''
        raise AssertionError(('Unexpected Android operation', parts))


class UpdatePageScroll46Controls(unittest.TestCase):
    def scan(self,first,later):
        adb=FakeAdb(later);saved={}
        current,report=DRIVER.scan_update_controls(adb,first,lambda name,raw:saved.setdefault(name,raw),PACKAGE)
        return current,report,adb,saved

    def test_original_six_controls_and_actual_installer_visibility_across_scrolls(self):
        first=xml(DRIVER.LABELS[1:4]);settings=xml(DRIVER.LABELS[-2:])
        current,report,adb,saved=self.scan(first,[settings,first])
        self.assertEqual(report['labelsSeen'],list(DRIVER.LABELS))
        self.assertEqual(current,first)
        self.assertEqual([row['direction'] for row in report['gestures']],['down','up'])
        self.assertEqual(len(report['snapshots']),3);self.assertEqual(len(saved),3)
        self.assertEqual(len(adb.calls),6)
        self.assertFalse(any('tap' in row for row in adb.calls))
        self.assertEqual(report['gestures'][0],dict(direction='down',x=500,fromY=1310,toY=440,duration=400))
        self.assertEqual(report['gestures'][1],dict(direction='up',x=500,fromY=440,toY=1310,duration=400))

    def test_short_page_does_not_need_gestures_or_extra_adb_reads(self):
        first=xml(DRIVER.LABELS[1:]).replace('scrollable="true"','scrollable="false"')
        current,report,adb,saved=self.scan(first,[])
        self.assertEqual(current,first);self.assertEqual(adb.calls,[])
        self.assertEqual(report['gestures'],[]);self.assertEqual(len(saved),1)

    def test_missing_original_setting_is_not_waived_at_bound(self):
        first=xml(DRIVER.LABELS[1:-1]);adb=FakeAdb([first])
        with self.assertRaisesRegex(AssertionError,'absent after bounded actual scrolling'):
            DRIVER.scan_update_controls(adb,first,lambda *unused:None,PACKAGE)
        self.assertEqual(sum(row[:3]==('shell','input','swipe') for row in adb.calls),6)

    def test_installer_must_be_visible_again_before_old_installer_tap(self):
        first=xml(DRIVER.LABELS[1:4]);settings=xml(DRIVER.LABELS[-2:]);adb=FakeAdb([settings])
        with self.assertRaisesRegex(AssertionError,'installer button is not visible'):
            DRIVER.scan_update_controls(adb,first,lambda *unused:None,PACKAGE)
        self.assertEqual(sum(row[:3]==('shell','input','swipe') for row in adb.calls),7)

    def test_wrong_page_or_package_cannot_supply_original_controls(self):
        for first in [xml(DRIVER.LABELS[1:],package='other.browser'),xml(DRIVER.LABELS[1:]).replace('应用更新','设置')]:
            with self.subTest(first=first),self.assertRaisesRegex(AssertionError,'actual production update page'):
                self.scan(first,[])

    def test_offscreen_controls_do_not_count(self):
        first=xml(DRIVER.LABELS[1:]);root=ET.fromstring(first)
        target=next(node for node in root.iter('node') if node.get('text')==DRIVER.LABELS[-1]);target.set('bounds','[50,1700][950,1800]')
        changed=ET.tostring(root,encoding='unicode')
        with self.assertRaisesRegex(AssertionError,'absent after bounded actual scrolling'):
            self.scan(changed,[changed])

    def test_disabled_nonbutton_and_invalid_bounds_fail_instead_of_inventing_controls(self):
        first=xml(DRIVER.LABELS[1:])
        for key,value,error in [('class','android.widget.TextView','actual Android update button'),('bounds','[50,200][50,200]','Empty actual Android bounds')]:
            root=ET.fromstring(first);target=next(node for node in root.iter('node') if node.get('text')=='安装更新');target.set(key,value)
            with self.subTest(key=key),self.assertRaisesRegex(AssertionError,error):self.scan(ET.tostring(root,encoding='unicode'),[])
        root=ET.fromstring(first);target=next(node for node in root.iter('node') if node.get('text')=='安装更新');target.set('enabled','false');changed=ET.tostring(root,encoding='unicode')
        with self.assertRaisesRegex(AssertionError,'absent after bounded actual scrolling'):self.scan(changed,[changed])

    def test_adb_failure_is_not_replaced_by_prior_snapshot(self):
        with self.assertRaisesRegex(OSError,'controlled adb read failed'):
            self.scan(xml(DRIVER.LABELS[1:4]),[OSError('controlled adb read failed')])

    def test_prior_disabled_offscreen_or_foreign_duplicate_cannot_redirect_original_next_tap(self):
        for attributes in [dict(enabled='false'),dict(bounds='[50,1700][950,1800]'),dict(package='other.browser')]:
            root=ET.fromstring(xml(DRIVER.LABELS[1:]))
            scroll=next(node for node in root.iter('node') if node.get('class')=='android.widget.ScrollView')
            duplicate=ET.Element('node',dict(package=PACKAGE,**{'class':'android.widget.Button','text':'安装更新','enabled':'true','clickable':'true','bounds':'[50,200][950,300]'}))
            duplicate.attrib.update(attributes);scroll.insert(0,duplicate)
            with self.subTest(attributes=attributes),self.assertRaisesRegex(AssertionError,'unique actual installer target'):
                self.scan(ET.tostring(root,encoding='unicode'),[])

    def test_stage_snapshots_all_have_exact_byte_hashes(self):
        import hashlib
        first=xml(DRIVER.LABELS[1:4]);settings=xml(DRIVER.LABELS[-2:])
        unused,report,adb,saved=self.scan(first,[settings,first])
        for snapshot in report['snapshots']:
            self.assertEqual(snapshot['sha256'],hashlib.sha256(saved[snapshot['file']].encode()).hexdigest())
        self.assertEqual(report['maxSwipesPerDirection'],6)


if __name__=='__main__':unittest.main(verbosity=2)
