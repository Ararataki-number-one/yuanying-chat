"""Rejection controls for original download fixture receipts; no Android execution."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
capture=importlib.import_module('capture_download_workspace')
invocation=importlib.import_module('profile_invocation_contract')
from profile_sdk_identity_test import fixture as sdk_fixture, sdk

NONCE,RUN='1'*32,'2'*32


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()


def body(mode='populated'):
    rows,files,partials=[],[],[]
    if mode=='populated':
        for index,name in enumerate(capture.FILENAMES):
            slot=(2,0,1,3,4)[index]
            row=dict(slot=slot,id=f'00000000-0000-4000-8000-{index:012d}',name=name,
                     environmentId=f'11111111-1111-4111-8111-{slot:012d}',environmentGeneration=0,
                     state='paused' if index==0 else 'failed' if index==1 else 'saved')
            if row['state']=='saved':
                row.update(uri=f'content://{capture.PACKAGE}.saved-downloads/{slot}/{row["id"]}/{quote(name,safe="")}',savedBytes=12)
                files.append(dict(id=row['id'],name=name,slot=slot,uri=row['uri'],bytes=12,sha256='a'*64,readable=True))
            elif row['state']=='paused':
                row.update(received=8,total=24)
                partials.append(dict(id=row['id'],name=name,slot=slot,bytes=8,sha256='b'*64))
            rows.append(row)
    return dict(status='ready',mode=mode,parentRunNonce=RUN,actualProductionActivity=capture.ACTIVITY,
                syntheticFixture=True,syntheticTaskMetadata=True,actualNetworkTransfer=False,
                recordCount=len(rows),savedCount=len(files),pausedCount=len(partials),
                failedCount=1 if rows else 0,activeTransferCount=0,rows=rows,savedFiles=files,partialFiles=partials)


class DownloadFixtureReceiptTests(unittest.TestCase):
    def setUp(self):
        *_,self.identity,_=sdk_fixture()
        self.reader=sdk_fixture()[2]
        self.sdk=patch.object(invocation._sdk,'verify_sdk_identity',
            side_effect=lambda value,*args,**kwargs:sdk.verify_sdk_identity(value,*args,reader=self.reader,**kwargs))
        self.sdk.start();self.addCleanup(self.sdk.stop)
        self.payload=dict(schema=1,sourceCommit=self.identity['sourceCommit'],buildIdentity=copy.deepcopy(self.identity),
            runNonce=NONCE,fixtureAction='download-workspace',command=1,sequence=1,nativeContext='environment-1',processSlot=0,
            observedAtElapsedRealtime=9,event=dict(kind='downloadWorkspaceFixture',nativeContext='environment-1',processSlot=0,result=body()))

    def journal(self,raw):
        receipt=dict(kind='eventReceipt',schema=1,runNonce=NONCE,fixtureAction='download-workspace',command=1,sequence=1,
            nativeContext='environment-1',processSlot=0,eventKind='downloadWorkspaceFixture',payloadBytes=len(raw),
            payloadSha256=hashlib.sha256(raw).hexdigest())
        return dict(schema=1,status='committed',runNonce=NONCE,processSlot=0,fixtureAction='download-workspace',command=1,
                    receipts=[json.dumps(receipt)])

    def verify(self,payload=None,journal=None,raw=None,mode='populated'):
        raw=encoded(self.payload if payload is None else payload) if raw is None else raw
        return capture.verify_fixture(raw,encoded(self.journal(raw) if journal is None else journal),
            identity=self.identity,nonce=NONCE,run_nonce=RUN,command=1,mode=mode)

    def rejected(self,change):
        value=copy.deepcopy(self.payload);change(value)
        with self.assertRaises((ValueError,KeyError,TypeError)):self.verify(value)

    def test_real_file_and_partial_schema_accepts_complete_owned_receipt(self):
        value=self.verify();self.assertEqual(value['savedCount'],3);self.assertEqual(value['activeTransferCount'],0)

    def test_empty_library_requires_empty_rows_and_both_file_lists(self):
        value=copy.deepcopy(self.payload);value['event']['result']=body('empty')
        self.assertEqual(self.verify(value,mode='empty')['recordCount'],0)
        value['event']['result']['savedFiles']=[{}]
        with self.assertRaises(ValueError):self.verify(value,mode='empty')

    def test_foreign_source_tree_apk_and_sdk_receipts_fail(self):
        for key,changed in (('sourceCommit','c'*40),('sourceTree','d'*40),('apkSha256','c'*64),('dirtySource',True)):
            with self.subTest(field=key):self.rejected(lambda p,k=key,v=changed:p['buildIdentity'].__setitem__(k,v))
        self.rejected(lambda p:p['buildIdentity']['sdkBuildIdentity'].__setitem__('sdkAarSha256','0'*64))

    def test_wrong_nonce_parent_command_sequence_context_and_mode_fail(self):
        for key,value in (('runNonce','3'*32),('command',2),('command',True),('sequence',2),('processSlot',1),('nativeContext','environment-2')):
            with self.subTest(field=key,value=value):self.rejected(lambda p,k=key,v=value:p.__setitem__(k,v))
        for key,value in (('parentRunNonce','4'*32),('mode','empty'),('actualProductionActivity','fixture-only')):
            with self.subTest(field=key):self.rejected(lambda p,k=key,v=value:p['event']['result'].__setitem__(k,v))

    def test_missing_duplicate_pending_and_forged_journal_fail(self):
        raw=encoded(self.payload)
        for change in (lambda j:j.update(status='pending'),lambda j:j.update(receipts=[]),
                       lambda j:j['receipts'].append(j['receipts'][0]),lambda j:j.update(runNonce='4'*32),
                       lambda j:j.update(command=2)):
            journal=self.journal(raw);change(journal)
            with self.subTest(journal=journal),self.assertRaises(ValueError):self.verify(journal=journal,raw=raw)
        journal=self.journal(raw);receipt=json.loads(journal['receipts'][0]);receipt['payloadSha256']='0'*64;journal['receipts']=[json.dumps(receipt)]
        with self.assertRaises(ValueError):self.verify(journal=journal,raw=raw)

    def test_original_payload_bytes_are_bound_without_reserializing(self):
        raw=encoded(self.payload);journal=self.journal(raw)
        with self.assertRaises(ValueError):self.verify(journal=journal,raw=raw+b' ')
        duplicated=raw.replace(b'"schema":1',b'"schema":1,"schema":1',1)
        with self.assertRaises(ValueError):self.verify(raw=duplicated)

    def test_synthetic_scope_cannot_be_promoted_to_live_download(self):
        for key,value in (('syntheticFixture',False),('syntheticTaskMetadata',False),('actualNetworkTransfer',True),
                          ('activeTransferCount',1)):
            with self.subTest(field=key):self.rejected(lambda p,k=key,v=value:p['event']['result'].__setitem__(k,v))
        self.rejected(lambda p:p['event']['result']['rows'][0].__setitem__('state','downloading'))

    def test_miscount_duplicate_names_and_unbound_environment_fail(self):
        for change in (lambda v:v.update(recordCount=6),lambda v:v.update(savedCount=True),
                       lambda v:v['rows'][1].update(name=capture.PAUSED),lambda v:v['rows'][0].update(environmentId=''),
                       lambda v:v['rows'][0].update(environmentGeneration=-1),lambda v:v['rows'][0].update(slot=7)):
            self.rejected(lambda p,c=change:c(p['event']['result']))

    def test_saved_proofs_require_exact_owned_uri_and_matching_size(self):
        for change in (lambda f:f.update(uri='file:///unrelated.pdf'),lambda f:f.update(readable=False),
                       lambda f:f.update(bytes=13),lambda f:f.update(bytes=0),lambda f:f.update(slot=0),
                       lambda f:f.update(sha256='x'*64),lambda f:f.update(id='foreign')):
            self.rejected(lambda p,c=change:c(p['event']['result']['savedFiles'][0]))

    def test_paused_progress_must_match_actual_partial_proof(self):
        for change in (lambda f:f.update(bytes=9),lambda f:f.update(bytes=0),lambda f:f.update(name=capture.FAILED),
                       lambda f:f.update(id='foreign'),lambda f:f.update(sha256='not-a-digest')):
            self.rejected(lambda p,c=change:c(p['event']['result']['partialFiles'][0]))
        self.rejected(lambda p:p['event']['result']['rows'][0].update(total=8))


class DownloadHierarchyTests(unittest.TestCase):
    def node(self,**fields):
        values={'package':capture.PACKAGE,'class':'android.widget.TextView','text':capture.SAVED[0],
                'bounds':'[60,500][1050,580]','visible-to-user':'true'}
        values.update(fields);return values

    def xml(self,*nodes):
        root=ET.Element('hierarchy')
        for values in nodes:ET.SubElement(root,'node',values)
        return ET.tostring(root,encoding='unicode')

    def test_file_positions_use_real_visible_app_text_nodes(self):
        xml=self.xml(self.node(),self.node(**{'class':'android.widget.Button','text':capture.SAVED[1]}),
                     self.node(**{'package':'other.app','text':capture.PAUSED}),
                     self.node(**{'visible-to-user':'false','text':capture.FAILED}),
                     self.node(text=capture.SAVED[2],bounds='[60,2700][1050,2780]'))
        self.assertEqual(capture.file_positions(xml),[(capture.SAVED[0],(60,500,1050,580))])

    def test_changed_clock_does_not_imply_file_scroll(self):
        first=self.xml(self.node(),self.node(text='11:30',bounds='[20,20][100,80]'))
        second=self.xml(self.node(),self.node(text='11:31',bounds='[20,20][100,80]'))
        self.assertEqual(capture.file_positions(first),capture.file_positions(second))
        moved=self.xml(self.node(bounds='[60,400][1050,480]'))
        self.assertNotEqual(capture.file_positions(first),capture.file_positions(moved))

    def test_selection_requires_one_actual_checked_checkbox(self):
        box=self.node(**{'class':'android.widget.CheckBox','text':'','content-desc':'收集文件 '+capture.SAVED[0],'checked':'true'})
        self.assertTrue(capture.checked_file(self.xml(box),capture.SAVED[0]))
        self.assertFalse(capture.checked_file(self.xml(box,box),capture.SAVED[0]))
        for key,value in (('checked','false'),('visible-to-user','false'),('class','android.widget.TextView'),('package','other.app')):
            changed=dict(box);changed[key]=value
            self.assertFalse(capture.checked_file(self.xml(changed),capture.SAVED[0]))


if __name__=='__main__':unittest.main()
