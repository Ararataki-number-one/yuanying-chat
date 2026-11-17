"""Selector/geometry and signature parsing checks; not Android execution evidence."""
import importlib.util
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
SPEC=importlib.util.spec_from_file_location('glass_capture',ROOT/'tools/gecko/capture_glass_navigation.py')
CAPTURE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CAPTURE)


def hierarchy(labels,boxes,selected=None):
    root=ET.Element('hierarchy')
    for label,box in zip(labels,boxes):
        ET.SubElement(root,'node',{'package':'local.pocketchat.test','text':label,
            'content-desc':label,'class':'android.widget.Button','clickable':'true','enabled':'true',
            'selected':str(label==selected).lower(),'visible-to-user':'true',
            'bounds':'[{},{}][{},{}]'.format(*box)})
    return root


def xml(root):return ET.tostring(root,encoding='unicode')


class ActualDisplayViewportTest(unittest.TestCase):
    # Exact relevant default-display lines retained from b389db2 run 43130666820.
    api32 = ('  Display: mDisplayId=0 rootTasks=5\n'
             '    init=1236x2676 480dpi base=2472x1236 480dpi '
             'cur=2472x1236 app=2472x1236 rng=1236x1164-2472x2400\n')
    api35 = ('  Display: mDisplayId=0 (organized)\n'
             '    init=1236x2676 480dpi mMinSizeOfResizeableTaskDp=220 '
             'base=2676x1236 480dpi cur=2676x1236 app=2676x1236 '
             'rng=1236x1236-2676x2676\n')

    def setUp(self):
        self.display = CAPTURE.WIDTH, CAPTURE.HEIGHT, CAPTURE.DENSITY
        self.request = CAPTURE.DISPLAY_REQUEST

    def tearDown(self):
        CAPTURE.set_display(*self.display, requested=self.request)

    def test_retained_api32_and_api35_window_observations_keep_actual_widths(self):
        for raw, width in ((self.api32, 2472), (self.api35, 2676)):
            with self.subTest(width=width):
                self.assertEqual(CAPTURE.window_display_viewport(raw),
                    dict(widthPx=width, heightPx=1236, densityDpi=480))

    def test_current_viewport_is_not_inferred_from_base_override_or_app_insets(self):
        raw = self.api35.replace('base=2676x1236 480dpi', 'base=2676x1236 320dpi')
        raw = raw.replace('cur=2676x1236', 'cur=1236x2676').replace('app=2676x1236', 'app=1236x2532')
        self.assertEqual(CAPTURE.window_display_viewport(raw),
            dict(widthPx=1236, heightPx=2676, densityDpi=320))

    def test_initial_density_is_used_only_when_no_base_override_exists(self):
        raw = self.api32.replace('base=2472x1236 480dpi ', '')
        self.assertEqual(CAPTURE.window_display_viewport(raw),
            dict(widthPx=2472, heightPx=1236, densityDpi=480))

    def test_other_displays_cannot_supply_default_viewport_or_density(self):
        other = self.api35.replace('mDisplayId=0', 'mDisplayId=2')
        self.assertEqual(CAPTURE.window_display_viewport(other + self.api32 + other),
            dict(widthPx=2472, heightPx=1236, densityDpi=480))

    def test_missing_duplicate_or_malformed_display_observations_fail_closed(self):
        for raw in ('', self.api32.replace('mDisplayId=0', 'mDisplayId=1'), self.api32 * 2,
                    self.api32 + self.api32.split('\n', 1)[1],
                    self.api32.replace('cur=2472x1236', ''),
                    self.api32.replace('cur=2472x1236', 'cur=2472x1236 cur=2472x1236'),
                    self.api32.replace('cur=2472x1236', 'cur=-2472x1236'),
                    self.api32.replace('cur=2472x1236', 'cur=0x1236'),
                    self.api32.replace('base=2472x1236 480dpi', 'base=2472x1236 unknown'),
                    self.api32.replace('base=2472x1236 480dpi', 'base=2472x1236 0dpi'),
                    self.api32.replace('base=2472x1236 480dpi',
                                       'base=2472x1236 480dpi base=2472x1236 480dpi'),
                    self.api32.replace('init=1236x2676 480dpi', 'init=1236x2676 unknown')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                CAPTURE.window_display_viewport(raw)

    def test_clamped_viewport_binds_geometry_but_cannot_pass_requested_landscape(self):
        CAPTURE.set_display(2676, 1236, 480)
        # Unchanged native touch bounds from the retained API32 landscape XML.
        retained = xml(hierarchy(CAPTURE.LABELS,
            [(909, 990, 1127, 1194), (1127, 990, 1345, 1194),
             (1345, 990, 1563, 1194), (2220, 984, 2436, 1200)]))
        self.assertEqual(CAPTURE.navigation_geometry(retained)['horizontalCenterOffsetPx'], -102)
        with tempfile.TemporaryDirectory() as directory:
            owner = {}
            adb = MagicMock(return_value=self.api32.encode())
            with self.assertRaisesRegex(ValueError, 'requested 2676x1236.*observed 2472x1236'):
                CAPTURE.observe_display_viewport(adb, directory, owner, 'landscape', 2676, 1236, 480)
            row = owner['displayViewport']
            self.assertEqual(row['status'], 'failed')
            self.assertFalse(row['matchesRequested'])
            self.assertEqual(row['requested']['widthPx'], 2676)
            self.assertEqual(row['actual']['widthPx'], 2472)
            original = (Path(directory) / row['file']).read_bytes()
            self.assertEqual(original, self.api32.encode())
            self.assertEqual(row['sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(CAPTURE.DISPLAY_REQUEST, (2676, 1236, 480))
            self.assertEqual((CAPTURE.WIDTH, CAPTURE.HEIGHT), (2472, 1236))
            self.assertEqual(CAPTURE.navigation_geometry(retained)['horizontalCenterOffsetPx'], 0)
            self.assertIsNotNone(CAPTURE.navigation(retained))
            adb.assert_called_once_with('shell', 'dumpsys', 'window', 'displays', timeout=10)

    def test_matching_actual_viewport_is_verified_and_missing_density_match_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = {}
            actual = CAPTURE.observe_display_viewport(MagicMock(return_value=self.api35.encode()),
                directory, owner, 'matching', 2676, 1236, 480)
            self.assertEqual(owner['displayViewport']['status'], 'verified')
            self.assertEqual(actual, owner['displayViewport']['requested'])
            with self.assertRaisesRegex(ValueError, 'at 320 dpi; observed.*at 480 dpi'):
                CAPTURE.observe_display_viewport(MagicMock(return_value=self.api35.encode()),
                    directory, owner, 'wrong-density', 2676, 1236, 320)
            self.assertEqual(owner['displayViewport']['status'], 'failed')

    def test_unreadable_or_unparseable_actual_viewport_never_falls_back_to_request(self):
        CAPTURE.set_display(1236, 2676, 480)
        for output in (OSError('display unavailable'), b'Physical size: 2676x1236\n', b'\xff'):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                owner = {}
                adb = MagicMock(side_effect=output) if isinstance(output, Exception) else MagicMock(return_value=output)
                with self.assertRaises((OSError, ValueError, UnicodeDecodeError)):
                    CAPTURE.observe_display_viewport(adb, directory, owner, 'missing', 2676, 1236, 480)
                row = owner['displayViewport']
                self.assertEqual(row['status'], 'failed')
                self.assertNotIn('actual', row)
                self.assertNotIn('matchesRequested', row)
                self.assertEqual((CAPTURE.WIDTH, CAPTURE.HEIGHT), (1236, 2676))
                if isinstance(output, bytes):
                    self.assertEqual((Path(directory) / row['file']).read_bytes(), output)


class IntegrationSigningCertificateTest(unittest.TestCase):
    certificate='e89c5ab997e20257d6399f7648e912e1af2124401f2bef324eae09d6d93f9080'
    # Exact successful build-tools 37 output retained by the failed capture.
    actual_output='''Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v3.2 scheme (APK Signature Scheme v3.2): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
V2 Signer: certificate DN: CN=SyntheticIntegration
V2 Signer: certificate SHA-256 digest: e89c5ab997e20257d6399f7648e912e1af2124401f2bef324eae09d6d93f9080
V2 Signer: certificate SHA-1 digest: 1cf1f33462a1bf1a9cf8298af23745e3aeaa8555
V2 Signer: certificate MD5 digest: 42ad4ada042029ec4d019f23a224a7e1
V2 Signer: key algorithm: RSA
V2 Signer: key size (bits): 2048
V2 Signer: public key SHA-256 digest: 63e8972ea33a91b7c2373cd2c41fde42ebe1e5e0b6b14a122195de69c59a7d4f
V2 Signer: public key SHA-1 digest: dcaa5c0a8496ec0788d1c8a43d8aff70849daaf3
V2 Signer: public key MD5 digest: 361365e880936160d62fe9f7092e4a41
'''

    def parse(self,output):
        return CAPTURE.integration_signing_certificate(output.encode())

    def test_actual_build_tools_37_output_uses_certificate_not_public_key(self):
        self.assertEqual(self.parse(self.actual_output),self.certificate)

    def test_legacy_single_signer_format_remains_supported(self):
        self.assertEqual(self.parse(self.actual_output.replace('V2 Signer:','Signer #1')),self.certificate)

    def test_requires_one_exact_single_signer_declaration(self):
        declared='Number of signers: 1\n'
        for replacement in ('','Number of signers: 2\n',declared*2,
                            declared+'Number of signers: 2\n','Number of signers: 01\n',
                            'Number of signers: unknown\n','number of signers: 1\n'):
            with self.subTest(declaration=replacement),self.assertRaises(ValueError):
                self.parse(self.actual_output.replace(declared,replacement))

    def test_missing_certificate_cannot_be_replaced_by_public_key_hash(self):
        line='V2 Signer: certificate SHA-256 digest: '+self.certificate+'\n'
        with self.assertRaises(ValueError):self.parse(self.actual_output.replace(line,''))

    def test_duplicate_certificate_lines_never_deduplicate(self):
        for prefix in ('V2 Signer:','Signer #1','Signer #2','V3 Signer:','Unknown signer:'):
            for value in (self.certificate,'a'*64,'invalid'):
                with self.subTest(prefix=prefix,digest=value),self.assertRaises(ValueError):
                    self.parse(self.actual_output+prefix+' certificate SHA-256 digest: '+value+'\n')

    def test_malformed_certificate_digests_fail_closed(self):
        for value in ('',self.certificate[:-1],self.certificate+'0',self.certificate.upper(),'g'*64,
                      self.certificate+' extra','0x'+self.certificate):
            with self.subTest(digest=value),self.assertRaises(ValueError):
                self.parse(self.actual_output.replace(self.certificate,value))

    def test_only_actual_v2_and_legacy_first_signer_prefixes_are_accepted(self):
        for prefix in ('Signer #2','Signer #01','Signer #1:','V2 Signer','V3 Signer:',
                       'Unknown signer:','Warning: V2 Signer:',' V2 Signer:'):
            with self.subTest(prefix=prefix),self.assertRaises(ValueError):
                self.parse(self.actual_output.replace('V2 Signer:',prefix))

    def test_malformed_second_certificate_line_is_not_ignored(self):
        for second in ('Unknown: Certificate SHA-256 digest: '+'b'*64,
                       'Unknown: certificate SHA256 digest: '+'b'*64,
                       'Unknown: certificate SHA-256 fingerprint: '+'b'*64):
            with self.subTest(second=second),self.assertRaises(ValueError):
                self.parse(self.actual_output+second+'\n')


class NavigationCaptureModesTest(unittest.TestCase):
    compact=((291,2358,509,2562),(509,2358,727,2562),(727,2358,945,2562),(984,2352,1200,2568))
    workspace=((51,2358,277,2562),(277,2358,504,2562),(504,2358,731,2562),(731,2358,958,2562),(958,2358,1185,2562))

    def test_chat_retains_centered_three_and_separate_reading(self):
        value=xml(hierarchy(CAPTURE.LABELS,self.compact))
        self.assertIsNotNone(CAPTURE.navigation(value))
        self.assertIsNone(CAPTURE.workspace_navigation_geometry(value))
        geometry=CAPTURE.observed_navigation_geometry(value)
        self.assertEqual(geometry['layout'],'conversation-split')
        self.assertEqual(geometry['horizontalCenterOffsetPx'],0)
        self.assertFalse(CAPTURE.selected_navigation(value,'网络'))

    def test_all_five_selected_destinations_use_workspace_geometry(self):
        for selected in CAPTURE.WORKSPACE_LABELS:
            with self.subTest(selected=selected):
                value=xml(hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,selected))
                self.assertIsNone(CAPTURE.navigation(value))
                self.assertTrue(CAPTURE.selected_navigation(value,selected))
                geometry=CAPTURE.observed_navigation_geometry(value)
                self.assertEqual(geometry['layout'],'workspace-five')
                self.assertEqual(geometry['leftToRightLabels'],list(CAPTURE.WORKSPACE_LABELS))
                self.assertEqual(geometry['horizontalCenterOffsetPx'],0)

    def test_old_selected_compact_bar_cannot_pass_as_native_workspace(self):
        for selected in ('环境','网络','下载'):
            value=xml(hierarchy(CAPTURE.LABELS,self.compact,selected))
            self.assertFalse(CAPTURE.selected_navigation(value,selected))

    def test_missing_duplicate_hidden_and_disabled_destinations_fail_closed(self):
        for broken in ('missing','duplicate','hidden','disabled'):
            with self.subTest(broken=broken):
                root=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
                node=root[0]
                if broken=='missing':root.remove(node)
                elif broken=='duplicate':ET.SubElement(root,'node',dict(node.attrib))
                elif broken=='hidden':node.set('visible-to-user','false')
                else:node.set('enabled','false')
                self.assertFalse(CAPTURE.selected_navigation(xml(root),'环境'))

    def test_wrong_order_misalignment_and_small_targets_fail_closed(self):
        variants=[]
        order=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        order[0].set('text','环境');order[1].set('text','会话');variants.append(order)
        off_center=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        off_center[0].set('bounds','[61,2358][277,2562]');variants.append(off_center)
        unequal=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        unequal[0].set('bounds','[51,2358][267,2562]');variants.append(unequal)
        too_short=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        too_short[0].set('bounds','[51,2358][277,2501]');variants.append(too_short)
        for root in variants:self.assertFalse(CAPTURE.selected_navigation(xml(root),'环境'))

    def test_hidden_chat_bar_does_not_confuse_visible_workspace(self):
        root=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'下载')
        for node in hierarchy(CAPTURE.LABELS,self.compact):
            node.set('visible-to-user','false');root.append(node)
        self.assertTrue(CAPTURE.selected_navigation(xml(root),'下载'))

    def test_two_visible_bars_are_ambiguous(self):
        root=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'网络')
        root.extend(hierarchy(CAPTURE.LABELS,self.compact))
        self.assertIsNone(CAPTURE.observed_navigation_geometry(xml(root)))
        self.assertFalse(CAPTURE.selected_navigation(xml(root),'网络'))


