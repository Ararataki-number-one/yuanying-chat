#!/usr/bin/env python3
"""Run production model/receipts and exact integration projection with scoped service adapters."""
import argparse, hashlib, importlib.util, json, pathlib, subprocess
p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);p.add_argument('--fixture-ref',help='Private old integration projection reproduction; not accepted as current host evidence');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];work=root/'work/network-application-host';classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
production=root/'app/src/main/java/local/pocketchat';files=[production/name for name in ('EnvironmentSpec.java','NetworkApplicationReceipt.java','J.java')]+[pathlib.Path(__file__).parent/'local/pocketchat/NetworkApplicationHostTest.java']
loader=importlib.util.spec_from_file_location('extract_receipt',root/'tools/gecko/run_network_core_host.py');extract=importlib.util.module_from_spec(loader);loader.loader.exec_module(extract)
fixture=root/'tests/gecko/NetworkSettingsInternalApplication.java';native=production/'NativeNetwork.java';template=pathlib.Path(__file__).with_name('ReceiptProjectionTest.java.in')
fixture_source=subprocess.check_output(['git','show',a.fixture_ref+':'+str(fixture.relative_to(root))],cwd=root,text=True) if a.fixture_ref else fixture.read_text()
receipt_method=extract.block(native.read_text(),'  static final class ExitRouteReceipt {');projection_method=extract.block(fixture_source,'  JSONObject identities()')
generated=work/'ReceiptProjectionTest.java';generated.write_text(template.read_text().replace('@RECEIPT@',receipt_method).replace('@IDENTITIES@',projection_method))
inputs=files+[fixture,native,template,pathlib.Path(__file__).resolve(),root/'tools/gecko/run_network_core_host.py']
hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)],check=True)
r=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.NetworkApplicationHostTest'],text=True,capture_output=True,check=True)
result=json.loads(r.stdout);assert result['passed']==len(result['checks']) and all(row['pass'] is True for row in result['checks'])
subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar)+':'+str(classes),'-d',str(classes),str(generated)],check=True)
projection_run=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-Dprojection.legacy='+str(bool(a.fixture_ref)).lower(),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.ReceiptProjectionTest'],text=True,capture_output=True,check=True)
projection=json.loads(projection_run.stdout);assert projection['passed']==len(projection['checks']) and all(row['pass'] is True for row in projection['checks'])
result['checks'].extend(projection['checks']);result['passed']=len(result['checks']);result['status']=projection['status']
result.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)),files=hashes,projectionFixtureRef=a.fixture_ref,projectionReceipt={'status':projection['status'],'checks':projection['passed'],'productionReceiptSha256':hashlib.sha256(receipt_method.encode()).hexdigest(),'integrationProjectionSha256':hashlib.sha256(projection_method.encode()).hexdigest(),'fixtureSourceSha256':hashlib.sha256(fixture_source.encode()).hexdigest(),'exactProductionReceipt':True,'exactIntegrationProjection':True},scope='Actual EnvironmentSpec and NetworkApplicationReceipt plus exact production ExitRouteReceipt and integration identities projection. Narrow owning-network and service snapshot adapters exercise matching only; no Android, real service/core verification, or application admission claim.')
assert all(hashlib.sha256((root/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':result['passed'],'report':str(out)}))
