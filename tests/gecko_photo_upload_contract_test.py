"""Host decoder/receiver controls only; these fixtures are not Android evidence."""
import copy
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import photo_upload_contract as contract
import integration_event_contract as transfer


def png(pixels, filter_type=0, width=contract.WIDTH, height=contract.HEIGHT):
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    stride = width*4
    previous = bytes(stride)
    rows = bytearray()
    for y in range(height):
        row = pixels[y*stride:(y+1)*stride]
        rows.append(filter_type)
        for i,value in enumerate(row):
            left = row[i-4] if i>=4 else 0
            up = previous[i]
            upper_left = previous[i-4] if i>=4 else 0
            if filter_type==4:
                p=left+up-upper_left
                options=[(abs(p-left),left),(abs(p-up),up),(abs(p-upper_left),upper_left)]
                predictor=min(enumerate(options),key=lambda item:(item[1][0],item[0]))[1][1]
            else: predictor=(0,left,up,(left+up)//2)[filter_type]
            rows.append((value-predictor)&255)
        previous=row
    return contract.PNG_SIGNATURE+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(rows),9))+chunk(b'IEND',b'')


def multipart(raw, filename='photo-123.png', mime='image/png'):
    boundary='controlled-photo-boundary-216'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode())
    return 'multipart/form-data; boundary='+boundary,body


def identity():
    return dict(schema=1,package='local.pocketchat.test',sourceCommit='a'*40,sourceTree='b'*40,
                dirtySource=False,version='1.7.0',versionCode=52,sdkCoordinate=transfer.SDK_COORDINATE,
                apkSha256='c'*64,apkBytes=100,buildStampSha256='d'*64)


def native(case):
    value=dict(nativePrivacyReady=True,nativePrivacyLevel=case['privacyLevel'],
               nativeFingerprintingProtected=case['privacyLevel']==2,
               photoEvidence={key:copy.deepcopy(case[key]) for key in ('runNonce','command','privacyLevel','mode','receipts')})
    value['photoEvidence']['schema']=1
    if case['mode']=='select':
        value.update({key:True for key in ('productionChooserOpened','imageMimeAndMultiple','pendingPreserved','noPhantomUpload','desktop')})
        value['upload']='ok:photo-123.png:image/png:64x48'
    else:value.update(chooserOpened=False,upload='protected:no-selection')
    return value


def packets(case, result):
    # In-memory forged packets are parser controls only. They are never saved
    # or offered as actual device evidence.
    kind='desktopImage' if case['mode']=='select' else 'photoProtectionProbe'
    context='environment-'+str(case['processSlot']+1)
    event=dict(kind=kind,result=result,nativeContext=context,processSlot=case['processSlot'])
    envelope=dict(schema=1,sourceCommit=identity()['sourceCommit'],buildIdentity=identity(),
                  runNonce=case['runNonce'],fixtureAction=case['fixtureAction'],command=case['command'],
                  sequence=1,nativeContext=context,processSlot=case['processSlot'],event=event)
    raw=json.dumps(envelope,separators=(',',':'))+'\n'
    receipt={key:envelope[key] for key in ('schema','runNonce','fixtureAction','command','sequence','nativeContext','processSlot')}
    receipt.update(kind='eventReceipt',eventKind=kind,payloadBytes=len(raw.encode()),payloadSha256=contract.digest(raw.encode()))
    return [dict(receipt=receipt,rawUtf8=raw)]


def native_photo_poll_scripts(target):
    """Use both actual Java call-site expressions, not a copied readback helper."""
    scripts={}
    for name in ('GeckoIntegrationTestActivity.java','GeckoPhotoProtectionProbe.java'):
        lines=[line for line in (ROOT/'tests/gecko'/name).read_text().splitlines()
               if 'evaluateJavascript(' in line and 'photoEvidence:' in line]
        if len(lines)!=1:raise AssertionError('One native photo poll expression required: '+name)
        match=re.fullmatch(r'\s*session\.web\.evaluateJavascript\((".*?")\+JSONObject\.quote\(target\)\+(".*"),raw->\{',lines[0])
        if match is None:raise AssertionError('Native poll Java string structure differs: '+name)
        scripts[name]=json.loads(match[1])+json.dumps(target)+json.loads(match[2])
    return scripts


