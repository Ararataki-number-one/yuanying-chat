"""Fail-closed historical projection after the exact reviewed31 addition.

Run the real download-names main through its four original preservation guards.
The compile boundary is a sentinel; these tests do not claim JVM or Android work.
Independent immutable historical hashes avoid a new shallow-checkout dependency.
"""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'tests/download-names-host/run.py'
PROD=ROOT/'app/src/main/java/local/pocketchat'
spec=importlib.util.spec_from_file_location('actual_download_names_compat',RUNNER)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
START='  /** A confirmation belongs to the exact environment shown in its dialog. */\n'
END='  void beginDelete(int slot)'
HISTORICAL_CATALOG_SHA='862e188b47ada1bacb2c753519f6a48fae11ec09190a3e4ada1f8ddddfa94ac2'
HISTORICAL_DOWNLOADS_SHA='321551512da371ae6d572acf1777c154012d476c0f92ac42acfe9cf3accb9984'


class CompilationReached(Exception):pass


class DownloadNamesCatalogCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_current=(PROD/'ProfileCatalog.java').read_text()
        cls.current=runner.remove_reviewed46(cls.raw_current,'ProfileCatalog.java')
        begin=cls.current.index(START);finish=cls.current.index(END,begin+len(START))
        cls.block=cls.current[begin:finish]
        assert len(cls.block.encode())==1579
        assert hashlib.sha256(cls.block.encode()).hexdigest()=='5e961abfcccae702bc026b4664063afa1a783be04514cdd499b906c8fd7d8811'
        old=cls.current[:begin]+cls.current[finish:]
        names=runner.member(old,'Map<Integer,String> names()')
        display=runner.member(old,'static String displayName(')
        cls.baseline_catalog=old.replace('  /** Refresh-local labels only; do not load private drafts/notes or cache across renames. */\n','').replace('  '+names+'\n','').replace('  '+display+'\n','')
        assert hashlib.sha256(cls.baseline_catalog.encode()).hexdigest()==HISTORICAL_CATALOG_SHA
        downloads=runner.remove_reviewed38((PROD/'DesignDownloads.java').read_text())
        apply=runner.member(downloads,'void apply(JSONArray data,')
        bind=runner.member(downloads,'void bind(JSONObject row,')
        old_apply=apply.replace('Map<Integer,String> environmentNames=null;','').replace('if(environmentNames==null)environmentNames=ProfileCatalog.get(a).names();','').replace('row.bind(value,now,ProfileCatalog.displayName(environmentNames,value.optInt("slot")));','row.bind(value,now);')
        old_bind=bind.replace('void bind(JSONObject row,long now,String environmentName)','void bind(JSONObject row,long now)').replace('text(status,environmentName+','text(status,Profiles.display(a,row.optInt("slot"))+')
        cls.baseline_downloads=downloads.replace(apply,old_apply).replace(bind,old_bind)
        assert hashlib.sha256(cls.baseline_downloads.encode()).hexdigest()==HISTORICAL_DOWNLOADS_SHA

    def guards_reach_compile(self,catalog,downloads=None):
        original_read=Path.read_bytes
        def read(path):
            if path==PROD/'ProfileCatalog.java':return catalog.encode()
            if path==PROD/'DesignDownloads.java' and downloads is not None:return downloads.encode()
            return original_read(path)
        def historical(args,**kwargs):
            self.assertEqual(args[:2],['git','show'])
            if args[2]==runner.BASELINE+':app/src/main/java/local/pocketchat/ProfileCatalog.java':return self.baseline_catalog.encode()
            if args[2]==runner.BASELINE+':app/src/main/java/local/pocketchat/DesignDownloads.java':return self.baseline_downloads.encode()
            raise AssertionError('Unexpected external command at the preservation boundary')
        argv=[str(RUNNER),'--java-home','/unused/jdk','--json-jar','/unused/json.jar','--output','/unused/report.json']
        with mock.patch.object(Path,'read_bytes',read),mock.patch.object(runner.subprocess,'check_output',side_effect=historical),mock.patch.object(runner.subprocess,'run',side_effect=CompilationReached),mock.patch.object(sys,'argv',argv):
            runner.main()

    def test_exact_addition_retains_all_four_original_guards(self):
        with self.assertRaises(CompilationReached):self.guards_reach_compile(self.current)
        self.assertEqual(runner.remove_reviewed_delete_identity(self.current),self.current.replace(self.block,'',1))

    def test_exact_reviewed46_catalog_invalidation_reaches_original_guards(self):
        with self.assertRaises(CompilationReached):self.guards_reach_compile(self.raw_current)

    def test_changed_reviewed46_catalog_hook_is_rejected(self):
        changed=self.raw_current.replace('DownloadLibrary.changed(root);','DownloadLibrary.changed(null);',1)
        with self.assertRaisesRegex(AssertionError,'Reviewed46 bounded edit'):self.guards_reach_compile(changed)

    def test_legacy_catalogue_method_mutation_is_still_rejected(self):
        needle='String name(int slot){return item(slot).optString("name",slot==0?"默认环境":"环境 "+(slot+1));}'
        self.assertEqual(self.current.count(needle),1)
        mutated=self.current.replace(needle,needle.replace('"默认环境"','"unexpected-label-drift"'),1)
        with self.assertRaisesRegex(AssertionError,'allExistingCatalogBytes'):
            self.guards_reach_compile(mutated)

    def test_appended_api_body_mutation_is_rejected(self):
        mutated=self.current.replace('if(expected==null)throw new java.io.IOException("删除环境身份无效");','if(expected!=null)throw new java.io.IOException("删除环境身份无效");',1)
        self.assertNotEqual(mutated,self.current)
        with self.assertRaisesRegex(AssertionError,'Reviewed deletion addition bytes changed'):
            self.guards_reach_compile(mutated)

    def test_duplicate_addition_is_rejected(self):
        mutated=self.current.replace(self.block,self.block+self.block,1)
        with self.assertRaisesRegex(AssertionError,'exactly once'):self.guards_reach_compile(mutated)

    def test_mismatched_addition_digest_is_rejected(self):
        with mock.patch.object(runner,'digest',return_value='0'*64):
            with self.assertRaisesRegex(AssertionError,'Reviewed deletion addition bytes changed'):
                self.guards_reach_compile(self.current)

    def test_missing_addition_is_rejected(self):
        with self.assertRaisesRegex(AssertionError,'exactly once'):
            self.guards_reach_compile(self.current.replace(self.block,'',1))

    def test_changed_marker_or_whitespace_is_rejected(self):
        for changed in [self.current.replace(START,START.replace('confirmation','permission'),1),self.current.replace(self.block,self.block+'\n',1)]:
            with self.subTest(changed=hashlib.sha256(changed.encode()).hexdigest()):
                with self.assertRaises(AssertionError):self.guards_reach_compile(changed)

    def test_original_download_ui_guard_still_rejects_unrelated_drift(self):
        original=(PROD/'DesignDownloads.java').read_text()
        changed=original.replace('package local.pocketchat;','package local.pocketchat;\n// unrelated drift',1)
        with self.assertRaisesRegex(AssertionError,'allOtherDownloadUiBytes'):
            self.guards_reach_compile(self.current,changed)


if __name__=='__main__':unittest.main()
