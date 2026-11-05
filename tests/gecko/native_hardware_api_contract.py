#!/usr/bin/env python3
"""Native-pref bridge authority controls. Models are never Android execution proof."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'tests/gecko/assets/native-hardware-extension'


class NativeHardwareApiContract(unittest.TestCase):
    def test_components_are_registered_only_in_integration(self):
        manifest=ET.parse(ROOT/'tests/gecko/AndroidManifest.xml').getroot()
        android='{http://schemas.android.com/apk/res/android}'
        application=manifest.find('application');self.assertIsNotNone(application)
        activities=[n for n in application.findall('activity') if n.get(android+'name')=='local.pocketchat.NativeHardwareProbeActivity']
        providers=[n for n in application.findall('provider') if n.get(android+'name')=='local.pocketchat.NativeHardwareProbeProvider']
        self.assertEqual(len(activities),1);self.assertEqual(len(providers),1)
        self.assertEqual(activities[0].get(android+'process'),':native_hardware_probe')
        self.assertEqual(providers[0].get(android+'authorities'),'local.pocketchat.test.nativehardware')
        checkout=next(p for p in (ROOT,*ROOT.parents) if (p/'app/src/main/AndroidManifest.xml').is_file())
        self.assertNotIn('NativeHardwareProbe',(checkout/'app/src/main/AndroidManifest.xml').read_text())

    def test_actual_navigation_state_requires_each_owned_document(self):
        source=(ROOT/'tests/gecko/NativeHardwareProbeActivity.java').read_text()
        begin=source.index('  static final class NavigationState {')
        opening=source.index('{',begin);depth=1;end=opening+1
        while depth:
            depth+=int(source[end]=='{')-int(source[end]=='}');end+=1
        actual=source[begin:end]
        # Serialization is separately checked by the strict evidence parser.
        # Compile the actual navigation algorithm without its Android JSON output.
        js=actual.index('    JSONObject json()');jo=actual.index('{',js);depth=1;je=jo+1
        while depth:
            depth+=int(actual[je]=='{')-int(actual[je]=='}');je+=1
        actual=actual[:js]+actual[je:]
        program=r'''
class HardwareNavigationOwnerHost {
ACTUAL
static int checks;
static void ok(boolean value){checks++;if(!value)throw new AssertionError("Ownership check "+checks);}
static NavigationState bootstrap(){NavigationState n=new NavigationState("bootstrap","baseline/probe","baseline/probe",0);
  n.start("bootstrap",1);n.location("bootstrap");n.document("bootstrap");n.stop(true);ok(n.bootstrapReady());return n;}
public static void main(String[] ignored){
  NavigationState n=bootstrap();n.requestProbe();n.start("baseline/probe",2);n.location("baseline/probe");
  n.document("baseline/probe");n.stop(false);ok(!n.probeReady());ok(n.failedStops==1);n.stop(true);ok(n.probeReady());
  n.targetError=true;ok(!n.probeReady());
  n=bootstrap();n.requestProbe();n.start("baseline/probe",2);n.location("baseline/probe");n.stop(true);ok(!n.probeReady());
  n.document("cap2/probe");ok(!n.probeReady());n.document("baseline/probe");ok(n.probeReady());
  n=bootstrap();n.requestProbe();n.start("baseline/probe",2);n.document("baseline/probe");n.stop(true);ok(!n.probeReady());
  n.location("baseline/probe");ok(n.probeReady());n.start("cap2/probe",3);ok(!n.probeReady());
  n=bootstrap();n.requestProbe();n.location("baseline/probe");n.document("baseline/probe");n.stop(true);ok(!n.probeReady());
  for(String phase:new String[]{"cap2","cap1","reset"}){
    n=new NavigationState("bootstrap",phase+"/probe",phase+"/probe",2);n.bootstrapStart=n.bootstrapDocument=n.bootstrapStop=true;
    n.requestProbe();n.start("baseline/probe",3);n.location("baseline/probe");n.document("baseline/probe");n.stop(true);ok(!n.probeReady());
    n.start(phase+"/probe",4);n.location(phase+"/probe");n.document(phase+"/probe");n.stop(true);ok(n.probeReady());
    ok(n.generation==4);
  }
  try{n.requestProbe();throw new AssertionError("Repeated target accepted");}catch(IllegalStateException expected){checks++;}
  System.out.println("actualNavigationChecks="+checks+";actualAndroidExecution=false");
}}
'''.replace('ACTUAL',actual)
        javac=shutil.which('javac');java=shutil.which('java')
        if not (javac and java):
            checkout=next(p for p in (ROOT,*ROOT.parents) if (p/'tools/gecko/profile_invocation_contract.py').is_file())
            candidates=[Path(os.environ.get(key,'/unavailable-jdk'))/'bin' for key in ('JAVA_HOME','JAVA_HOME_17_X64')]
            candidates.append(checkout/'work/browser-ci-jdk/jdk-17.0.21+9/bin')
            selected=next((p for p in candidates if (p/'javac').is_file() and (p/'java').is_file()),None)
            self.assertIsNotNone(selected,'Actual JDK required; no skipped native ownership model')
            javac=str(selected/'javac');java=str(selected/'java')
        with tempfile.TemporaryDirectory(prefix='hardware-navigation-owner-') as directory:
            path=Path(directory)/'HardwareNavigationOwnerHost.java';path.write_text(program)
            ran=subprocess.run([javac,str(path)],capture_output=True,text=True,timeout=20)
            self.assertEqual(ran.returncode,0,ran.stderr)
            ran=subprocess.run([java,'-cp',directory,'HardwareNavigationOwnerHost'],capture_output=True,text=True,timeout=20)
            self.assertEqual(ran.returncode,0,ran.stderr);self.assertIn('actualAndroidExecution=false',ran.stdout)

    def test_privileged_parent_only_manifest(self):
        value=json.loads((ASSETS/'manifest.json').read_text())
        self.assertEqual(value['browser_specific_settings']['gecko']['id'],'hardware-probe@pocketchat.local')
        api=value['experiment_apis']['pocketNativeHardware']
        self.assertEqual(api['parent'],dict(scopes=['addon_parent'],paths=[['pocketNativeHardware']],script='parent.js'))
        self.assertNotIn('debugger',value['permissions'])
        self.assertNotIn('web_accessible_resources',value)
        schema=json.loads((ASSETS/'schema.json').read_text())[0]
        self.assertEqual([row['name'] for row in schema['functions']],['read','setCap','reset'])

    def test_native_preference_and_rfp_boundaries(self):
        program=r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const CPU='dom.maxHardwareConcurrency',RFP='privacy.resistFingerprinting';
const state={value:128,user:false,rfp:false,writes:[],kind:64,readFailure:false,writeFailure:false,ignoreWrite:false,flipRfp:false};
const prefs={getPrefType(key){assert.equal(key,CPU);return state.kind;},
  getIntPref(key){assert.equal(key,CPU);if(state.readFailure)throw Error('secret');return state.value;},
  prefHasUserValue(key){assert.equal(key,CPU);return state.user;},
  getBoolPref(key,fallback){assert.equal(key,RFP);assert.equal(fallback,false);return state.rfp;},
  setIntPref(key,value){assert.equal(key,CPU);state.writes.push(['set',key,value]);if(state.writeFailure)throw Error('secret');
    if(!state.ignoreWrite){state.value=value;state.user=true;}if(state.flipRfp)state.rfp=false;},
  clearUserPref(key){assert.equal(key,CPU);state.writes.push(['clear',key]);if(state.writeFailure)throw Error('secret');
    state.value=128;state.user=false;}};
const sandbox=vm.createContext({Cc:{'@mozilla.org/preferences-service;1':{getService(){return prefs;}}},Ci:{nsIPrefBranch:{PREF_INT:64}},
  ChromeUtils:{importESModule(){return {ExtensionCommon:{ExtensionAPI:class{}},ExtensionUtils:{ExtensionError:Error}};}}});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),sandbox);
function api(changes={},envType='addon_parent'){return new sandbox.pocketNativeHardware().getAPI({envType,
  extension:{id:'hardware-probe@pocketchat.local',isPrivileged:true,...changes}}).pocketNativeHardware;}
const control=api();let checks=0;
const baseline=await control.read('baseline-apply');
assert.equal(baseline.configuredCap,128);assert.equal(baseline.hasUserValue,false);assert.equal(baseline.requestedCap,null);checks++;
for(const cap of [2,1]){const receipt=await control.setCap(cap,'cap'+cap+'-apply');
  assert.equal(receipt.configuredCap,cap);assert.equal(receipt.hasUserValue,true);assert.equal(receipt.requestedCap,cap);
  assert.equal(receipt.status,'applied');assert.equal(receipt.nativePreferenceReadback,true);
  assert.equal(receipt.workerCoverageVerified,false);assert.equal(receipt.fingerprintProtectionVerified,false);checks++;}
const reset=await control.reset('reset-apply');assert.equal(reset.status,'reset');assert.equal(reset.configuredCap,128);
assert.equal(reset.hasUserValue,false);assert.equal(reset.requestedCap,null);checks++;
async function noWrite(action,pattern){const n=state.writes.length;await assert.rejects(action,pattern);assert.equal(state.writes.length,n);checks++;}
for(const value of [0,3,-1,NaN,Infinity,true,'1',null])await noWrite(control.setCap(value,'bad-cap'),/invalid-hardware-cap/);
for(const value of ['', 'bad token','x'.repeat(161),null])await noWrite(control.setCap(1,value),/invalid-hardware-request-token/);
assert.throws(()=>api({id:'foreign@example.com'}),/probe-native-hardware-api-only/);checks++;
assert.throws(()=>api({isPrivileged:false}),/probe-native-hardware-api-only/);checks++;
assert.throws(()=>api({},'content_parent'),/probe-native-hardware-api-only/);checks++;
state.kind=32;await noWrite(control.read('wrong-pref-type'),/native-hardware-pref-unavailable/);state.kind=64;
state.readFailure=true;await noWrite(control.read('getter-failure'),/native-hardware-readback-unavailable/);state.readFailure=false;
state.value=true;await noWrite(control.read('untyped-pref'),/native-hardware-readback-unavailable/);state.value=128;
state.value=0;await noWrite(control.read('invalid-native-cap'),/native-hardware-readback-unavailable/);state.value=128;
state.ignoreWrite=true;await assert.rejects(control.setCap(1,'write-ignored'),/native-hardware-readback-mismatch/);checks++;state.ignoreWrite=false;
state.writeFailure=true;await assert.rejects(control.setCap(1,'setter-failure'),/native-hardware-setting-failed/);checks++;state.writeFailure=false;
state.rfp=true;
for(const cap of [2,1]){const result=await control.setCap(cap,'rfp-cap'+cap);assert.equal(result.rfpEnabled,true);checks++;}
const rfpReset=await control.reset('rfp-reset');assert.equal(rfpReset.rfpEnabled,true);assert.equal(state.rfp,true);checks++;
state.flipRfp=true;await assert.rejects(control.setCap(1,'external-rfp-change'),/native-rfp-policy-changed/);checks++;
assert.ok(state.writes.every(row=>row[1]===CPU));checks++;
console.log(JSON.stringify({status:'passed',checks,actualAndroidExecution:false,workerCoverageVerified:false,
  scope:'authority and native-pref readback model only'}));
'''
        result=subprocess.run(['node','--input-type=module','-',str(ASSETS/'parent.js')],input=program,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertGreaterEqual(data['checks'],30)
        self.assertIs(data['actualAndroidExecution'],False)

    def test_background_requires_current_private_native_port(self):
        program=r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
let command,disconnect,runtimeMessage;const sent=[],calls=[],timers=[];
const port={postMessage(value){sent.push(value);},onMessage:{addListener(fn){command=fn;}},onDisconnect:{addListener(fn){disconnect=fn;}}};
const api={async read(token){calls.push(['read',token]);return {requestToken:token,status:'read'};},
  async setCap(cap,token){calls.push(['set',cap,token]);return {requestToken:token,status:'applied'};},
  async reset(token){calls.push(['reset',token]);return {requestToken:token,status:'reset'};}};
const browser={pocketNativeHardware:api,runtime:{id:'hardware-probe@pocketchat.local',
  connectNative(name){assert.equal(name,'pockethardwareprobe');return port;},onMessage:{addListener(fn){runtimeMessage=fn;}}}};
const sandbox=vm.createContext({browser,setTimeout(fn){timers.push(fn);}});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),sandbox);
assert.equal(sent[0].kind,'hardwareProbeReady');assert.equal(sent[0].apiAvailable,true);
runtimeMessage({kind:'hardwareProbeSet',cap:1,requestToken:'web-page'},{id:browser.runtime.id,tab:{id:1},url:'http://127.0.0.1/'});
await new Promise(resolve=>setImmediate(resolve));assert.equal(calls.length,0);
command({kind:'hardwareProbeSet',cap:2,requestToken:'native-cap2'});
await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(calls,[['set',2,'native-cap2']]);
assert.equal(sent.at(-1).kind,'hardwareProbeResult');assert.equal(sent.at(-1).requestToken,'native-cap2');
command({kind:'hardwareProbeRead',requestToken:'bad token'});await new Promise(resolve=>setImmediate(resolve));
assert.equal(calls.length,1);assert.equal(sent.at(-1).reason,'invalid-hardware-request-token');
disconnect();command({kind:'hardwareProbeSet',cap:1,requestToken:'stale-native'});
await new Promise(resolve=>setImmediate(resolve));assert.equal(calls.length,1);assert.equal(timers.length,1);
console.log(JSON.stringify({status:'passed',checks:6,actualAndroidExecution:false}));
'''
        result=subprocess.run(['node','--input-type=module','-',str(ASSETS/'background.js')],input=program,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIs(json.loads(result.stdout)['actualAndroidExecution'],False)


if __name__=='__main__':unittest.main()
