"""Finite CPU-on-IP preparation only; no runtime projection or Android claims."""
from historical_source_inputs import historical_bytes
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cpu_ip_source_compatibility as layer
from tls_cpu_ip_source_compatibility import source_input as tls_source_input
from final_browser_source_compatibility import metadata_input as final_metadata_input
import photo_background_source_compatibility as photo_background

ROOT=Path(__file__).resolve().parents[1]
SHA=lambda raw:hashlib.sha256(raw).hexdigest()


# Only the reviewed removal of automatic-resend wording is normalized for
# historical whole-file comparisons. Runtime and host code use current files.
BROWSER_COPY_CHANGES = {'app/src/main/java/local/pocketchat/GeckoTimeZoneUi.java': {'previous': (14385,
                                                                          '8a10db4213ebca20f247b9425f90037cd33db227e517a95a44d59094a8a1c6a3'),
                                                             'current': (14358,
                                                                         '640d28f48251f297970c17ba6df6bf2d8b60f6f697d0167162e8e20a22a4eeb2'),
                                                             'deltas': [('  private static void '
                                                                         'confirm(MainActivity a,ChatSession '
                                                                         's,GeckoTimeZoneStore.State '
                                                                         'expected,GeckoTimeZoneSpec '
                                                                         'wanted,Fence fence,JSONObject '
                                                                         'page,boolean '
                                                                         'manual,Consumer<String> done){\n'
                                                                         '    '
                                                                         'if(!activity(a,s)||!fence.current(s)){done.accept("当前网页已变化，未保存时区");return;}\n'
                                                                         '    ReferenceUi.Modal confirm=new '
                                                                         'ReferenceUi.Modal(a,"应用当前环境时区？");\n'
                                                                         '    '
                                                                         'confirm.note("保存为“"+wanted.label()+"”后将重新加载当前网页，并关闭此环境已打开的弹窗。");\n'
                                                                         '    '
                                                                         'if(!wanted.followsSystem())confirm.note("Service '
                                                                         'Worker '
                                                                         '仍可读取系统时区，不能提供完整时区隔离。原生设置回读不代表当前页面或 '
                                                                         'Worker 已通过验证。");\n'
                                                                         '    '
                                                                         'if(page==null&&s.web.hasVisibleDocument()||manual&&page!=null)confirm.note("当前网站的回复、上传、输入或表单不能完整自动核对与保留。请先取消并结束网站操作、手动保存；继续表示已结束相关操作并保留需要的内容。");\n'
                                                                         '    else '
                                                                         'if(page!=null&&PageMemory.hasDraft(page))confirm.note("当前 '
                                                                         'ChatGPT '
                                                                         '草稿会先暂存并再次核对。若输入变化或无法暂存，将保留网页并停止应用。");\n',
                                                                         '  private static void '
                                                                         'confirm(MainActivity a,ChatSession '
                                                                         's,GeckoTimeZoneStore.State '
                                                                         'expected,GeckoTimeZoneSpec '
                                                                         'wanted,Fence fence,JSONObject '
                                                                         'page,boolean '
                                                                         'manual,Consumer<String> done){\n'
                                                                         '    '
                                                                         'if(!activity(a,s)||!fence.current(s)){done.accept("当前网页已变化，未保存时区");return;}\n'
                                                                         '    ReferenceUi.Modal confirm=new '
                                                                         'ReferenceUi.Modal(a,"应用当前环境时区？");\n'
                                                                         '    '
                                                                         'confirm.note("保存为“"+wanted.label()+"”后将重新加载当前网页，并关闭此环境已打开的弹窗。不会自动重发提问。");\n'
                                                                         '    '
                                                                         'if(!wanted.followsSystem())confirm.note("Service '
                                                                         'Worker '
                                                                         '仍可读取系统时区，不能提供完整时区隔离。原生设置回读不代表当前页面或 '
                                                                         'Worker 已通过验证。");\n'
                                                                         '    '
                                                                         'if(page==null&&s.web.hasVisibleDocument()||manual&&page!=null)confirm.note("当前网站的回复、上传、输入或表单不能完整自动核对与保留。请先取消并结束网站操作、手动保存；继续表示已结束相关操作并保留需要的内容。");\n'
                                                                         '    else '
                                                                         'if(page!=null&&PageMemory.hasDraft(page))confirm.note("当前 '
                                                                         'ChatGPT '
                                                                         '草稿会先暂存并再次核对。若输入变化或无法暂存，将保留网页并停止应用。");\n')]},
 'app/src/main/java/local/pocketchat/GeckoPopupNavigationUi.java': {'previous': (15727,
                                                                                 '39ae6f65c3eb957fe5f7a8b0f1e2a01ef85177abe0e11a71a5d721ae6e39392b'),
                                                                    'current': (15697,
                                                                                'ec792da8d55a3e6ebab857ebed1ff32605785a63425475856d70e1e4e5d61fb2'),
                                                                    'deltas': [('  void confirm(Attempt '
                                                                                'value){\n'
                                                                                '    '
                                                                                'if(!valid(value,false)){fail(value,changedMessage());return;}\n'
                                                                                '    MainActivity '
                                                                                'activity=value.target.activity;ReferenceUi.Modal '
                                                                                'confirm=new '
                                                                                'ReferenceUi.Modal(activity,"在当前页打开链接？");dialog=confirm;\n'
                                                                                '    '
                                                                                'confirm.note("新窗口已拦截。继续会用目标网页替换当前页，不能保证网站的登录跳转结果。");confirm.note(value.target.target);\n'
                                                                                '    '
                                                                                'if(value.manual)confirm.note("请先结束网站正在进行的回复、上传或其他操作，并手动保存表单和输入。继续表示已完成这些操作并保留所需内容。"+(value.page!=null?"本机草稿保存已关闭，本次不会保存草稿副本。":""));\n'
                                                                                '    else '
                                                                                'if(value.page!=null&&PageMemory.hasDraft(value.page))confirm.note("当前 '
                                                                                'ChatGPT '
                                                                                '草稿会先暂存到本机并再次核对；若输入变化或无法暂存，当前网页会保留。");\n'
                                                                                '    '
                                                                                'confirm.cancel=()->fail(value,"已取消，当前网页已保留");confirm.setOnDismissListener(ignored->{if(dialog==confirm){dialog=null;fail(value,"已取消，当前网页已保留");}});\n',
                                                                                '  void confirm(Attempt '
                                                                                'value){\n'
                                                                                '    '
                                                                                'if(!valid(value,false)){fail(value,changedMessage());return;}\n'
                                                                                '    MainActivity '
                                                                                'activity=value.target.activity;ReferenceUi.Modal '
                                                                                'confirm=new '
                                                                                'ReferenceUi.Modal(activity,"在当前页打开链接？");dialog=confirm;\n'
                                                                                '    '
                                                                                'confirm.note("新窗口已拦截。继续会用目标网页替换当前页，不会自动重发提问，也不能保证网站的登录跳转结果。");confirm.note(value.target.target);\n'
                                                                                '    '
                                                                                'if(value.manual)confirm.note("请先结束网站正在进行的回复、上传或其他操作，并手动保存表单和输入。继续表示已完成这些操作并保留所需内容。"+(value.page!=null?"本机草稿保存已关闭，本次不会保存草稿副本。":""));\n'
                                                                                '    else '
                                                                                'if(value.page!=null&&PageMemory.hasDraft(value.page))confirm.note("当前 '
                                                                                'ChatGPT '
                                                                                '草稿会先暂存到本机并再次核对；若输入变化或无法暂存，当前网页会保留。");\n'
                                                                                '    '
                                                                                'confirm.cancel=()->fail(value,"已取消，当前网页已保留");confirm.setOnDismissListener(ignored->{if(dialog==confirm){dialog=null;fail(value,"已取消，当前网页已保留");}});\n')]}}

