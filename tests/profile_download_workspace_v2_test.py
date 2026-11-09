"""Host-only current download interaction controls; never Android evidence."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
sys.path.insert(0, str(ROOT / 'tests/gecko'))
import download_workspace_contract_v2 as contract
import download_workspace_v2 as capture
import ui_visual_contract as matrix
import gecko_ui_visual_capture_test as legacy

SOURCE = 'a' * 40


def hierarchy(*items):
    root = ET.Element('hierarchy')
    for text, description, kind, rectangle in items:
        ET.SubElement(root, 'node', dict(text=text, **{'content-desc': description,
            'class': 'android.widget.' + kind, 'package': contract.PACKAGE,
            'clickable': 'true', 'enabled': 'true', 'bounds': rectangle}))
    return ET.tostring(root, encoding='unicode')


def fixture(row=None, index=1):
    record = copy.deepcopy(row) if row else dict(variant='current', scene='downloads', theme='light',
        fontScale=1, logicalViewport='360x640', actualPixels=[1080,1920], densityDpi=480)
    record['downloadLocationNonce'] = f'{index + 1000:032x}'
    native = legacy.NativeCaptureCoverageTest().label(record)
    native.update(top=600, invocationNonce=f'{index:032x}', activityIdentity=10, rootIdentity=20, buttonIdentity=30)
    record['downloadLocationRaw'] = json.dumps(native)
    icon = ('', '保存位置', 'Button', '[870,90][1020,240]')
    tools = ('', '展开下载工具', 'Button', '[870,300][1014,444]')
    scroll = ('', '', 'ScrollView', f'[40,260][1040,{record["actualPixels"][1]-200}]')
    header = hierarchy(icon, scroll, tools)
    expanded = hierarchy(icon, scroll, ('', '收起下载工具', 'Button', '[870,300][1014,444]'),
                         ('保存位置', '', 'Button', '[600,600][1020,744]'))
    dialog = hierarchy(('保存位置', '', 'TextView', '[80,300][1000,400]'),
        ('默认位置：Download/元婴期院士/窗口_编号/\n\n文件菜单显示实际保存位置。', '', 'TextView', '[80,420][1000,850]'),
        ('知道了', '', 'Button', '[720,900][1020,1044]'))
    value = dict(schema=2, status='passed', actualAndroidExecution=True, sourceCommit=SOURCE,
        invocationNonce=native['invocationNonce'], headerXml=header, returnedXml=header, beforeToolsXml=header,
        dialogXml=dialog, toolsXml=expanded, measuredXml=expanded,
        dialogImage='model-location-dialog.png', dialogXmlFile='model-location-dialog.xml',
        toolsImage='model-expanded-tools.png', toolsXmlFile='model-expanded-tools.xml',
        actualAndroidTaps=2, actualAndroidBack=1, actualAndroidSwipes=0, events=[
            dict(sequence=1, kind='tap', atMs=100, target='保存位置', bounds=[870,90,1020,240], point=[945,165]),
            dict(sequence=2, kind='back', atMs=110, keyCode=4),
            dict(sequence=3, kind='tap', atMs=120, target='展开下载工具', bounds=[870,300,1014,444], point=[942,372])])
    record.update(downloadWorkspaceContract=2, downloadWorkspace=value)
    return record


class DownloadWorkspaceReaderTest(unittest.TestCase):
    def test_current_five_captures_and_original_111_matrix(self):
        records = legacy.NativeCaptureCoverageTest().records()
        for index, row in enumerate(records):
            if row['scene'] == 'downloads':
                records[index] = fixture(row, index + 1)
        self.assertEqual(len(records), 111)
        self.assertEqual(sum(row['scene'] == 'downloads' for row in records), 5)
        matrix.verify_captures(records, SOURCE)
        matrix.verify_captures(legacy.NativeCaptureCoverageTest().records(), SOURCE)

    def test_original_native_label_gate_is_exact_and_still_fails_clipping(self):
        name = 'tools/gecko/ui_visual_contract.py'
        def function(text):
            return ast.dump(next(node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef) and node.name=='verify_download_location'),include_attributes=False)
        self.assertEqual(hashlib.sha256(function((ROOT/name).read_text()).encode()).hexdigest(),
                         'f8e37f331dab44d0803ec63ed909f86365e1f851120fc3af6f5bfcee33a600a7')
        for key, value in (('visibleHeight',143),('layoutTextLength',3),('actualAndroidLayout',False),('viewClass','android.widget.Button')):
            record=fixture();native=json.loads(record['downloadLocationRaw']);native[key]=value;record['downloadLocationRaw']=json.dumps(native)
            with self.subTest(key=key),self.assertRaises(AssertionError):contract.verify_download_workspace(record,SOURCE)

    def test_header_role_accessibility_and_real_touch_bounds_are_required(self):
        for before, after in (('content-desc="保存位置"','content-desc="其他"'),
                              ('[870,90][1020,240]','[870,90][1010,230]'),
                              ('package="local.pocketchat.test"','package="other.application"'),
                              ('clickable="true"','clickable="false"')):
            record=fixture();value=record['downloadWorkspace'];value['headerXml']=value['headerXml'].replace(before,after,1)
            with self.subTest(change=after),self.assertRaises(AssertionError):contract.verify_download_workspace(record,SOURCE)

    def test_actual_dialog_and_expanded_same_native_label_are_required(self):
        for key, before, after in (('dialogXml','默认位置：Download/元婴期院士/窗口_编号/','Unrelated dialog'),
                                   ('dialogXml','知道了','确定'),('toolsXml','[600,600][1020,744]','[600,601][1020,745]'),
                                   ('measuredXml','text="保存位置"','text="其他位置"')):
            record=fixture();value=record['downloadWorkspace'];value[key]=value[key].replace(before,after,1)
            with self.subTest(key=key),self.assertRaises(AssertionError):contract.verify_download_workspace(record,SOURCE)

    def test_wrong_source_invocation_replayed_tap_or_fabricated_count_fails(self):
        changes=[lambda v:v.update(sourceCommit='b'*40),lambda v:v.update(invocationNonce='f'*32),
                 lambda v:v['events'].append(copy.deepcopy(v['events'][0])),
                 lambda v:v['events'][0].update(point=[900,100]),lambda v:v.update(actualAndroidTaps=1),
                 lambda v:v.update(actualAndroidBack=True),lambda v:v.update(actualAndroidExecution=False)]
        for change in changes:
            record=fixture();change(record['downloadWorkspace'])
            with self.subTest(change=change),self.assertRaises(AssertionError):contract.verify_download_workspace(record,SOURCE)

    def test_matrix_rejects_partial_versions_and_duplicate_invocations(self):
        for mode in ('mixed','unknown','duplicate'):
            records=legacy.NativeCaptureCoverageTest().records();indices=[i for i,r in enumerate(records) if r['scene']=='downloads']
            for i in indices:records[i]=fixture(records[i],i+1)
            if mode=='mixed':records[indices[0]].pop('downloadWorkspaceContract')
            elif mode=='unknown':records[indices[0]]['downloadWorkspaceContract']=3
            else:
                row=records[indices[0]];parent=records[indices[1]]['downloadWorkspace']['invocationNonce'];row['downloadWorkspace']['invocationNonce']=parent
                native=json.loads(row['downloadLocationRaw']);native['invocationNonce']=parent;row['downloadLocationRaw']=json.dumps(native)
            with self.subTest(mode=mode),self.assertRaises(AssertionError):matrix.verify_captures(records,SOURCE)


class DownloadWorkspaceDriverTest(unittest.TestCase):
    def run_driver(self, failure=None):
        expected=fixture();observations=expected['downloadWorkspace'];row={k:copy.deepcopy(v) for k,v in expected.items() if k not in ('downloadWorkspace','downloadWorkspaceContract','downloadLocationRaw','downloadLocationNonce')}
        state=dict(phase='default',clock=100.0,taps=0,nonce=None,tools_ready=failure!='scroll',label_ready=failure!='scroll');commands=[];deadlines=[]
        def adb(deadline,*parts):
            self.assertGreater(deadline,state['clock']);deadlines.append(deadline);state['clock']+=.01;commands.append(parts)
            if parts[:3]==('shell','input','tap'):
                state['taps']+=1;state['phase']='dialog' if state['taps']==1 else 'expanded'
            elif parts[:3]==('shell','input','swipe'):
                start,end=int(parts[4]),int(parts[6])
                if state['phase']=='default' and start<end:state['tools_ready']=True
                if state['phase']=='expanded' and start>end:state['label_ready']=True
            elif parts[:3]==('shell','input','keyevent'):state['phase']='default'
            elif parts[:3]==('shell','am','start'):
                self.assertEqual(state['phase'],'expanded');self.assertIn('--activity-single-top',parts)
                self.assertEqual(parts[parts.index('visualObserveAction')+1],'download-workspace-location')
                self.assertEqual(parts[parts.index('visualParentNonce')+1],observations['invocationNonce'])
                self.assertEqual(parts[parts.index('visualSourceCommit')+1],SOURCE)
                state['nonce']=parts[parts.index('visualObserveNonce')+1]
            elif parts[:3]==('logcat','-d','-s'):
                native=json.loads(expected['downloadLocationRaw']);native['nonce']=state['nonce']
                if failure=='native':native['visibleHeight']=143
                return 'I PocketDownloadLabel: '+json.dumps(native)
            return ''
        def dump(deadline):
            self.assertGreater(deadline,state['clock']);deadlines.append(deadline);state['clock']+=.1
            if state['phase']=='dialog' and failure!='dialog':return observations['dialogXml']
            xml=observations['toolsXml'] if state['phase']=='expanded' else observations['headerXml']
            if not state['tools_ready'] or state['phase']=='expanded' and not state['label_ready']:
                tree=ET.fromstring(xml)
                for item in list(tree):
                    if (not state['tools_ready'] and item.get('content-desc')=='展开下载工具'
                        or state['phase']=='expanded' and not state['label_ready'] and item.get('text')=='保存位置'):tree.remove(item)
                xml=ET.tostring(tree,encoding='unicode')
            return xml
        def sleep(value):state['clock']+=value
        clock=types.SimpleNamespace(monotonic=lambda:state['clock'],monotonic_ns=lambda:int(state['clock']*1e9),sleep=sleep)
        png=b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',*row['actualPixels'])
        with tempfile.TemporaryDirectory(prefix='download-v2-host-') as directory,mock.patch.object(capture,'time',clock):
            error=None
            try:capture.capture(adb,dump,lambda deadline:png,SOURCE,observations['invocationNonce'],Path(directory),'model',row)
            except Exception as caught:error=caught
            receipt=json.loads((Path(directory)/'model-download-workspace-v2.json').read_text())
        return row,receipt,commands,deadlines,state,error

    def test_actual_helper_issues_two_taps_back_and_fresh_read_without_rebuilding(self):
        row,receipt,commands,deadlines,state,error=self.run_driver()
        self.assertIsNone(error);contract.verify_download_workspace(row,SOURCE)
        self.assertEqual([c for c in commands if c[:2]==('shell','input')],[('shell','input','tap','945','165'),('shell','input','keyevent','4'),('shell','input','tap','942','372')])
        self.assertEqual(set(deadlines),{135.0});self.assertEqual(receipt['status'],'passed')
        self.assertFalse(any(c[:3] in [('shell','am','force-stop'),('shell','pm','clear')] for c in commands))

    def test_missing_dialog_never_replays_tap_or_resets_deadline(self):
        _,receipt,commands,deadlines,state,error=self.run_driver('dialog')
        self.assertIsInstance(error,TimeoutError);self.assertEqual(state['taps'],1)
        self.assertEqual(set(deadlines),{135.0});self.assertNotEqual(receipt['status'],'passed')
        self.assertFalse(any(c[:3]==('shell','am','start') for c in commands))

    def test_real_visibility_gestures_reveal_tools_then_label_in_opposite_directions(self):
        row,receipt,commands,deadlines,state,error=self.run_driver('scroll')
        self.assertIsNone(error);contract.verify_download_workspace(row,SOURCE)
        self.assertEqual([event['kind'] for event in receipt['events']],['tap','back','swipe','tap','swipe'])
        self.assertEqual([event['stage'] for event in receipt['events'] if event['kind']=='swipe'],['reveal-tools','reveal-label'])
        self.assertEqual(set(deadlines),{135.0});self.assertEqual(state['taps'],2)
        broken=copy.deepcopy(row);broken['downloadWorkspace']['events'][2]['stage']='reveal-label'
        with self.assertRaises(AssertionError):contract.verify_download_workspace(broken,SOURCE)

    def test_native_clipping_still_fails_and_retains_actual_partial_events(self):
        _,receipt,commands,deadlines,state,error=self.run_driver('native')
        self.assertIsInstance(error,AssertionError);self.assertEqual(state['taps'],2)
        self.assertEqual([event['kind'] for event in receipt['events']],['tap','back','tap'])
        self.assertNotEqual(receipt['status'],'passed')


class DownloadWorkspaceStageTest(unittest.TestCase):
    def test_real_staging_includes_reader_and_runs_without_repository_imports(self):
        from profile_release_navigation_v2_test import stage_actual_reader_blocks
        script='''import json,pathlib,sys
stage=pathlib.Path.cwd().resolve();sys.path.insert(0,str(stage))
from tools.gecko.download_workspace_contract_v2 import verify_download_workspace
verify_download_workspace(json.loads(sys.stdin.read()),"a"*40)
for name,module in list(sys.modules.items()):
 if name.startswith("tools.gecko") and getattr(module,"__file__",None):assert pathlib.Path(module.__file__).resolve().is_relative_to(stage)
'''
        with tempfile.TemporaryDirectory(prefix='download-v2-stage-') as directory:
            stage=Path(directory);stage_actual_reader_blocks(stage)
            environment=dict(os.environ);environment.pop('PYTHONPATH',None)
            result=subprocess.run([sys.executable,'-I','-c',script],cwd=stage,input=json.dumps(fixture()),text=True,capture_output=True,env=environment)
            self.assertEqual(result.returncode,0,result.stderr)
            (stage/'tools/gecko/download_workspace_contract_v2.py').unlink()
            result=subprocess.run([sys.executable,'-I','-c',script],cwd=stage,input=json.dumps(fixture()),text=True,capture_output=True,env=environment)
            self.assertNotEqual(result.returncode,0);self.assertIn('ModuleNotFoundError',result.stderr)


if __name__=='__main__':unittest.main()
