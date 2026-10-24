#!/usr/bin/env python3
"""Actual visual fixture factory and production display guards on a host JVM."""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', type=pathlib.Path, required=True)
    parser.add_argument('--json-jar', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    loader = importlib.util.spec_from_file_location('extract', ROOT / 'tools/gecko/run_network_core_host.py')
    extract = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(extract)
    fixture = ROOT / 'tests/gecko/UiVisualIntegrationActivity.java'
    production = ROOT / 'app/src/main/java/local/pocketchat/NetworkWorkspaceUi.java'
    source = production.read_text()
    methods = [extract.block(source, '  static '+signature) for signature in (
        'JSONObject runningConfiguration(', 'String displayEntry(', 'String displayExit(', 'String nodeName(')]
    factory = extract.block(fixture.read_text(), '  static JSONObject networkPresentation(')
    runner = (ROOT / 'tests/gecko/run_ui_visuals.py').read_text()
    assert "'network':'固定测试出口'" in runner
    assert 'deadline=time.monotonic()+35;readiness_scrolls=0' in runner
    java = r'''package local.pocketchat;
import org.json.*;
public final class VisualNetworkFixtureTest {
 static final JSONArray checks=new JSONArray();
 static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));if(!value)throw new AssertionError(name);}
 static class NativeNetwork{static String hash(String value){return Sha256.hash(value);}}
 static class WindowNetworkState{JSONObject runtime;long now=100000,environmentGeneration=2;String environmentId="visual-environment";WindowNetworkState(JSONObject value){runtime=value;}}
 FIXTURE
 PRODUCTION
 static JSONObject clone(JSONObject value)throws Exception{return new JSONObject(value.toString());}
 static WindowNetworkState state(JSONObject runtime)throws Exception{JSONObject copy=clone(runtime);copy.put("uiLive",true);return new WindowNetworkState(copy);}
 public static void main(String[] args)throws Exception{
  JSONObject row=J.obj("environmentId","visual-environment","generation",2),presentation=networkPresentation(row,100000),runtime=presentation.getJSONObject("runtime"),running=runtime.getJSONObject("runningConfiguration");
  check("Original legacy visual runtime cannot claim a running route",runningConfiguration(state(J.obj("mode","internal","configured",true,"connected",false,"at",100000)))==null);
  WindowNetworkState accepted=state(runtime);JSONObject shown=runningConfiguration(accepted);
  check("Exact updated visual factory reaches original running route predicate",shown!=null);
  check("Original fixed exit screenshot label is retained",displayExit(shown).equals("固定测试出口"));
  check("Original entry screenshot label is retained",displayEntry(shown).equals("日本大阪 03"));
  check("Visual sample declares synthetic scope and no network evidence",runtime.getBoolean("syntheticPresentationOnly")&&!runtime.getBoolean("actualNetworkEvidence")&&running.getString("scope").equals("ui-visual-synthetic"));
  check("Visual sample never claims connected verified or applied",!runtime.getBoolean("connected")&&!running.getBoolean("verified")&&!runtime.has("appliedRevision")&&!presentation.has("uiMetadata"));
  check("Original saved fixture config stays separate from running summary",presentation.getJSONObject("config")!=running&&presentation.getJSONObject("config").getString("exitName").equals("固定测试出口"));
  for(String failure:new String[]{"uuid","generation","identity-missing","fingerprint","mode","stale","future","not-live"}){
   WindowNetworkState changed=state(runtime);JSONObject value=changed.runtime.getJSONObject("runningConfiguration");
   switch(failure){case "uuid":value.put("environmentId","different-environment");break;case "generation":value.put("generation",3);break;case "identity-missing":value.remove("environmentId");break;case "fingerprint":value.remove("configurationFingerprint");break;case "mode":value.remove("mode");break;case "stale":changed.runtime.put("at",55000);break;case "future":changed.runtime.put("at",160001);break;case "not-live":changed.runtime.put("uiLive",false);break;}
   check("Original production route guard rejects "+failure,runningConfiguration(changed)==null);
  }
  for(JSONObject invalid:new JSONObject[]{new JSONObject(),J.obj("environmentId","visual-environment"),J.obj("environmentId","visual-environment","generation",-1)}){
   boolean rejected=false;try{networkPresentation(invalid,100000);}catch(IllegalArgumentException expected){rejected=true;}check("Visual factory refuses missing or invalid source identity "+invalid,rejected);
  }
  boolean badTime=false;try{networkPresentation(row,0);}catch(IllegalArgumentException expected){badTime=true;}check("Visual factory refuses an absent observation time",badTime);
  check("Presentation factory does not modify original identity",row.length()==2&&row.getString("environmentId").equals("visual-environment")&&row.getInt("generation")==2);
  System.out.println(J.obj("status","passed","passed",checks.length(),"total",checks.length(),"checks",checks));
 }
}
class J{static JSONObject obj(Object... pairs){JSONObject value=new JSONObject();try{for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);}catch(JSONException error){throw new RuntimeException(error);}return value;}}
'''.replace(' FIXTURE', factory).replace(' PRODUCTION', '\n'.join(methods))
    inputs = [fixture, production, ROOT / 'app/src/main/java/local/pocketchat/Sha256.java',
              ROOT / 'tests/gecko/run_ui_visuals.py', ROOT / 'tools/gecko/ui_visual_contract.py',
              ROOT / 'tools/gecko/run_network_core_host.py', pathlib.Path(__file__).resolve()]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    with tempfile.TemporaryDirectory(prefix='visual-network-fixture-') as temporary:
        work = pathlib.Path(temporary)
        path = work / 'VisualNetworkFixtureTest.java'
        path.write_text(java)
        subprocess.run([str(args.java_home / 'bin/javac'), '-encoding', 'UTF-8', '-cp', str(args.json_jar), '-d', str(work), str(path), str(ROOT / 'app/src/main/java/local/pocketchat/Sha256.java')], check=True)
        run = subprocess.run([str(args.java_home / 'bin/java'), '-cp', str(work)+':'+str(args.json_jar), 'local.pocketchat.VisualNetworkFixtureTest'], check=True, capture_output=True, text=True)
    result = json.loads(run.stdout)
    result.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  sourceDirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
                  sourceFiles=hashes, jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),
                  actualAndroidExecution=False, actualNetworkEvidence=False,
                  exactFixtureFactory=True, exactProductionDisplayGuards=True,
                  originalFixedExitLabelUnchanged=True, originalReadinessDeadlineUnchanged=True,
                  scope='Whole integration-only visual factory and exact production display helpers; narrow WindowNetworkState field adapter. Synthetic visual data is not an ExitRouteReceipt or applied/network acceptance.')
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status':result['status'], 'passed':result['passed'], 'total':result['total']}))


if __name__ == '__main__':
    main()
