"""AM/proc/meminfo identity negatives; fixtures are explicitly synthetic."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import experience_process_identity as M
import experience_scenarios as scenarios
from experience_memory_fixture import PACKAGE,ISOLATED,raw_snapshot,block,stat


class MemoryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.raw = raw_snapshot(M.PROTOCOL)

    def evaluate(self, raw=None):
        return M.evaluate(self.raw if raw is None else raw,PACKAGE,M.parse_stat,scenarios.pss_value)

    def rejected(self, mutate, message=None):
        raw = copy.deepcopy(self.raw);mutate(raw);result=self.evaluate(raw)
        self.assertFalse(result['available'],result);self.assertIsNone(result['totalPssKb'])
        if message:self.assertIn(message,result['error'])

    def test_complete_owner_and_exact_truncation_have_real_pss_values_not_zero(self):
        result=self.evaluate();self.assertTrue(result['available'],result)
        self.assertEqual(result['totalPssKb'],23000);self.assertEqual(len(result['processes']),2)
        self.assertIn('15-byte-comm',result['processes'][1]['argvIdentity'])
        M.verify(dict(result,rawEvidence=self.raw),PACKAGE,M.parse_stat,scenarios.pss_value)

    def test_exact_installed_uid_does_not_select_another_app_with_same_prefix(self):
        self.assertEqual(M.package_uid(self.raw['before']['packageUidRaw'],PACKAGE),10210)
        for bad in ('package:'+PACKAGE+'.other uid:10210\n',('package:'+PACKAGE+' uid:10210\n')*2):
            with self.assertRaises(ValueError):M.package_uid(bad,PACKAGE)

    def test_other_package_same_process_prefix_is_rejected(self):
        self.rejected(lambda r:[r[s].update(amRaw=r[s]['amRaw'].replace('packageList={'+PACKAGE+'}', 'packageList={'+PACKAGE+'.other}'))for s in ('before','after')], 'exact target')

    def test_owner_uid_crossed_or_multiple_hosting_packages_are_rejected(self):
        for before,after in [('uid=10210 ISOLATED','uid=10211 ISOLATED'),('packageList={'+PACKAGE+'}','packageList={'+PACKAGE+', other.app}')]:
            self.rejected(lambda r:[r[s].update(amRaw=r[s]['amRaw'].replace(before,after))for s in ('before','after')])

    def test_each_runtime_uid_credential_before_and_after_is_required(self):
        for side in ('Before','After'):
            self.rejected(lambda r:r['processes'][1].update({'rawStatus'+side:r['processes'][1]['rawStatus'+side].replace('99001','99002',1)}),'runtime UID')

    def test_pid_generation_comm_parent_or_counter_race_is_rejected(self):
        for replacement in (stat(12,ISOLATED[-15:],901),stat(13,ISOLATED[-15:]),stat(12,'wrong-comm'),stat(12,ISOLATED[-15:],parent=358),stat(12,ISOLATED[-15:]).replace(' 123 ',' 122 '),''):
            self.rejected(lambda r:r['processes'][1].update(rawStatAfter=replacement))

    def test_am_full_name_record_token_generation_uid_or_set_change_is_rejected(self):
        for before,after in [('startSeq=7','startSeq=8'),('ProcessRecord{c ','ProcessRecord{d '),(ISOLATED,ISOLATED[:-1]+'0'),('packageList={'+PACKAGE+'}','packageList={other.app}')]:
            self.rejected(lambda r:r['after'].update(amRaw=r['after']['amRaw'].replace(before,after)))

    def test_meminfo_full_name_is_not_a_prefix_or_an_owner_credential(self):
        self.rejected(lambda r:r['processes'][1].update(rawMeminfo=r['processes'][1]['rawMeminfo'].replace(ISOLATED,ISOLATED[:-1]+'0')),'full process name')
        self.rejected(lambda r:r['before'].update(amRaw=''),'ActivityManager')
        self.rejected(lambda r:r['before'].update(amRaw=r['before']['amRaw']+'  *APP* UID 1 malformed\n'),'unparsed')

    def test_truncation_without_exact_capacity_termination_or_comm_is_rejected(self):
        for raw in ((ISOLATED[:98]+'x').encode(),ISOLATED[:97].encode()+b'\0',ISOLATED[:98].encode()+b'x',b'other.app'+b'\0'*90):
            self.rejected(lambda r:r['processes'][1].update(rawCmdlineBeforeHex=raw.hex()))
        self.rejected(lambda r:r['processes'][0].update(rawCmdlineBeforeHex=(PACKAGE.encode()+b'\0').hex()),'capacity')

    def test_unknown_native_descendant_cannot_disappear_from_total(self):
        self.rejected(lambda r:[r[s].update(psRaw=r[s]['psRaw']+'13 11 10210 libmihomo.so\n')for s in ('before','after')],'coverage')

    def test_missing_duplicate_or_partial_process_observation_is_not_valid_total(self):
        for mutate in (lambda r:r['processes'].pop(),lambda r:r['processes'].append(copy.deepcopy(r['processes'][0])),lambda r:r['processes'][1].update(error='process exited')):
            self.rejected(mutate)

    def test_system_process_startseq_zero_does_not_invalidate_own_am_records(self):
        for side in ('before','after'):
            self.raw[side]['amRaw']+=block(1,'system',1000,owner_uid=1000,packages='android',start_seq=0)
        self.assertTrue(self.evaluate()['available'])

    def test_unstarted_nonowned_processes_can_share_zero_pid_without_hiding_own_failure(self):
        for side in ('before','after'):
            self.raw[side]['amRaw']+=block(0,'other.one',10211,owner_uid=10211,packages='other.one',token='a1',start_seq=0)+block(0,'other.two',10212,owner_uid=10212,packages='other.two',token='a2',start_seq=0)
        self.assertTrue(self.evaluate()['available'])
        for side in ('before','after'):
            self.raw[side]['amRaw']+=block(0,PACKAGE+':pending',10210,token='a3',start_seq=0)
        self.assertFalse(self.evaluate()['available'])

    def test_raw_negative_controls_reject_each_case_without_mutating_original(self):
        for side in ('before','after'):
            self.raw[side]['amRaw']=block(1,'system',1000,owner_uid=1000,packages='android',start_seq=0)+self.raw[side]['amRaw']
        previous=copy.deepcopy(self.raw);cases=M.negative_controls(self.raw,PACKAGE,M.parse_stat,scenarios.pss_value)
        self.assertEqual(self.raw,previous);self.assertEqual(len(cases),6)
        self.assertTrue(all(not c['observed']['available'] and c['derivedRawEvidence']!=previous for c in cases))

    def test_claimed_total_or_generation_cannot_override_raw(self):
        result=self.evaluate();result.update(rawEvidence=self.raw,totalPssKb=0)
        with self.assertRaisesRegex(ValueError,'claimed observation'):M.verify(result,PACKAGE,M.parse_stat,scenarios.pss_value)

    def test_collector_final_stat_is_after_last_status_cmdline_and_retains_actual_reads(self):
        expected=[]
        for side in ('before',):
            expected += [(('shell','cmd','package','list','packages','-U',PACKAGE),self.raw[side]['packageUidRaw']), (('shell','dumpsys','activity','processes'),self.raw[side]['amRaw']), (('shell','ps','-A','-o','PID,PPID,UID,NAME'),self.raw[side]['psRaw'])]
        for row in self.raw['processes']:
            pid=row['pid']
            for field,file in [('rawStatBefore','stat'),('rawStatusBefore','status'),('rawCmdlineBeforeHex','cmdline'),('rawMeminfo',None),('rawStatusAfter','status'),('rawCmdlineAfterHex','cmdline'),('rawStatAfter','stat')]:
                command=('shell','dumpsys','meminfo',str(pid)) if file is None else ('exec-out','cat','/proc/%d/%s'%(pid,file))
                expected.append((command,bytes.fromhex(row[field]) if field.endswith('Hex') else row[field]))
        expected += [(('shell','cmd','package','list','packages','-U',PACKAGE),self.raw['after']['packageUidRaw']), (('shell','dumpsys','activity','processes'),self.raw['after']['amRaw']), (('shell','ps','-A','-o','PID,PPID,UID,NAME'),self.raw['after']['psRaw'])]
        def adb(*args,**kwargs):
            command,value=expected.pop(0);self.assertEqual(args,command);self.assertEqual(kwargs.get('binary',False),isinstance(value,bytes));return value
        result=M.collect(adb,PACKAGE,M.parse_stat,scenarios.pss_value)
        self.assertTrue(result['available'],result);self.assertFalse(expected)
        self.assertEqual(result['rawEvidence']['processes'],self.raw['processes'])

    def test_denied_am_does_not_fall_back_to_dumpsys_or_prefix(self):
        def denied(*args,**kwargs):raise subprocess.CalledProcessError(1,args,output=b'Permission denied')
        result=M.collect(denied,PACKAGE,M.parse_stat,scenarios.pss_value)
        self.assertFalse(result['available']);self.assertIsNone(result['totalPssKb'])
        self.assertEqual(result['rawEvidence']['collectionErrorRaw'],'Permission denied')


if __name__=='__main__':unittest.main()