class CurrentBrowserToolsCaptureTest(unittest.TestCase):
    """Synthetic v4 sheets; original v3/C10 recording tests stay independent."""

    def setUp(self):
        self.display = CAPTURE.WIDTH, CAPTURE.HEIGHT, CAPTURE.DENSITY
        CAPTURE.set_display(1236, 2676, 480)

    def tearDown(self):
        CAPTURE.set_display(*self.display)

    def panel(self, *, title='网页工具', complete=True, target_height=144):
        root = ET.Element('hierarchy')

        def node(parent, kind, box, **attributes):
            values = {'package': CAPTURE.PACKAGE, 'class': 'android.widget.'+kind,
                      'visible-to-user': 'true', 'enabled': 'true',
                      'bounds': '[{},{}][{},{}]'.format(*box)}
            values.update(attributes)
            return ET.SubElement(parent, 'node', values)

        frame = node(root, 'FrameLayout', (0, 600, 1236, 2600))
        node(frame, 'TextView', (60, 630, 900, 750), text=title, **{'content-desc': title})
        node(frame, 'Button', (1008, 618, 1152, 762), clickable='true',
             **{'content-desc': '关闭'+title})
        scroll = node(frame, 'ScrollView', (60, 800, 1176, 2500), scrollable='true')
        if complete:
            node(scroll, 'Button', (84, 900, 1152, 900+target_height),
                 text='进入专注阅读', clickable='true')
        return xml(root)

    def test_tools_wait_for_owned_action_body_with_same_deadline_and_original_xml(self):
        incomplete, full = self.panel(complete=False), self.panel()
        with tempfile.TemporaryDirectory() as directory, patch.object(CAPTURE.time, 'monotonic', return_value=100):
            read, adb, inputs = MagicMock(return_value=full), MagicMock(), []
            capture = MagicMock(read=read)
            raw, target = CAPTURE.menu_action(capture, adb, incomplete, '进入专注阅读',
                directory, 'tools', 120, inputs, sheet='tools')
            self.assertEqual(raw, full)
            self.assertEqual(CAPTURE.bounds(target), (84, 900, 1152, 1044))
            read.assert_called_once_with(deadline=120)
            adb.assert_not_called()
            self.assertEqual(inputs, [])
            self.assertEqual((Path(directory)/'tools-menu-0.xml').read_text(), incomplete)
            self.assertEqual((Path(directory)/'tools-menu-1.xml').read_text(), full)

    def test_menu_and_tools_cannot_substitute_for_each_other(self):
        for title, sheet in (('浏览器菜单', 'tools'), ('网页工具', 'menu')):
            with self.subTest(title=title), tempfile.TemporaryDirectory() as directory, \
                    patch.object(CAPTURE.time, 'monotonic', return_value=100):
                transport, adb, inputs = MagicMock(), MagicMock(), []
                with self.assertRaises(ValueError):
                    CAPTURE.menu_action(transport, adb, self.panel(title=title), '进入专注阅读',
                        directory, 'wrong-sheet', 120, inputs, sheet=sheet)
                transport.read.assert_not_called()
                adb.assert_not_called()
                self.assertEqual(inputs, [])

    def test_tools_cannot_accept_small_target_after_the_original_twelve_scroll_limit(self):
        clipped, full = self.panel(target_height=100), self.panel()
        with tempfile.TemporaryDirectory() as directory, patch.object(CAPTURE.time, 'monotonic', return_value=100):
            read = MagicMock(side_effect=[clipped]*11+[full])
            adb, inputs = MagicMock(), []
            with self.assertRaisesRegex(ValueError, '12 observed scrolls'):
                CAPTURE.menu_action(MagicMock(read=read), adb, clipped, '进入专注阅读',
                    directory, 'clipped', 120, inputs, sheet='tools')
            self.assertEqual(read.call_count, 12)
            self.assertEqual(adb.call_count, 12)
            self.assertEqual(len(inputs), 12)
            self.assertTrue(all(call.kwargs == {'deadline': 120} for call in read.call_args_list))

    def test_capsule_has_only_current_native_tap_semantics(self):
        root = hierarchy(('日常会话',), ((330, 90, 906, 234),))
        root[0].set('content-desc', '当前环境：日常会话，点按切换环境')
        root[0].set('long-clickable', 'false')
        self.assertIsNotNone(CAPTURE.capsule(xml(root)))
        for key, value in (('long-clickable', 'true'), ('class', 'android.widget.TextView'),
                           ('content-desc', '当前环境：日常会话，点按输入网址，长按切换环境')):
            changed = ET.fromstring(xml(root))
            changed[0].set(key, value)
            with self.subTest(key=key):
                self.assertIsNone(CAPTURE.capsule(xml(changed)))


if __name__=='__main__':unittest.main()
