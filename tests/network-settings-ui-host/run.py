#!/usr/bin/env python3
"""Exact production UI helpers; no Android UI/lifecycle execution claim."""
import argparse,hashlib,importlib.util,json,pathlib,subprocess
parser=argparse.ArgumentParser();parser.add_argument('--java-home',required=True,type=pathlib.Path);parser.add_argument('--json-jar',required=True,type=pathlib.Path);parser.add_argument('--output',required=True,type=pathlib.Path);args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];work=root/'work/network-settings-ui-host';work.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('extract',root/'tools/gecko/run_network_core_host.py'); extract=importlib.util.module_from_spec(spec); spec.loader.exec_module(extract)
source=root/'app/src/main/java/local/pocketchat/NetworkWorkspaceUi.java'; text=source.read_text()
names=['entryModeLabel','setupOnly','runningConfiguration','displayEntry','displayExit','externalName','metadata','version','metadataSummary','pendingSummary','pendingCandidateId','nodeName','editingContext','operationResult','operationText']
methods=[]
for name in names:
 import re
 sig=re.search(r'  static \S+ '+name+r'\(',text).group(0)
 methods.append(extract.block(text,sig))
java='''package local.pocketchat;
import org.json.*;
public class UiSnapshotTest {
 static class NativeNetwork {static String hash(String s){return Sha256.hash(s);}}
 static int passed;static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);passed++;}
 static JSONObject obj(Object... values){JSONObject result=new JSONObject();try{for(int i=0;i<values.length;i+=2)result.put((String)values[i],values[i+1]);return result;}catch(Exception failed){throw new RuntimeException(failed);}}
 static class WindowNetworkState{JSONObject runtime;long now=100000,environmentGeneration=2;String environmentId="scope-a",state="未配置",ip="",region="",latency="延迟未测";boolean connected;WindowNetworkState(JSONObject runtime){this.runtime=runtime;}}
 METHODS
 public static void main(String[] ignored)throws Exception{
  check(entryModeLabel("latency").equals("自动优选"),"latency mode has one user-facing label");
  JSONObject running=obj("environmentId","scope-a","generation",2,"mode","internal","entry","Entry|actual","exitName","actual exit","configurationFingerprint","proof");
  WindowNetworkState state=new WindowNetworkState(obj("uiLive",true,"at",100000,"runningConfiguration",running));
  check(runningConfiguration(state)==running,"fresh running core is displayed");
  running.put("environmentId","scope-b");check(runningConfiguration(state)==null,"old runtime UUID cannot follow reused slot");running.put("environmentId","scope-a");
  running.put("generation",3);check(runningConfiguration(state)==null,"old runtime generation cannot follow rebuilt environment");running.remove("generation");check(runningConfiguration(state)==null,"unscoped running summaries stay unknown");running.put("generation",2);
  state.runtime.put("uiLive",false);check(runningConfiguration(state)==null,"saved snapshots cannot claim a running core");state.runtime.put("uiLive",true);
  state.runtime.put("at",55000);check(runningConfiguration(state)==null,"stale runtime cannot claim a running core");state.runtime.put("at",100000);
  running.remove("configurationFingerprint");check(runningConfiguration(state)==null,"missing core fingerprint is explicit unknown");running.put("configurationFingerprint","proof");
  check(displayEntry(running).equals("actual"),"actual entry name is shown");check(displayExit(running).equals("actual exit"),"actual fixed exit is shown");
  check(externalName(obj("proxy",false)).equals("手机网络 / VPN"),"boolean false does not invent proxy");check(externalName(obj("proxy",true)).equals("应用专用代理"),"safe proxy flag is used");
  String secret="socks://private-user:private-password@host:1080";check(externalName(obj("proxy",secret)).equals("应用专用代理")&&!externalName(obj("proxy",secret)).contains(secret),"proxy summary omits credentials");
  JSONObject metadata=obj("available",true,"desiredRevision",9,"appliedRevision",7,"pendingReady",true);
  JSONObject item=obj("uiMetadata",metadata,"pendingNetwork",true,"pendingAction","external","pendingConfig",obj("proxy",secret));
  check(metadataSummary(item).equals("已保存 v9 · 网页配置已确认 v7"),"saved and applied versions remain distinct");
  check(pendingSummary(item).equals("应用专用代理"),"pending external route is summarized without secrets");
  check(editingContext(item,true).startsWith("正在编辑待应用配置"),"editing pending is explicit");
  check(editingContext(item,false).contains("保存后将替换它"),"switching route modes explains replacement");
  metadata.put("pendingReady",false);check(pendingSummary(item).equals("保存状态待恢复"),"staged save is not presented as ready");
  JSONObject receipt=obj("environmentId","scope-a","generation",2,"saveState","saved","applicationState","pending","scope","session","savedRevision",9,"appliedRevision",7);
  check(operationResult(state,obj("operationResult",receipt))==receipt,"exact result scope is accepted");
  receipt.put("environmentId","scope-b");check(operationResult(state,obj("operationResult",receipt))==null,"slot reuse UUID rejects old result");receipt.put("environmentId","scope-a");receipt.put("generation",3);check(operationResult(state,obj("operationResult",receipt))==null,"new generation rejects old result");receipt.put("generation",2);
  check(operationText(receipt,"waiting").startsWith("等待应用")&&!operationText(receipt,"waiting").contains("已应用")&&!operationText(receipt,"waiting").contains("v9"),"pending receipt never claims application");
  receipt.put("applicationState","applying");check(operationText(receipt,"").startsWith("连接中")&&!operationText(receipt,"").contains("已应用"),"applying has distinct state");
  receipt.put("applicationState","saved-unconfirmed");check(operationText(receipt,"").startsWith("已保存 · 核验未完成"),"unverified save is not success");
  receipt.put("applicationState","applied");receipt.put("scope","core");check(operationText(receipt,"").equals("已应用")&&receipt.getString("scope").equals("core")&&receipt.getLong("appliedRevision")<receipt.getLong("savedRevision")&&!operationText(receipt,"").contains("网页配置已确认"),"core proof cannot claim webpage proof");
  receipt.put("scope","session");check(operationText(receipt,"").equals("已应用")&&receipt.getString("scope").equals("session"),"session receipt has precise scope");
  receipt.put("scope","next-session");check(operationText(receipt,"").equals("等待应用")&&!operationText(receipt,"").startsWith("已应用"),"future session does not claim current application");
  receipt.put("saveState","superseded");check(operationText(receipt,"").startsWith("已由较新的设置替换"),"superseded receipt is explicit");
  receipt.put("saveState","failed");check(operationText(receipt,"").startsWith("未能保存"),"failed save cannot inherit old success");
  check(operationText(null,"legacy success").startsWith("操作结果待确认"),"a callback boolean alone is insufficient proof");
  receipt.put("saveState","uncertain");receipt.put("applicationState","unconfirmed");check(operationText(receipt,"").startsWith("保存结果待确认"),"ambiguous durable result never claims failure or success");
  receipt.put("saveState","saved");receipt.put("applicationState","saved-unconfirmed");receipt.put("savedRevision",0);check(operationText(receipt,"").startsWith("已保存 · 核验未完成")&&!operationText(receipt,"").contains("v0"),"known save with unreadable model keeps version explicitly unknown");
  receipt.put("applicationState","cancelled");check(operationText(receipt,"").startsWith("待应用设置已取消"),"cancelled saved candidate has its own terminal state");
  check(!operationText(receipt,"").contains("已保存 · 待应用")&&!operationText(receipt,"").contains("已由较新的设置替换"),"cancellation never invents pending application or a replacement candidate");

  check(metadataSummary(new JSONObject()).equals("配置版本暂时无法读取"),"absent metadata does not invent versions");
  check(pendingCandidateId(new JSONObject(),null).equals(""),"absent pending uses explicit empty guard");
  JSONObject legacy=obj("action","external","config",obj("proxy","socks://old:1080"));String legacyId=pendingCandidateId(legacy,null);
  check(legacyId.equals("legacy:"+Sha256.hash(legacy.toString())),"legacy UI candidate guard matches backend snapshot identity");
  legacy.put("savedAt",1);check(!legacyId.equals(pendingCandidateId(legacy,null)),"legacy guard changes with a replacement saved receipt");
  check(pendingCandidateId(legacy,obj("id","stable-candidate")).equals("stable-candidate"),"modern pending keeps its intent identity");

  // Empty setup hints may replace placeholders, never observations or pending work.
  WindowNetworkState setup=new WindowNetworkState(new JSONObject());
  JSONObject setupMeta=obj("available",true,"environmentId","scope-a","generation",2);
  JSONObject setupItem=obj("uiMetadata",setupMeta);
  check(setupOnly(setup,setupItem),"known unconfigured environment with no observations may show setup hint");
  setup.ip="203.0.113.9";check(!setupOnly(setup,setupItem),"historical IP keeps network details");setup.ip="";
  setup.region="日本";check(!setupOnly(setup,setupItem),"known exit region keeps network details");setup.region="";
  for(String observedLatency:new String[]{"122 ms","122 ms（上次）","探测未通过"}){
   setup.latency=observedLatency;check(!setupOnly(setup,setupItem),"latency observation keeps details: "+observedLatency);
  }
  setup.latency="延迟未测";
  setup.connected=true;check(!setupOnly(setup,setupItem),"connected observation cannot become an empty setup hint");setup.connected=false;
  for(String observedState:new String[]{"连接中","未运行"}){
   setup.state=observedState;check(!setupOnly(setup,setupItem),"existing connection state keeps details: "+observedState);
  }
  setup.state="未配置";
  setupItem.put("pendingNetwork",true);check(!setupOnly(setup,setupItem),"pending application keeps network details");setupItem.remove("pendingNetwork");
  check(!setupOnly(setup,new JSONObject()),"missing metadata cannot establish empty setup state");
  setupMeta.put("available",false);check(!setupOnly(setup,setupItem),"unreadable metadata keeps network details");setupMeta.put("available",true);
  setupMeta.put("environmentId","scope-b");check(!setupOnly(setup,setupItem),"another environment's metadata cannot hide details");setupMeta.put("environmentId","scope-a");
  setupMeta.put("generation",3);check(!setupOnly(setup,setupItem),"another generation's metadata cannot hide details");setupMeta.put("generation",2);
  setupMeta.remove("generation");check(!setupOnly(setup,setupItem),"unscoped metadata keeps network details");setupMeta.put("generation",2);
  setup.environmentId="";check(!setupOnly(setup,setupItem),"missing environment identity keeps network details");setup.environmentId="scope-a";
  check(setupOnly(setup,setupItem),"cleared observations and matching readable metadata restore setup hint");
  setup.runtime=obj("uiLive",true,"at",100000,"runningConfiguration",running);
  check(runningConfiguration(setup)==running&&!setupOnly(setup,setupItem),"fresh actual running configuration keeps route details");

  System.out.println(obj("passed",passed,"total",passed,"scope","Extracted production UI formatting and identity helpers; no Android execution"));
 }
}
'''.replace(' METHODS','\n'.join(methods))
(work/'UiSnapshotTest.java').write_text(java)
# Literal Java newlines belong inside escaped string literals.
p=work/'UiSnapshotTest.java';p.write_text(p.read_text().replace('待应用\n已保存','待应用\\n已保存'))
jdk=args.java_home/'bin';jar=args.json_jar
policy=root/'app/src/main/java/local/pocketchat/NetworkOptimizationPolicy.java'
subprocess.run([str(jdk/'javac'),'-encoding','UTF-8','-cp',str(jar),'-d',str(work),str(p),str(policy),str(root/'app/src/main/java/local/pocketchat/Sha256.java'),str(root/'tests/browser-runtime/NetworkOptimizationPolicyTest.java')],check=True)
results={}
for test in ['UiSnapshotTest','NetworkOptimizationPolicyTest']:
 run=subprocess.run([str(jdk/'java'),'-cp',str(work)+':'+str(jar),'local.pocketchat.'+test],check=True,text=True,capture_output=True);results[test]=json.loads(run.stdout)
files=[source,policy,root/'app/src/main/java/local/pocketchat/Sha256.java',root/'tests/NetworkReferenceTestActivity.java',pathlib.Path(__file__)]
report={'results':results,'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'sourceDirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)),'files':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'actualAndroidExecution':False,'extractedMethods':names}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(results,ensure_ascii=False))
