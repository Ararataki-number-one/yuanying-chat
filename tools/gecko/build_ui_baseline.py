#!/usr/bin/env python3
"""Render the previous UI with the same test data, version and core implementation."""
import argparse,hashlib,json,pathlib,shutil,subprocess

root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration'
p=argparse.ArgumentParser();p.add_argument('--gradle',required=True);p.add_argument('--key',required=True);args=p.parse_args()
baseline='45b4d44528ad54fc7d54299fa9f6091a90446f79'
if subprocess.run(['git','cat-file','-e',baseline+'^{commit}'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    subprocess.run(['git','fetch','--depth=1','origin',baseline],cwd=root,check=True)
files=[root/'app/src/main/java/local/pocketchat'/name for name in ['DesignUi.java','ReferenceUi.java','WindowHomeActivity.java','DesignChrome.java','EnvironmentEditorUi.java','EntryPickerUi.java','NetworkWorkspaceUi.java','BrowserDisplayUi.java']]
original={file:file.read_bytes() for file in files}
current=root/'app/build/outputs/apk/integration/app-x86_64-integration.apk'
shutil.copy2(current,out/'ui-current.apk')
try:
    for file in files:file.write_bytes(subprocess.check_output(['git','show',baseline+':'+str(file.relative_to(root))],cwd=root))
    subprocess.run([args.gradle,':app:assembleIntegration','-PtestSigningKey='+args.key,'--console=plain'],cwd=root,check=True)
    shutil.copy2(current,out/'ui-baseline.apk')
finally:
    for file,content in original.items():file.write_bytes(content)
    shutil.copy2(out/'ui-current.apk',current)
assert all(file.read_bytes()==content for file,content in original.items())
record={'baselineStyleCommit':subprocess.check_output(['git','rev-parse',baseline],cwd=root,text=True).strip(),'coreSourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'changedForBaseline':[str(f.relative_to(root)) for f in files], 'currentSha256':hashlib.sha256((out/'ui-current.apk').read_bytes()).hexdigest(),'baselineSha256':hashlib.sha256((out/'ui-baseline.apk').read_bytes()).hexdigest()}
(out/'ui-build-comparison.json').write_text(json.dumps(record,indent=2)+'\n')
