"""Exact Gecko157 RFP standard-zone oracle controls; no Android/native execution."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
GENERIC=ROOT/'tests/gecko/GeckoEnvironmentPolicyIntegrationActivity.java'
ACTIVITY=ROOT/'tests/gecko/GeckoIpTimeZoneIntegrationActivity.java'
CHECKER=ROOT/'tools/browser/check_gecko_ip_timezone_evidence.py'
EXTRACTOR=ROOT/'tests/gecko-timezone-flow-host/run.py'
CLOCK_SHA='04dd96fc3ec44c5a8643c5684a5fd9a40185b060f73539f8dfe9bf275e6031bd'
STANDARD='Atlantic/Reykjavik'
RFP_CONJUNCTION='&&(!"rfp-priority".equals(name)||RFP_STANDARD_ZONE.equals(early.getJSONObject("nativeTimeZone").opt("timeZone")))'
# Exact packet copied from the original failed diagnostic9 report, not a new
# native observation. CI controls embed it and never require an old Git object.
PRIOR_REPORT_SHA='0c23dd54017fa54eba51bc3735fb6e47bdc991dae3cbda4e8dea4f221c31370b'
OBSERVED_PACKET={'timeZone':'Atlantic/Reykjavik','january':{'offsetMinutes':0,'year':2026,'month':1,'day':15,'hour':12,'minute':0},'july':{'offsetMinutes':0,'year':2026,'month':7,'day':15,'hour':12,'minute':0}}
JAVA_HOME=None;OUTPUT=None;RESULT={}
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def fixed_clock(zone):
    # Independent fixed-epoch literals, never generated with the checker oracle.
    if zone=='America/New_York':a,b=(300,7,0),(240,8,0)
    elif zone in ('Asia/Kathmandu','Asia/Katmandu'):a=b=(-345,17,45)
    else:a=b=(0,12,0)
    return dict(timeZone=zone,**{name:dict(offsetMinutes=value[0],year=2026,month=month,day=15,hour=value[1],minute=value[2]) for name,month,value in [('january',1,a),('july',7,b)]})

def packet(clock):
    return dict(schema=1,firstInline=True,secure=True,runNonce='b'*32,sourceCommit='a'*40,phase='rfp-priority',origin='https://fp-a.pocketchat.test',documentId='00000000-0000-0000-0000-000000000006',nativeUserAgent='Controlled Gecko157 schema input',nativeTimeZone=copy.deepcopy(clock),markerComplete=True,networkAllowed=True)

JAVA=r'''package local.pocketchat;
import org.json.*;
public final class RfpClockHost {
 static int checks;static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks++;}
 @CONSTANT@
 static JSONObject row(int month,int offset,int hour,int minute)throws Exception{return new JSONObject().put("offsetMinutes",offset).put("year",2026).put("month",month).put("day",15).put("hour",hour).put("minute",minute);}
 static JSONObject clock(String zone)throws Exception{int a=0,b=0,ah=12,bh=12,minute=0;if(zone.equals("America/New_York")){a=300;b=240;ah=7;bh=8;}if(zone.equals("Asia/Kathmandu")||zone.equals("Asia/Katmandu")){a=b=-345;ah=bh=17;minute=45;}return new JSONObject().put("timeZone",zone).put("january",row(1,a,ah,minute)).put("july",row(7,b,bh,minute));}
 static JSONObject sample(JSONObject clock)throws Exception{return new JSONObject().put("page",new JSONObject().put("nativeTimeZone",clock).put("firstInline",true).put("secure",true).put("networkAllowed",true));}
 static boolean matches(JSONObject clock,String zone)throws Exception{return GeckoEnvironmentPolicyIntegrationActivity.clockMatches(sample(clock),zone);}
 static boolean capture(JSONObject clock,String name,String zone)throws Exception{JSONObject value=sample(clock),early=value.getJSONObject("page");return @CAPTURE_RHS@;}
 public static void main(String[] args)throws Exception{
  JSONObject nativePacket=new JSONObject(@PACKET@);
  check("Actual prior Reykjavik packet satisfies the unchanged generic clock method",matches(nativePacket,"Atlantic/Reykjavik"));
  check("Actual RFP-only capture RHS accepts the prior exact native packet",capture(nativePacket,"rfp-priority",RFP_STANDARD_ZONE));
  check("Generic rule comparison preserves actual JDK Abidjan equivalence",matches(clock("Africa/Abidjan"),"Atlantic/Reykjavik"));
  for(String zone:new String[]{"UTC","Etc/UTC","Africa/Abidjan","Iceland"})check("RFP wrong zero-offset name is rejected: "+zone,!capture(clock(zone),"rfp-priority",RFP_STANDARD_ZONE));
  for(String season:new String[]{"january","july"})for(String field:new String[]{"offsetMinutes","year","month","day","hour","minute"}){JSONObject changed=new JSONObject(nativePacket.toString());JSONObject value=changed.getJSONObject(season);value.put(field,value.getInt(field)+1);check("Correct Reykjavik name cannot hide incorrect numeric observation: "+season+"/"+field,!capture(changed,"rfp-priority",RFP_STANDARD_ZONE));}
  check("Ordinary UTC still accepts actual UTC",capture(clock("UTC"),"https-proxy","UTC"));
  check("Ordinary UTC retains existing Etc UTC alias",capture(clock("Etc/UTC"),"https-proxy","UTC"));
  check("Ordinary UTC rejects Reykjavik rules despite equal current offsets",!capture(nativePacket,"https-proxy","UTC"));
  check("New York retains exact winter and DST values",matches(clock("America/New_York"),"America/New_York"));
  JSONObject ny=clock("America/New_York");ny.getJSONObject("july").put("offsetMinutes",300).put("hour",7);check("New York wrong summer DST is rejected",!matches(ny,"America/New_York"));
  check("Kathmandu retains exact quarter-hour values",matches(clock("Asia/Kathmandu"),"Asia/Kathmandu"));
  check("Existing Katmandu alias remains unchanged",matches(clock("Asia/Katmandu"),"Asia/Kathmandu"));
  JSONObject ktm=clock("Asia/Kathmandu");ktm.getJSONObject("january").put("offsetMinutes",-330).put("minute",30);check("Kathmandu incorrect numeric offset is rejected",!matches(ktm,"Asia/Kathmandu"));
  JSONObject wrong=clock("America/New_York");wrong.put("timeZone","UTC");check("New York wrong zone name is rejected",!matches(wrong,"America/New_York"));
  wrong=clock("Asia/Kathmandu");wrong.put("timeZone","UTC");check("Kathmandu wrong zone name is rejected",!matches(wrong,"Asia/Kathmandu"));
  System.out.println("{\"status\":\"passed\",\"checks\":"+checks+"}");
 }
}
final class GeckoEnvironmentPolicyIntegrationActivity {@CLOCK@}
'''


class RfpStandardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate=module('actual_rfp_standard_ip_checker',CHECKER)
        cls.extract=module('rfp_standard_actual_java_member',EXTRACTOR)
        cls.method=cls.extract.block(GENERIC.read_text(),'static boolean clockMatches(')
        cls.capture_rhs=re.findall(r'^\s*check\(name\+"\.first-inline-native-clock",(.+)\);$',ACTIVITY.read_text(),re.MULTILINE)
        if len(cls.capture_rhs)!=1:raise ValueError('One actual native capture RHS required')
        cls.capture_rhs=cls.capture_rhs[0]
        cls.constant=re.findall(r'^  static final String RFP_STANDARD_ZONE="[^"]+";$',ACTIVITY.read_text(),re.MULTILINE)
        if len(cls.constant)!=1:raise ValueError('One exact native RFP standard constant required')
        cls.constant=cls.constant[0]
        cls.inputs=[GENERIC,ACTIVITY,CHECKER,EXTRACTOR,Path(__file__).resolve()]
        cls.hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in cls.inputs}

    def test_only_rfp_case_uses_the_exact_official_standard_name(self):
        source=ACTIVITY.read_text();gate=self.gate
        self.assertEqual(re.findall(r'RFP_STANDARD_ZONE="([^"]+)"',source),[STANDARD])
        self.assertEqual(gate.RFP_STANDARD_ZONE,STANDARD)
        self.assertEqual(source.count('RFP_STANDARD_ZONE'),3)
        self.assertEqual(source.count('capture("rfp-priority",RFP_STANDARD_ZONE,false,'),1)
        self.assertIn('capture("https-proxy","UTC",false,',source)
        self.assertIn('capture("bootstrap-preparation","UTC",true,',source)
        self.assertEqual(len(self.method.encode()),908)
        self.assertEqual(sha(self.method.encode()),CLOCK_SHA,'The generic clockMatches method must remain byte-for-byte unchanged')
        self.assertTrue(self.capture_rhs.endswith(RFP_CONJUNCTION))
        self.assertEqual(self.capture_rhs[:-len(RFP_CONJUNCTION)],'early.getBoolean("firstInline")&&early.getBoolean("secure")&&early.getBoolean("networkAllowed")&&GeckoEnvironmentPolicyIntegrationActivity.clockMatches(value,zone)')

    def test_actual_python_clock_and_page_accept_original_packet_and_reject_wrong_names(self):
        gate=self.gate;self.assertEqual(fixed_clock(STANDARD),OBSERVED_PACKET)
        gate.clock(copy.deepcopy(OBSERVED_PACKET),STANDARD);gate.page(packet(OBSERVED_PACKET),'a'*40,'b'*32,STANDARD)
        for zone in ('UTC','Etc/UTC','Africa/Abidjan','Iceland'):
            wrong=fixed_clock(zone)
            for call in (lambda:gate.clock(wrong,STANDARD),lambda:gate.page(packet(wrong),'a'*40,'b'*32,STANDARD)):
                with self.subTest(zone=zone),self.assertRaisesRegex(ValueError,'Intl native zone differs'):call()
        for season in ('january','july'):
            for field in ('offsetMinutes','year','month','day','hour','minute'):
                wrong=copy.deepcopy(OBSERVED_PACKET);wrong[season][field]+=1
                for call in (lambda:gate.clock(wrong,STANDARD),lambda:gate.page(packet(wrong),'a'*40,'b'*32,STANDARD)):
                    with self.subTest(season=season,field=field),self.assertRaises(ValueError):call()

    def test_ordinary_utc_new_york_and_kathmandu_policies_are_unchanged(self):
        gate=self.gate
        for zone in ('UTC','Etc/UTC','Etc/GMT','GMT'):gate.clock(fixed_clock(zone),'UTC')
        with self.assertRaisesRegex(ValueError,'Intl native zone differs'):gate.clock(OBSERVED_PACKET,'UTC')
        gate.clock(fixed_clock('America/New_York'),'America/New_York');gate.clock(fixed_clock('Asia/Kathmandu'),'Asia/Kathmandu');gate.clock(fixed_clock('Asia/Katmandu'),'Asia/Kathmandu')
        for wanted in ('America/New_York','Asia/Kathmandu'):
            wrong=fixed_clock(wanted);wrong['timeZone']='UTC'
            with self.subTest(wanted=wanted),self.assertRaises(ValueError):gate.clock(wrong,wanted)
            wrong=fixed_clock(wanted);wrong['july']['hour']+=1
            with self.subTest(wanted=wanted),self.assertRaises(ValueError):gate.clock(wrong,wanted)

    def test_python_name_guard_counterfeit_is_caught_by_the_same_negative_expectation(self):
        source=inspect.getsource(self.gate.clock);tree=ast.parse(source)
        guard=next(n for n in ast.walk(tree) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and len(n.value.args)>1 and isinstance(n.value.args[1],ast.Constant) and n.value.args[1].value=='Intl native zone differs')
        original=ast.get_source_segment(source,guard);self.assertEqual(source.count(original),1)
        mutant=source.replace(original,'pass # explicit counterfeit: strict name guard removed',1)
        namespace=dict(self.gate.__dict__);exec(compile(mutant,str(CHECKER)+':host-only-name-mutant','exec'),namespace)
        def same_negative_expectation(check):
            denied=False
            try:check(fixed_clock('UTC'),STANDARD)
            except ValueError:denied=True
            if not denied:raise AssertionError('RFP wrong zero-offset name must remain rejected')
        same_negative_expectation(self.gate.clock)
        with self.assertRaisesRegex(AssertionError,'RFP wrong zero-offset name must remain rejected'):same_negative_expectation(namespace['clock'])
        RESULT['pythonNameCounterfeit']=dict(compiled=True,rejectedBySameNegativeExpectation=True,mutatedFunctionSha256=sha(mutant.encode()))

    def test_actual_java_clock_method_and_compiled_rules_guard_counterfeit(self):
        java_home=JAVA_HOME or Path(os.environ.get('PROFILE_JAVA_HOME',os.environ.get('JAVA_HOME_17_X64',os.environ.get('JAVA_HOME',''))))
        java=java_home/'bin/java' if str(java_home)!='.' else Path(shutil.which('java') or '');javac=java.with_name('javac')
        self.assertTrue(java.is_file() and javac.is_file(),'Selected JDK17 required')
        jars=[Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/gecko-integration/catalog-json.jar')),Path(os.environ.get('PROFILE_ANDROID_JSON_JAR',ROOT/'work/profile-host/android-json.jar'))]
        target=OUTPUT or ROOT/'work/rfp-standard-host/results.json';artifacts=target.parent/'artifacts';artifacts.mkdir(parents=True,exist_ok=True);runs=[];controls=[]
        guard='if(!zone.getRules().equals(observed.getRules()))return false;';self.assertEqual(self.method.count(guard),1)
        for label,jar in zip(('desktop','android-json'),jars):
            self.assertTrue(jar.is_file(),'Real selected JSON jar missing: '+str(jar))
            for variant,method,rhs in [('current',self.method,self.capture_rhs),('removed-rules-guard',self.method.replace(guard,'',1),self.capture_rhs),('removed-rfp-name-guard',self.method,self.capture_rhs.replace(RFP_CONJUNCTION,'',1))]:
                with tempfile.TemporaryDirectory(prefix='rfp-standard-clock-')as temporary:
                    folder=Path(temporary);text=JAVA.replace('@CLOCK@',method).replace('@CONSTANT@',self.constant).replace('@CAPTURE_RHS@',rhs).replace('@PACKET@',json.dumps(json.dumps(OBSERVED_PACKET,separators=(',',':'))));path=folder/'RfpClockHost.java';path.write_text(text)
                    out=artifacts/(label+'-'+variant);out.mkdir(exist_ok=True);(out/'RfpClockHost.java').write_text(text)
                    command=[str(javac),'--release','17','-encoding','UTF-8','-cp',str(jar.resolve()),'-d',str(folder/'classes'),str(path)]
                    built=subprocess.run(command,text=True,capture_output=True,timeout=30);(out/'compile.command.json').write_text(json.dumps(command)+'\n');(out/'compile.stdout.log').write_text(built.stdout);(out/'compile.stderr.log').write_text(built.stderr);self.assertEqual(built.returncode,0,built.stdout+built.stderr)
                    command=[str(java),'-cp',str(folder/'classes')+os.pathsep+str(jar.resolve()),'local.pocketchat.RfpClockHost'];ran=subprocess.run(command,text=True,capture_output=True,timeout=20);(out/'run.command.json').write_text(json.dumps(command)+'\n');(out/'run.stdout.log').write_text(ran.stdout);(out/'run.stderr.log').write_text(ran.stderr)
                    if variant=='current':self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr);runs.append(dict(jsonVariant=label,jsonJarSha256=sha(jar.read_bytes()),generatedHostSha256=sha(text.encode()),report=json.loads(ran.stdout)))
                    else:
                        assertion='Ordinary UTC rejects Reykjavik rules despite equal current offsets'if variant=='removed-rules-guard'else'RFP wrong zero-offset name is rejected: Africa/Abidjan'
                        self.assertEqual(ran.returncode,1);self.assertIn('java.lang.AssertionError: '+assertion,ran.stderr);controls.append(dict(jsonVariant=label,variant=variant,compiled=True,rejected=True,methodSha256=sha(method.encode()),captureRhsSha256=sha(rhs.encode()),assertion=assertion))
        RESULT.update(javaRuns=runs,compiledJavaCounterfeits=controls)


if __name__=='__main__':
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--java-home',type=Path);p.add_argument('--output',type=Path);args,rest=p.parse_known_args();JAVA_HOME=args.java_home;OUTPUT=args.output
    run=unittest.main(argv=[sys.argv[0],*rest],exit=False);stable=all(sha(path.read_bytes())==RfpStandardTests.hashes[str(path.relative_to(ROOT))]for path in RfpStandardTests.inputs)
    RESULT.update(schema=1,status='passed'if run.result.wasSuccessful() and stable else'failed',unittestCount=run.result.testsRun,sourceFiles=RfpStandardTests.hashes,executionInputsUnchanged=stable,genericClockMethodSha256=sha(RfpStandardTests.method.encode()),actualCaptureRhsSha256=sha(RfpStandardTests.capture_rhs.encode()),genericJdkAbidjanRulesEquivalent=True,priorNativePacketSourceReportSha256=PRIOR_REPORT_SHA,priorNativePacketSha256=sha(json.dumps(OBSERVED_PACKET,separators=(',',':')).encode()),rfpStandardZone=STANDARD,officialSourceReference=dict(repository='mozilla-firefox/firefox',gitCommit='0c469c2352451630bc69fc328c9f0c589c6c534d',path='toolkit/components/resistfingerprinting/nsRFPService.cpp',method='nsRFPService::GetSpoofedJSTimeZone',line=1063,sourceSha256='1cad1459e55c976db17c5a60a247efdb0f089c47d171b317c54863fad2c6985d',hgToGitMappingIndependentlyProven=False),actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimeZoneExecution=False,actualPublicGeoExecution=False,scope='Unchanged complete generic Activity.clockMatches and actual current IP Activity capture assertion RHS execute on a real JVM with two real JSON jars. Generic JVM ZoneRules equates Reykjavik and Abidjan; the additional exact-name conjunction applies only to rfp-priority. Current actual Python clock/page validators execute against the fixed prior native packet and controlled name/numeric counterexamples. Existing ordinary aliases and non-RFP UTC captures remain unchanged. Official native source constant reference and prior native observation provenance are distinct; no HG/Git mapping or fresh native/device execution is claimed.')
    target=OUTPUT or ROOT/'work/rfp-standard-host/results.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(RESULT,ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if RESULT['status']=='passed'else 1)
