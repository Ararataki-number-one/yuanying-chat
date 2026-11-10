"""Host-only parser and driver controls; never Android acceptance evidence.

Every hierarchy below is built from explicitly synthetic native classes,
geometry and action flags. No device capture, user label, CI identifier,
original capture digest or compressed artifact is embedded in this file.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests/gecko')]
import chrome_collapse_contract_v2 as reader
import run_chrome_collapse_v2 as runner
import gecko_chrome_collapse_v2_test as original_fixture

def host_xml():
    """Synthetic small-screen hierarchy with an editable short-path overlap."""
    tree=ET.Element('hierarchy',rotation='0')
    def node(parent,kind,rectangle,**extra):
        left,top,right,bottom=rectangle
        attrs={'class':kind,'package':reader.PACKAGE,'enabled':'true',
            'clickable':'false','long-clickable':'false','focusable':'false',
            'checkable':'false','bounds':f'[{left},{top}][{right},{bottom}]'}
        attrs.update(extra)
        return ET.SubElement(parent,'node',attrs)
    owner=node(tree,'android.widget.FrameLayout',(0,0,1080,1920))
    web=node(owner,'android.webkit.WebView',(0,477,1080,1194),focusable='true')
    node(web,'android.widget.EditText',(24,881,971,1115),
        **{'resource-id':'host-editor','clickable':'true','focusable':'true'})
    node(web,'android.widget.Button',(24,1123,150,1194),clickable='true',focusable='true')
    node(web,'android.widget.Button',(150,1123,267,1194),clickable='true',focusable='true')
    return ET.tostring(tree,encoding='unicode')


def before():
    return dict(command='horizontal', expanded=True, keyboard=False, windowFocus=True,
                page=0, addressDialog={'showing': False}, webX=0, webY=477, webWidth=1080, webHeight=717)


def identity():
    return dict(sourceCommit='a'*40, sourceTree='b'*40, apkSha256='c'*64)


def activity():
    return 'topResumedActivity=ActivityRecord{abc u0 '+reader.ACTIVITY+' t8}\n'


def output(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                text=raw[:8192].decode('utf-8', 'replace'), truncated=len(raw)>8192)


def capture_record(xml):
    """Declared fake host receipt with original UiVisualCapture field shapes."""
    remote = '/sdcard/pocketchat-ui-visual-'+'e'*32+'-7.xml'
    def command(parts, start, end, stdout):
        return dict(parts=parts, startedAtWallTimeMillis=start//1_000_000,
            completedAtWallTimeMillis=end//1_000_000, startedAtMonotonicNanos=start,
            completedAtMonotonicNanos=end, timeoutSeconds=(120_000_000_000-start)/1e9,
            exitCode=0, stdout=output(stdout), stderr=output(b''))
    raw=xml.encode()
    return dict(index=7, remotePath=remote, startedAtMonotonicNanos=101_000_000_000,
        completedAtMonotonicNanos=104_000_000_000, existingSceneDeadline=120.0,
        status='captured', xmlBytes=len(raw), xmlSha256=hashlib.sha256(raw).hexdigest(),
        commands=[command(['shell', 'uiautomator', 'dump', remote], 101_100_000_000,
                          103_000_000_000, ('UI hierchary dumped to: '+remote+'\n').encode()),
                  command(['shell', 'cat', remote], 103_100_000_000, 103_900_000_000, raw)])


def proof():
    xml=host_xml()
    return reader.make_short_target_proof(raw_xml=xml, activity_state=activity(), identity=identity(),
        nonce='d'*32, android_user=0, before=before(), capture_nonce='e'*32,
        capture_record=capture_record(xml), action_started_ns=100_000_000_000,
        activity_started_ns=105_000_000_000, activity_completed_ns=106_000_000_000,
        prepared_ns=107_000_000_000)


def verify(value):
    return reader.verify_short_target(value, identity=identity(), nonce='d'*32, android_user=0, before=before())


class ChromeShortTargetTests(unittest.TestCase):
    def test_synthetic_editor_overlap_selects_clear_12px_segment(self):
        xml=host_xml(); geometry=reader.short_target_geometry(xml, before())
        self.assertEqual(xml,host_xml())
        self.assertEqual(geometry['originalFrom'], [540,955])
        self.assertEqual(geometry['originalTo'], [540,943])
        self.assertIn([24,881,971,1115], geometry['excludedBounds'])
        self.assertEqual(geometry['from'], [540,684])
        self.assertEqual(geometry['to'], [540,672]); self.assertEqual(geometry['durationMs'],320)
        self.assertEqual(geometry['marginPx'],24)
        for left, top, right, bottom in geometry['excludedBounds']:
            x,y=geometry['from']
            self.assertFalse(top-24 <= y < bottom+24+12)

    def test_replacement_uses_largest_vertical_blank_instead_of_nearer_control_edge(self):
        xml=host_xml().replace('[24,881][971,1115]', '[24,900][971,990]')
        geometry=reader.short_target_geometry(xml,before())
        # A second gap below the editor is closer to the original Y, but the
        # broad empty region above it keeps the entire gesture farther away.
        self.assertEqual(geometry['from'],[540,694])
        self.assertEqual(geometry['to'],[540,682])
        self.assertEqual(geometry['durationMs'],320)

    def test_only_side_gutters_remaining_cannot_supply_a_safe_target(self):
        xml=host_xml().replace('[24,881][971,1115]', '[24,477][971,1194]')
        with self.assertRaisesRegex(AssertionError,'No full-width editable-safe'):
            reader.short_target_geometry(xml,before())

    def test_safe_original_point_is_preserved_without_retargeting(self):
        xml=host_xml().replace('[24,881][971,1115]', '[24,1080][971,1115]')
        geometry=reader.short_target_geometry(xml,before())
        self.assertEqual(geometry['from'],geometry['originalFrom'])
        self.assertEqual(geometry['to'],geometry['originalTo'])

    def test_each_actionable_flag_and_editable_class_excludes_the_actual_segment(self):
        for selected in ('clickable','long-clickable','focusable','checkable','class'):
            tree=ET.fromstring(host_xml()); editor=next(n for n in tree.iter('node') if n.get('resource-id')=='host-editor')
            editor.set('class','android.widget.TextView'); editor.set('enabled','false')
            for flag in ('clickable','long-clickable','focusable','checkable'):editor.set(flag,'false')
            editor.set('class' if selected=='class' else selected,'android.widget.EditText' if selected=='class' else 'true')
            with self.subTest(selected=selected):
                actual=reader.short_target_geometry(ET.tostring(tree,encoding='unicode'),before())
                self.assertIn([24,881,971,1115],actual['excludedBounds']);self.assertEqual(actual['from'],[540,684])

    def test_overlapping_native_control_is_also_excluded(self):
        tree=ET.fromstring(host_xml())
        ET.SubElement(tree,'node',{'class':'android.widget.Button','package':reader.PACKAGE,
            'clickable':'true','bounds':'[995,700][1080,1150]'})
        actual=reader.short_target_geometry(ET.tostring(tree,encoding='unicode'),before())
        self.assertEqual(actual['from'][0],540);self.assertLess(actual['from'][1],700-24)
        self.assertEqual(actual['from'][1]-actual['to'][1],12)

    def test_no_safe_segment_foreign_ownership_and_stale_geometry_reject(self):
        for mutation in ('covered','foreign-web','foreign-child','foreign-ancestor','duplicate-web','web-bounds','child-bounds','flags'):
            tree=ET.fromstring(host_xml()); web=next(n for n in tree.iter('node') if n.get('class')=='android.webkit.WebView')
            editor=next(n for n in tree.iter('node') if n.get('resource-id')=='host-editor')
            if mutation=='covered':editor.set('bounds','[0,477][1080,1194]')
            if mutation=='foreign-web':web.set('package','foreign.test')
            if mutation=='foreign-child':editor.set('package','foreign.test')
            if mutation=='foreign-ancestor':list(tree)[0].set('package','foreign.test')
            if mutation=='duplicate-web':tree.append(copy.deepcopy(web))
            if mutation=='web-bounds':web.set('bounds','[0,477][1080,1195]')
            if mutation=='child-bounds':editor.attrib.pop('bounds')
            if mutation=='flags':editor.attrib.pop('clickable')
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):
                reader.short_target_geometry(ET.tostring(tree,encoding='unicode'),before())
        for field,value in (('keyboard',True),('windowFocus',False),('expanded',False),('command','compactExpand'),('page',False),('webHeight',718)):
            snapshot=before();snapshot[field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):reader.short_target_geometry(host_xml(),snapshot)

    def test_fresh_counterfeit_host_receipt_has_exact_bytes_and_recomputed_geometry(self):
        value=proof();geometry=verify(value)
        self.assertEqual(value['xmlSha256'],hashlib.sha256(host_xml().encode()).hexdigest())
        self.assertEqual(value['captureRecord']['commands'][1]['stdout'],output(host_xml().encode()))
        self.assertEqual(geometry['from'],[540,684]);self.assertEqual(geometry['durationMs'],320)
        self.assertFalse(value['applicationAcceptance']);self.assertTrue(value['preEmitOnly'])
        self.assertEqual((value['originalActionBudgetMs'],value['preparationBudgetMs']),(90000,20000))

    def test_proof_cannot_supply_foreign_identity_altered_bytes_or_an_arbitrary_point(self):
        changes=[lambda p:p.update(sourceCommit='f'*40),lambda p:p.update(sourceTree='f'*40),
            lambda p:p.update(apkSha256='f'*64),lambda p:p.update(runNonce='f'*32),lambda p:p.update(androidUser=10),
            lambda p:p.update(beforeSnapshotSha256='f'*64),lambda p:p.update(xmlSha256='f'*64),
            lambda p:p.update(xmlBytes=p['xmlBytes']+1),lambda p:p.update(activitySha256='f'*64),
            lambda p:p.update(activityBytes=p['activityBytes']+1),lambda p:p['geometry'].update({'from':[540,955]}),
            lambda p:p['geometry'].update(excludedBounds=[]),lambda p:p['geometry'].update(durationMs=640),
            lambda p:p.update(phase='compactExpand'),lambda p:p.update(schema=True),lambda p:p.update(schema=1.0),
            lambda p:p['geometry'].update(targetContract=True),lambda p:p.update(preEmitOnly=False),
            lambda p:p.update(applicationAcceptance=True),lambda p:p.update(extra='unreviewed'),
            lambda p:p.update(originalActionBudgetMs=90001),lambda p:p.update(preparationBudgetMs=20001)]
        for index,change in enumerate(changes):
            value=proof();change(value)
            with self.subTest(index=index),self.assertRaises((AssertionError,ValueError,TypeError,KeyError)):verify(value)

    def test_stale_capture_or_activity_and_extended_deadlines_fail_closed(self):
        changes=[lambda p:p.update(actionStartedAtMonotonicNanos=102_000_000_000),
            lambda p:p.update(activityStartedAtMonotonicNanos=103_000_000_000),
            lambda p:p.update(activityCompletedAtMonotonicNanos=104_000_000_000),
            lambda p:p.update(preparedAtMonotonicNanos=120_000_000_000),
            lambda p:p['captureRecord'].update(existingSceneDeadline=121.0),
            lambda p:p['captureRecord']['commands'][0].update(timeoutSeconds=90),
            lambda p:p['captureRecord']['commands'][1].update(startedAtMonotonicNanos=102_000_000_000),
            lambda p:p['captureRecord'].update(completedAtMonotonicNanos=106_000_000_000)]
        for index,change in enumerate(changes):
            value=proof();change(value)
            with self.subTest(index=index),self.assertRaises((AssertionError,ValueError,TypeError,KeyError)):verify(value)

    def test_capture_metadata_command_and_prefix_corruption_reject(self):
        changes=[lambda p:p.update(captureRunNonce='f'*32),lambda p:p['captureRecord'].update(index=8),
            lambda p:p['captureRecord'].update(status='not-ready'),lambda p:p['captureRecord'].update(xmlSha256='f'*64),
            lambda p:p['captureRecord']['commands'].reverse(),lambda p:p['captureRecord']['commands'][0].update(exitCode=1),
            lambda p:p['captureRecord']['commands'][1]['parts'].append('extra'),
            lambda p:p['captureRecord']['commands'][1]['stdout'].update(text='truncated counterfeiting'),
            lambda p:p['captureRecord']['commands'][1]['stdout'].update(truncated=not p['captureRecord']['commands'][1]['stdout']['truncated']),
            lambda p:p['captureRecord']['commands'][1].update(stderr=output(b'failure')),
            lambda p:p.update(activityState='mLastPausedActivity=ActivityRecord{abc u0 '+reader.ACTIVITY+' t8}\n'),
            lambda p:p.update(activityState=activity().replace('u0','u1')),
            lambda p:p.update(activityState=activity().replace(reader.ACTIVITY,reader.ENVIRONMENT_ACTIVITY))]
        for index,change in enumerate(changes):
            value=proof();change(value)
            with self.subTest(index=index),self.assertRaises((AssertionError,ValueError,TypeError,KeyError)):verify(value)


class ChromeShortDriverTests(unittest.TestCase):
    def invoke(self, failure=None):
        commands=[];reads=[];diagnostic={};xml=host_xml()
        with tempfile.TemporaryDirectory() as directory:
            capture=types.SimpleNamespace(nonce='e'*32,count=7,diagnostics=Path(directory)/'capture.json')
            def read(*,deadline):
                reads.append(deadline)
                if failure=='capture':raise OSError('controlled capture failure')
                raw=xml.replace('package="local.pocketchat.test"','package="foreign.test"') if failure=='xml' else xml
                if failure=='gutter':raw=raw.replace('[24,881][971,1115]','[24,477][971,1194]')
                value=dict(schema=1,sourceCommit='a'*40,runNonce=capture.nonce,attemptCount=7,
                    attempts=[capture_record(raw)])
                if failure=='identity':value['sourceCommit']='f'*40
                if failure=='capture-nonce':value['runNonce']='f'*32
                if failure=='index':value['attemptCount']=8
                capture.diagnostics.write_text(json.dumps(value)+'\n')
                return raw
            capture.read=read
            def command(parts,**kwargs):
                commands.append((parts,kwargs))
                if parts[3:]==['shell','dumpsys','activity','activities']:
                    if failure=='activity':raise subprocess.CalledProcessError(1,parts,output=b'controlled failure')
                    return (activity().replace('u0','u1') if failure=='owner' else activity()).encode()
                self.assertEqual(parts[3:6],['shell','input','swipe'])
                if failure=='input':raise subprocess.TimeoutExpired(parts,kwargs['timeout'])
                return b''
            times=[121.0] if failure=='deadline' else [104.5,107.0,107.25,191.0 if failure=='late-input' else 107.6]
            times_ns=[100_000_000_000,105_000_000_000,106_000_000_000,
                      121_000_000_000 if failure=='prepared' else 107_000_000_000,
                      107_300_000_000,191_000_000_000 if failure=='late-input' else 107_600_000_000]
            result=None;error=None
            with patch.object(runner.time,'monotonic',side_effect=times),patch.object(runner.time,'monotonic_ns',side_effect=times_ns),\
                 patch.object(runner.subprocess,'check_output',side_effect=command):
                try:result=runner.short_swipe_once(capture=capture,prefix=['host-only-adb','-s','host-only-serial'],
                    identity=identity(),nonce='d'*32,android_user=0,before=before(),diagnostic=diagnostic)
                except (AssertionError,OSError,TimeoutError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as caught:error=caught
            return result,error,reads,commands,diagnostic

    def test_actual_python_driver_emits_one_original_swipe_after_fresh_observations(self):
        result,error,reads,commands,diagnostic=self.invoke()
        self.assertIsNone(error);geometry,receipt=result
        self.assertEqual(reads,[120.0]);self.assertEqual(len(commands),2)
        self.assertEqual(commands[0][0][3:],['shell','dumpsys','activity','activities'])
        self.assertEqual(commands[0][1]['timeout'],15.5)
        self.assertEqual(commands[1][0][3:],['shell','input','swipe','540','684','540','672','320'])
        self.assertEqual(commands[1][1]['timeout'],82.75)
        self.assertEqual(verify(receipt),geometry)
        self.assertEqual(diagnostic['inputInvocations'],1)
        self.assertEqual(diagnostic['status'],'input-command-returned')
        self.assertFalse(diagnostic['releaseAcceptance'])
        self.assertEqual(diagnostic['targetProof'],receipt)

    def test_failed_preparation_never_emits_and_original_input_failure_is_not_retried(self):
        for failure in ('capture','identity','capture-nonce','index','xml','gutter','deadline','prepared','activity','owner','input','late-input'):
            with self.subTest(failure=failure):
                result,error,reads,commands,diagnostic=self.invoke(failure)
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(reads,[120.0])
                inputs=[row for row in commands if row[0][3:6]==['shell','input','swipe']]
                self.assertEqual(len(inputs),1 if failure in ('input','late-input') else 0)
                self.assertLessEqual(len(commands),2)
                self.assertFalse(diagnostic['releaseAcceptance'])
                if failure=='input':
                    self.assertEqual(diagnostic['inputInvocations'],1)
                    self.assertEqual(diagnostic['status'],'input-command-failed')
                    self.assertEqual(diagnostic['deliveryStatus'],'not-established')
                    self.assertEqual(verify(diagnostic['targetProof'])['from'],[540,684])


class ChromeShortFullCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the original fixture's real missing-object read/cache. Its SDK
        # validator and every EventTransfer check still execute unchanged.
        original_fixture.ChromeCollapseV2Controls.setUpClass()

    @classmethod
    def tearDownClass(cls):
        original_fixture.ChromeCollapseV2Controls.tearDownClass()

    def case_with_proof(self):
        case=original_fixture.case_fixture(360,1,'d'*32)
        sample=case['observations']['horizontal']
        left,top=sample['webX'],sample['webY']
        right,bottom=left+sample['webWidth'],top+sample['webHeight']
        tree=ET.Element('hierarchy',rotation='0')
        def node(parent,kind,rectangle,**extra):
            l,t,r,b=rectangle
            attrs={'class':kind,'package':reader.PACKAGE,'enabled':'true','clickable':'false',
                'long-clickable':'false','focusable':'false','checkable':'false',
                'bounds':f'[{l},{t}][{r},{b}]'}
            attrs.update(extra)
            return ET.SubElement(parent,'node',attrs)
        owner=node(tree,'android.widget.FrameLayout',(0,0,1080,1920))
        web=node(owner,'android.webkit.WebView',(left,top,right,bottom),focusable='true')
        # Deliberate host-only editable overlap at the original point. These
        # bytes are never saved as Android CI evidence or an original capture.
        node(web,'android.widget.EditText',(24,1100,971,1450),clickable='true',focusable='true')
        node(web,'android.widget.Button',(24,1458,150,1590),clickable='true',focusable='true')
        xml=ET.tostring(tree,encoding='unicode')
        target=reader.make_short_target_proof(raw_xml=xml,activity_state=activity(),
            identity=original_fixture.identity(),nonce=case['runNonce'],android_user=case['androidUser'],
            before=sample,capture_nonce='e'*32,capture_record=capture_record(xml),
            action_started_ns=100_000_000_000,activity_started_ns=105_000_000_000,
            activity_completed_ns=106_000_000_000,prepared_ns=107_000_000_000)
        row=next(row for row in case['actualAndroidInputs'] if row['label']=='short')
        row.update({'from':target['geometry']['from'],'to':target['geometry']['to'],
                    'shortTargetProof':target})
        return case,row

    def verify_case(self,case):
        return reader.verify_case(case,original_fixture.identity())

    def test_original_complete_case_without_proof_keeps_original_geometry_contract(self):
        case=original_fixture.case_fixture(360,1,'d'*32)
        self.assertFalse(any('shortTargetProof' in row for row in case['actualAndroidInputs']))
        self.assertEqual(self.verify_case(case),len(reader.NAMES))
        self.assertEqual(len(case['observations']),34);self.assertEqual(len(case['actualAndroidInputs']),35)

    def test_complete_case_accepts_one_fresh_host_target_proof_with_all_old_checks(self):
        case,row=self.case_with_proof()
        self.assertNotEqual(row['from'],row['shortTargetProof']['geometry']['originalFrom'])
        self.assertEqual(self.verify_case(case),len(reader.NAMES))
        self.assertEqual(sum('shortTargetProof' in value for value in case['actualAndroidInputs']),1)
        self.assertEqual(sum(value['kind']=='swipe' for value in case['actualAndroidInputs']),8)
        self.assertEqual(len(case['observations']),34);self.assertEqual(len(case['actualAndroidInputs']),35)

    def test_changed_coordinates_without_proof_cannot_enter_the_new_contract(self):
        case,row=self.case_with_proof();row.pop('shortTargetProof')
        with self.assertRaises(AssertionError):self.verify_case(case)
        case=original_fixture.case_fixture(360,1,'d'*32)
        row=next(row for row in case['actualAndroidInputs'] if row['label']=='short');row['from'][0]+=1
        with self.assertRaises(AssertionError):self.verify_case(case)

    def test_full_case_rejects_forged_point_and_proof_identity(self):
        changes=[lambda row:row.update({'from':[540,1203]}),
            lambda row:row['shortTargetProof'].update(sourceCommit='f'*40),
            lambda row:row['shortTargetProof'].update(runNonce='f'*32),
            lambda row:row['shortTargetProof'].update(phase='compactExpand'),
            lambda row:row['shortTargetProof'].update(beforeSnapshotSha256='f'*64),
            lambda row:row['shortTargetProof'].update(xmlSha256='f'*64),
            lambda row:row.update(shortTargetProof=None)]
        for index,change in enumerate(changes):
            case,row=self.case_with_proof();change(row)
            with self.subTest(index=index),self.assertRaises((AssertionError,ValueError,TypeError,KeyError)):
                self.verify_case(case)

    def test_target_proof_cannot_authorize_another_input_kind_or_phase(self):
        for label in ('initialAddress','up','horizontal','headerUp','activityResume'):
            case,row=self.case_with_proof()
            other=next(value for value in case['actualAndroidInputs'] if value['label']==label)
            other['shortTargetProof']=row['shortTargetProof']
            with self.subTest(label=label),self.assertRaises(AssertionError):self.verify_case(case)


if __name__ == '__main__': unittest.main()
