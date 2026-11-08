"""Selector/geometry and signature parsing checks; not Android execution evidence."""
import importlib.util
from pathlib import Path
import sys
import unittest
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


if __name__=='__main__':unittest.main()