def browser_copy_input(raw, relative):
    if relative not in BROWSER_COPY_CHANGES:
        return raw
    item=BROWSER_COPY_CHANGES[relative]
    assert type(raw) is bytes
    identity=(len(raw),SHA(raw))
    if identity==item["previous"]:
        return raw
    assert identity==item["current"],"Unreviewed browser copy source"
    restored=raw
    for current,previous in item["deltas"]:
        current,previous=current.encode(),previous.encode()
        assert restored.count(current)==1
        restored=restored.replace(current,previous,1)
    assert (len(restored),SHA(restored))==item["previous"]
    forward=restored
    for current,previous in item["deltas"]:
        current,previous=current.encode(),previous.encode()
        assert forward.count(previous)==1
        forward=forward.replace(previous,current,1)
    assert forward==raw
    return restored


def git(*args):
    return subprocess.check_output(['git','--no-replace-objects',*args],cwd=ROOT,
        env=dict(os.environ,GIT_NO_LAZY_FETCH='1',GIT_OPTIONAL_LOCKS='0'))


class CpuIpHistoricalPreparation(unittest.TestCase):
    def test_complete_real_candidate_before_forward_and_inverse(self):
        self.assertEqual(git('rev-parse',layer.BASE_COMMIT+'^{tree}').decode().strip(),layer.BASE_TREE)
        value=layer.manifest();self.assertEqual(len(value['files']),2)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()),9)
        for relative,row in value['files'].items():
            before=git('show',layer.BASE_COMMIT+':'+relative);after=tls_source_input(historical_bytes(relative),relative)
            self.assertEqual((SHA(before),len(before)),(row['previousSha256'],row['previousBytes']))
            self.assertEqual((SHA(after),len(after)),(row['reviewedSha256'],row['reviewedBytes']))
            self.assertEqual(layer.source_input(before,relative),before)
            self.assertEqual(layer.source_input(after,relative),before)
            forward=before
            for item in row['deltas']:
                old,new=item['previous'].encode(),item['current'].encode()
                self.assertEqual(forward.count(old),1);forward=forward.replace(old,new,1)
            self.assertEqual(forward,after)

    def test_every_missing_duplicate_changed_moved_truncated_and_unknown_input_rejects(self):
        rejected=0
        for relative,row in layer.manifest()['files'].items():
            after=tls_source_input(historical_bytes(relative),relative)
            for delta in row['deltas']:
                part=delta['current'].encode();self.assertEqual(after.count(part),1)
                removed=after.replace(part,b'',1);moved=removed+part
                if moved==after:moved=part+removed
                for raw in (removed,after.replace(part,part+part,1),after.replace(part,part+b' ',1),moved,after[:-1],b'/* unknown */\n'+after):
                    with self.assertRaises(ValueError):layer.source_input(raw,relative)
                    rejected+=1
        self.assertEqual(rejected,54)

    def test_only_exact_complete_bytes_and_owned_paths_are_admitted(self):
        relative=next(iter(layer.PATHS));raw=historical_bytes(relative)
        for bad in (None,'source',bytearray(raw),raw[:100]):
            with self.assertRaises(ValueError):layer.source_input(bad,relative)
        for bad in (None,Path(relative),'/'+relative,'./'+relative,'app/src/main/java/local/pocketchat/MainActivity.java'):
            with self.assertRaises(ValueError):layer.source_input(raw,bad)

    def test_fixture_whole_pin_type_duplicates_and_bound(self):
        raw=layer.DELTA_PATH.read_bytes()
        for bad in (raw+b'\n',b' '+raw,raw[:-1],None,raw.decode(),b'x'*(layer.MAX_FIXTURE_BYTES+1)):
            with self.assertRaises(ValueError):layer._decode(bad)
        duplicate=raw.replace(b'"schema": 1',b'"schema": 1, "schema": 1',1)
        with patch.object(layer,'DELTA_SHA256',SHA(duplicate)),self.assertRaises(ValueError):layer._decode(duplicate)

    def test_counterfeit_metadata_or_oracle_members_reject_even_with_rebound_outer_pin(self):
        original=json.loads(layer.DELTA_PATH.read_bytes());relative=next(iter(layer.PATHS))
        mutations=[]
        for key,value in (('schema',True),('baseCommit','0'*40),('baseTree','0'*40),('actualAndroidExecution',True),('runtimeAcceptance',True),('oracle','replacement')):
            current=copy.deepcopy(original);current[key]=value;mutations.append(current)
        for key,value in (('previousBytes',True),('reviewedBytes',131073),('contextLines',2),('reviewedSha256','x'*64),('oracle','replacement')):
            current=copy.deepcopy(original);current['files'][relative][key]=value;mutations.append(current)
        current=copy.deepcopy(original);current['files']['unexpected.java']=current['files'][relative];mutations.append(current)
        current=copy.deepcopy(original);current['files'][relative]['deltas'][0]['current']+='corruption';mutations.append(current)
        for value in mutations:
            raw=json.dumps(value).encode()
            with patch.object(layer,'DELTA_SHA256',SHA(raw)),self.assertRaises(ValueError):layer._decode(raw)
        self.assertEqual(len(mutations),13)

    def test_real_fixture_symlink_and_foreign_path_reject(self):
        with tempfile.TemporaryDirectory(prefix='cpu-ip-history-') as temporary:
            root=Path(temporary);target=root/'original';target.write_bytes(layer.DELTA_PATH.read_bytes())
            path=root/'tests/fixtures/cpu-ip-source-deltas.json';path.parent.mkdir(parents=True);path.symlink_to(target)
            with patch.object(layer,'ROOT',root),patch.object(layer,'DELTA_PATH',path),self.assertRaises(ValueError):layer.manifest()
        with patch.object(layer,'DELTA_PATH',ROOT/'tests/fixtures/unreviewed.json'),self.assertRaises(ValueError):layer.manifest()

    def test_focused_pin_and_duplicate_guard_counterfeits_fail_the_same_original_checks(self):
        source=(ROOT/'tests/cpu_ip_source_compatibility.py').read_text();raw=layer.DELTA_PATH.read_bytes()
        changed=raw+b'\n';needle=' or _sha(raw) != DELTA_SHA256';self.assertEqual(source.count(needle),1)
        namespace={'__file__':str(ROOT/'tests/cpu_ip_source_compatibility.py'),'__name__':'cpu_ip_counterfeit'}
        exec(compile(source.replace(needle,'',1),'<pin counterfeit>','exec'),namespace)
        def original_pin_check(decode):
            with self.assertRaises(ValueError):decode(changed)
        original_pin_check(layer._decode)
        with self.assertRaises(AssertionError):original_pin_check(namespace['_decode'])
        duplicate=raw.replace(b'"schema": 1',b'"schema": 1, "schema": 1',1)
        namespace={'__file__':str(ROOT/'tests/cpu_ip_source_compatibility.py'),'__name__':'cpu_ip_counterfeit'}
        exec(compile(source.replace('json.loads(raw, object_pairs_hook=_unique)','json.loads(raw)',1),'<duplicate counterfeit>','exec'),namespace)
        namespace['DELTA_SHA256']=SHA(duplicate)
        with patch.object(layer,'DELTA_SHA256',SHA(duplicate)),self.assertRaises(ValueError):layer._decode(duplicate)
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):namespace['_decode'](duplicate)

    def test_all_original_fixtures_and_preexisting_test_assertions_remain_whole_bytes(self):
        fixtures=git('ls-tree','-r','--name-only',layer.BASE_COMMIT,'tests/fixtures').decode().splitlines()
        tests=('tests/browser_acceptance_workflow_test.py','tests/browser_environment_publish_gate_test.py',
            'tests/browser_fingerprint_publish_gate_test.py','tests/gecko-addon-lifecycle-host/AddonHost.java.in',
            'tests/gecko-addon-lifecycle-host/run.py','tests/native-protection-host/NativeProtectionControllerHost.java.in',
            'tests/native-runtime-capabilities-host/NativeRuntimeCapabilitiesHost.java','tests/profile_dual_browser_source_compatibility_test.py',
            'tests/profile_native_protection_test.py','tests/profile_worker_timezone_host_source_compatibility_test.py',
            'tests/profile_worker_timezone_source_compatibility_test.py','tests/review-host/run_identity_controller_host.py',
            'tests/worker_timezone_host_source_compatibility.py','tests/worker_timezone_source_compatibility.py')
        for relative in [*fixtures,*tests]:
            with self.subTest(path=relative):self.assertEqual(final_metadata_input(((ROOT/relative).read_bytes() if relative.startswith('tests/fixtures/') else historical_bytes(relative)),relative),git('show',layer.BASE_COMMIT+':'+relative))

    def test_ip_desired_native_controller_parser_and_guard_assets_remain_verbatim(self):
        paths=['app/src/main/java/local/pocketchat/'+name+'.java' for name in ('GeckoTimeZoneSpec','GeckoTimeZoneStore',
            'GeckoTimeZoneController','GeckoTimeZonePolicy','GeckoTimeZoneUi','GeckoIpTimeZonePolicy','GeckoIpRouteWatch','GeckoPopupNavigationUi')]
        paths+=['app/src/main/assets/gecko/'+name for name in ('background.js','ip-timezone-bootstrap.js','request-headers.js','native-timezone-api.js','native-timezone-bridge.js')]
        for relative in paths:
            with self.subTest(path=relative):
                raw=browser_copy_input((ROOT/relative).read_bytes(),relative)
                if relative==photo_background.PATH:
                    raw=photo_background.source_input(raw,relative)
                self.assertEqual(raw,git('show',layer.BASE_COMMIT+':'+relative))

    def test_browser_copy_inverse_only_admits_reviewed_complete_files(self):
        for relative,item in BROWSER_COPY_CHANGES.items():
            current=(ROOT/relative).read_bytes();restored=browser_copy_input(current,relative)
            self.assertEqual((len(restored),SHA(restored)),item['previous'])
            self.assertEqual(browser_copy_input(restored,relative),restored)
            part=item['deltas'][0][0].encode();self.assertEqual(current.count(part),1)
            mutations=(current+b'\n',current[:-1],current.replace(part,b'',1),
                       current.replace(part,part+part,1),current.replace(part,b'',1)+part,
                       current.replace(b'if(',b'if(false&&',1))
            for changed in mutations:
                self.assertNotEqual(changed,current)
                with self.subTest(path=relative),self.assertRaises(AssertionError):
                    browser_copy_input(changed,relative)

    def test_photo_inverse_restores_the_real_complete_original_without_changing_other_guards(self):
        relative=photo_background.PATH
        before=git('show',layer.BASE_COMMIT+':'+relative);current=(ROOT/relative).read_bytes()
        self.assertEqual((len(before),SHA(before)),(photo_background.PREVIOUS_BYTES,photo_background.PREVIOUS_SHA256))
        self.assertEqual((len(current),SHA(current)),(photo_background.CURRENT_BYTES,photo_background.CURRENT_SHA256))
        self.assertEqual(photo_background.source_input(before,relative),before)
        self.assertEqual(photo_background.source_input(current,relative),before)
        forward=before
        for new,old in photo_background.DELTAS:
            self.assertEqual(forward.count(old),1);forward=forward.replace(old,new,1)
        self.assertEqual(forward,current)

    def test_photo_inverse_rejects_changed_old_guard_or_missing_duplicate_moved_new_route(self):
        relative=photo_background.PATH;current=(ROOT/relative).read_bytes()
        mutations=[current+b'\n',current[:-1],current.replace(b'if(port!==host)',b'if(false)',1)]
        for part in (photo_background.PHOTO_ROUTE,photo_background.PHOTO_DISCONNECT):
            self.assertEqual(current.count(part),1)
            removed=current.replace(part,b'',1)
            mutations.extend((removed,removed+part,current.replace(part,part+part,1),current.replace(part,part+b' ',1)))
        for raw in mutations:
            self.assertNotEqual(raw,current)
            with self.assertRaises(ValueError):photo_background.source_input(raw,relative)
        self.assertEqual(len(mutations),11)
        for raw in (None,current.decode(),bytearray(current),current[:200]):
            with self.assertRaises(ValueError):photo_background.source_input(raw,relative)
        for path in (None,Path(relative),'./'+relative,'/'+relative,'app/src/main/assets/gecko/native-photo-api.js'):
            with self.assertRaises(ValueError):photo_background.source_input(current,path)

    def test_photo_inverse_never_reaches_production_or_actual_photo_behavior_hosts(self):
        paths=list((ROOT/'app').rglob('*.py'))+list((ROOT/'tools').rglob('*.py'))
        paths+=[ROOT/'tests/gecko_photo_permission_test.py',ROOT/'tests/gecko_upload_files_test.py',ROOT/'tests/gecko/run_device.py',ROOT/'tests/chromium-photo-browser/run.py']
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.ImportFrom):self.assertNotEqual(node.module,'photo_background_source_compatibility',str(path))
                elif isinstance(node,ast.Import):self.assertNotIn('photo_background_source_compatibility',[entry.name for entry in node.names],str(path))

    def test_no_runtime_or_behavior_consumer_imports_this_historical_layer(self):
        for folder in ('app','tools','tests/gecko-cpu-host','tests/gecko-cpu-controller-host','tests/gecko-cpu-ui-host','tests/gecko-ip-transport-host'):
            for path in (ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node,ast.ImportFrom):self.assertNotEqual(node.module,'cpu_ip_source_compatibility',str(path))
                    elif isinstance(node,ast.Import):self.assertNotIn('cpu_ip_source_compatibility',[entry.name for entry in node.names],str(path))


if __name__=='__main__':unittest.main(verbosity=2)