REALM_CONTROL=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
(async()=>{
 const outcomes=[];
 for(const mode of ['select','probe']){
  const config={schema:1,runNonce:'8'.repeat(32),command:7,privacyLevel:1,mode};
  const nodes={upload:{},'upload-result':{textContent:''},'photo-evidence':{textContent:'null'}};
  const document={documentElement:{dataset:{}},getElementById:id=>nodes[id]||null,
   createElement:tag=>{assert.equal(tag,'canvas');return {getContext:()=>({drawImage(){}}),toBlob:callback=>callback({}),toDataURL:()=> 'data:image/png;base64,AAAA'}}};
  const receipts=[];
  const page={window:{},document,URLSearchParams,FormData:class{append(){}},
   createImageBitmap:async()=>({width:64,height:48,close(){}}),
   fetch:async(url,options)=>{
    if(options?.method==='POST'){
     const phase=new URL(url,'http://fixture').searchParams.get('phase');
     const receipt={schema:1,runNonce:config.runNonce,command:7,processSlot:0,phase,
      sha256:'a'.repeat(64),rgbaSha256:'b'.repeat(64),exactPixels:true};
     receipts.push(receipt);return {ok:true,json:async()=>JSON.parse(JSON.stringify(receipt))};
    }
    return {ok:true,blob:async()=>({})};
   }};
  vm.createContext(page);
  const executable=input.html.match(/<script>\s*([\s\S]*?)<\/script>/)[1].replace('__PHOTO_CONFIG__',JSON.stringify(config));
  vm.runInContext(executable,page);
  for(let i=0;i<30&&!document.documentElement.dataset.photoReady&&!nodes['upload-result'].textContent;i++)await new Promise(setImmediate);
  if(mode==='select')await nodes.upload.onchange({target:{files:[{name:'photo-123.png',type:'image/png'}]}});
  else assert.equal(nodes['upload-result'].textContent,'protected:no-selection');
  assert.equal(receipts.length,mode==='select'?5:2);
  assert.equal(page.window.photoEvidence.receipts.length,receipts.length);
  const isolated={window:{},document,location:{href:input.target}};vm.createContext(isolated);
  assert.equal(vm.runInContext('window.photoEvidence||null',isolated),null,'old expando read must reproduce the failure');
  for(const [name,script] of Object.entries(input.scripts)){
   const actual=JSON.parse(JSON.stringify(vm.runInContext(script,isolated)));
   assert.deepEqual(actual.photoEvidence,{...config,receipts});
   const node=nodes['photo-evidence'];delete nodes['photo-evidence'];
   assert.equal(vm.runInContext(script,isolated).photoEvidence,null,'missing evidence must not be reconstructed');
   nodes['photo-evidence']=node;const saved=node.textContent;node.textContent='{broken';
   assert.throws(()=>vm.runInContext(script,isolated),/JSON|property|Unexpected|Expected/);
   node.textContent=saved;outcomes.push({mode,reader:name,receipts:receipts.length});
  }
 }
 console.log(JSON.stringify({status:'passed',modelOnly:true,actualBrowserExecution:false,outcomes}));
})().catch(error=>{console.error(error);process.exitCode=1});
'''


class PhotoUploadContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        no_fetch=patch.dict(os.environ,{'GIT_NO_LAZY_FETCH':'1'})
        no_fetch.start();cls.addClassCleanup(no_fetch.stop)
        cls.original=(ROOT/'tests/gecko/assets/photo-upload-pattern.png').read_bytes()
        cls.pixels=contract.expected_rgba()
        cls.solid=png(bytes([42,73,101,255])*(contract.WIDTH*contract.HEIGHT))

    def test_actual_provider_asset_has_all_expected_pixels_and_transparency(self):
        self.assertEqual(hashlib.sha256(self.original).hexdigest(),contract.FIXTURE_SHA256)
        self.assertEqual(contract.decode_png(self.original),self.pixels)
        observed=contract.inspect_png(self.original,expected_match=True,original=True)
        self.assertEqual(observed['distinctRgbaColors'],3072)
        self.assertEqual(self.pixels[:4],b'\x00'*4)
        self.assertEqual(observed['pixelCount'],3072)
        provider=(ROOT/'tests/gecko/GeckoUploadFixtureProvider.java').read_text()
        self.assertIn('open("photo-upload-pattern.png")',provider)
        self.assertIn('?10320:16',provider)
        self.assertNotIn('eraseColor',provider)

    def test_every_png_filter_decodes_full_rgba_independently(self):
        for value in range(5):
            with self.subTest(filter=value):
                self.assertEqual(contract.decode_png(png(self.pixels,value)),self.pixels)

    def test_solid_color_one_pixel_and_channel_corruption_fail_selected_photo(self):
        altered=bytearray(self.pixels);altered[-2]^=1
        shifted=bytes(channel for i in range(0,len(self.pixels),4) for channel in (self.pixels[i+1],self.pixels[i],self.pixels[i+2],self.pixels[i+3]))
        for raw in (self.solid,png(bytes(altered)),png(shifted)):
            with self.subTest(sha256=contract.digest(raw)),self.assertRaises(AssertionError):
                contract.inspect_png(raw,expected_match=True)

    def test_protection_receipt_requires_different_pixels(self):
        observed=contract.inspect_png(self.solid,expected_match=False)
        self.assertFalse(observed['exactPixels'])
        with self.assertRaises(AssertionError):contract.inspect_png(self.original,expected_match=False)
        with self.assertRaises(AssertionError):contract.inspect_png(self.solid,expected_match=False,original=True)

    def test_exact_file_bytes_and_reencoded_pixels_have_distinct_requirements(self):
        reencoded=png(self.pixels,1)
        self.assertNotEqual(reencoded,self.original)
        contract.inspect_png(reencoded,expected_match=True)
        with self.assertRaises(AssertionError):contract.inspect_png(reencoded,expected_match=True,original=True)

    def test_malformed_trailing_crc_dimensions_and_truncated_png_fail(self):
        corrupt=bytearray(self.original);corrupt[50]^=1
        changed_size=png(bytes([1,2,3,255])*(32*48),width=32,height=48)
        for raw in (b'',contract.PNG_SIGNATURE,self.original[:-1],self.original+b'garbage',bytes(corrupt),changed_size,self.original*15):
            with self.subTest(length=len(raw)),self.assertRaises(AssertionError):contract.decode_png(raw)

    def test_multipart_requires_one_exact_image_part(self):
        content_type,body=multipart(self.original)
        self.assertEqual(contract.multipart_image(content_type,body),self.original)
        for mime,raw in (multipart(self.original,filename='other.png'),multipart(self.original,mime='application/octet-stream'),
                         (content_type,body[:-6]),('image/png',self.original),(content_type+'\r\nInjected: x',body)):
            with self.subTest(mime=mime),self.assertRaises((AssertionError,ValueError)):
                contract.multipart_image(mime,raw)

    def ledger(self,directory,index=0):
        ledger=contract.PhotoUploadLedger(directory,identity())
        name,slot,level,mode,action=contract.CASES[index]
        nonce=f'{index+1:032x}'
        ledger.register(name,nonce,slot,level,mode,action)
        ledger.document(nonce,index+1,level,mode)
        return ledger,nonce

    def fill(self,ledger,nonce):
        case=ledger.cases[nonce]
        for phase in contract.phases(case['mode']):
            raw=self.solid if phase in contract.UNSELECTED and case['privacyLevel']==2 else self.original
            content_type,body=multipart(raw)
            ledger.receive(nonce,case['command'],phase,content_type,body)
        result=native(case);ledger.complete(nonce,result,packets(case,result))

    def test_receiver_rejects_unregistered_stale_duplicate_or_reordered_images(self):
        content_type,body=multipart(self.original)
        for kind in ('unregistered','stale','out-of-order','duplicate'):
            with tempfile.TemporaryDirectory() as directory:
                ledger,nonce=self.ledger(directory)
                if kind=='duplicate':ledger.receive(nonce,1,contract.UNSELECTED[0],content_type,body)
                with self.subTest(kind=kind),self.assertRaises(AssertionError):
                    ledger.receive('f'*32 if kind=='unregistered' else nonce,2 if kind=='stale' else 1,
                                   'original' if kind=='out-of-order' else contract.UNSELECTED[0],content_type,body)

    def test_native_json_cannot_replace_original_receiver_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger,nonce=self.ledger(directory)
            with self.assertRaises(AssertionError):ledger.complete(nonce,native(ledger.cases[nonce]),[])
            self.fill(ledger,nonce)
            good=native(ledger.cases[nonce])
            missing=copy.deepcopy(good);missing.pop('photoEvidence')
            with self.assertRaises(AssertionError):ledger.complete(nonce,missing,packets(ledger.cases[nonce],missing))
            for key in ('nativePrivacyReady','pendingPreserved','productionChooserOpened'):
                altered=copy.deepcopy(good);altered[key]=False
                with self.subTest(key=key),self.assertRaises(AssertionError):ledger.complete(nonce,altered,packets(ledger.cases[nonce],altered))
            altered=copy.deepcopy(good);altered['photoEvidence']['receipts'][0]['sha256']='0'*64
            with self.assertRaises(AssertionError):ledger.complete(nonce,altered,packets(ledger.cases[nonce],altered))
            records=packets(ledger.cases[nonce],good);records[0]['rawUtf8']+=' '
            with self.assertRaises(ValueError):ledger.complete(nonce,good,records)
            records=packets(ledger.cases[nonce],good);records[0]['receipt']['command']+=1
            with self.assertRaises(ValueError):ledger.complete(nonce,good,records)
            records=packets(ledger.cases[nonce],good);records[0]['receipt']['processSlot']=1
            with self.assertRaises(ValueError):ledger.complete(nonce,good,records)
            with self.assertRaises(AssertionError):ledger.complete(nonce,good,[])

    def test_publication_redecodes_every_retained_image_and_requires_all_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=contract.PhotoUploadLedger(directory,identity())
            for index,(name,slot,level,mode,action) in enumerate(contract.CASES,1):
                nonce=f'{index:032x}';ledger.register(name,nonce,slot,level,mode,action);ledger.document(nonce,index,level,mode)
                self.fill(ledger,nonce)
            report=ledger.report()
            observed=contract.verify_photo_upload_evidence(directory,identity()['sourceCommit'],report)
            self.assertEqual((observed['cases'],observed['images']),(8,28))
            changed=copy.deepcopy(report);changed['cases'].pop()
            with self.assertRaises(AssertionError):contract.verify_photo_upload_evidence(directory,identity()['sourceCommit'],changed)
            original=next(r for r in report['cases'][0]['receipts'] if r['phase']=='original')
            (Path(directory)/original['file']).write_bytes(self.solid)
            with self.assertRaises(AssertionError):contract.verify_photo_upload_evidence(directory,identity()['sourceCommit'],report)

    def test_page_uses_two_real_exports_and_defers_chooser_until_receiver_baseline(self):
        page=(ROOT/'tests/gecko/assets/photo-upload-fixture.html').read_text()
        self.assertIn('canvas.toBlob(',page);self.assertIn("canvas.toDataURL('image/png')",page)
        self.assertIn("await submit('original', file)",page)
        self.assertNotIn('getImageData',page)
        self.assertLess(page.index("await encoded(await canvasFor(await response.blob()), 'unselected-')"),
                        page.rindex("dataset.photoReady = 'true'"))

    def test_both_native_readers_obtain_exact_receipts_across_isolated_realms(self):
        target='http://fixture/browser-image?command=7&nonce='+'8'*32
        payload=dict(target=target,scripts=native_photo_poll_scripts(target),
                     html=(ROOT/'tests/gecko/assets/photo-upload-fixture.html').read_text())
        result=subprocess.run(['node','-e',REALM_CONTROL],input=json.dumps(payload),text=True,
                              capture_output=True,check=True,timeout=15)
        observed=json.loads(result.stdout)
        self.assertEqual(observed['status'],'passed')
        self.assertEqual(len(observed['outcomes']),4)

    def test_actual_http_fixture_keeps_receiver_validation_in_the_request_path(self):
        spec=importlib.util.spec_from_file_location('actual_photo_device_runner',ROOT/'tests/gecko/run_device.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as directory:
            ledger=contract.PhotoUploadLedger(directory,identity())
            name,slot,level,mode,action=contract.CASES[0];nonce='d'*32
            ledger.register(name,nonce,slot,level,mode,action)
            runner.Fixture.photo_ledger=ledger
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),runner.Fixture)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            try:
                with urllib.request.urlopen(base+'/browser-image?nonce='+nonce+'&command=7&privacy=1&mode=select',timeout=3) as response:
                    self.assertIn(nonce.encode(),response.read())
                content_type,body=multipart(self.original)
                endpoint=base+'/image-received?nonce='+nonce+'&command=7&phase=unselected-to-blob'
                request=urllib.request.Request(endpoint,data=body,headers={'Content-Type':content_type},method='POST')
                with urllib.request.urlopen(request,timeout=3) as response:
                    received=json.load(response)
                self.assertEqual(received['rgbaSha256'],contract.digest(self.pixels))
                bad_type,bad_body=multipart(self.solid)
                bad=urllib.request.Request(base+'/image-received?nonce='+nonce+'&command=7&phase=unselected-to-data-url',data=bad_body,headers={'Content-Type':bad_type},method='POST')
                with self.assertRaises(urllib.error.HTTPError) as raised:urllib.request.urlopen(bad,timeout=3)
                self.assertEqual(raised.exception.code,422)
                self.assertEqual(len(ledger.cases[nonce]['receipts']),1)
                self.assertEqual(len(ledger.cases[nonce]['errors']),1)
                failure=ledger.cases[nonce]['errors'][0]
                self.assertEqual((Path(directory)/failure['file']).read_bytes(),self.solid)
                self.assertEqual(failure['sha256'],contract.digest(self.solid))
            finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':unittest.main(verbosity=2)
