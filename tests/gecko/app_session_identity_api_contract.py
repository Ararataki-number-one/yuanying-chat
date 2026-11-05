#!/usr/bin/env python3
"""Actual SDK/API and source-only proof for the application-owned ID bridge.

No Gecko instance is constructed and no Android/native getter execution is claimed.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
BRIDGE=ROOT/'app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java'
VERIFIER=ROOT/'tools/gecko/check_caret_compat_evidence.py'
ORIGINAL_BRIDGE_SHA256='8465a704157f3d0bcb50dfa73f00a1ab5c12c6b791e4cc0954a3dd80c6c7ae7f'
ORIGINAL_RECEIPTS_SHA256='bed0d3a1346a70b3e9b4162b23f08df13853df4c80f30f4211d279f44a344269'
OBSERVER_NAMES=['org.mozilla.geckoview.PocketGeckoEditableTrace',
                'org.mozilla.geckoview.PocketGeckoInputTrace','org.mozilla.geckoview.PocketInputWriterTrace']


def require(value,message):
    if not value:raise ValueError('Application session ID contract: '+message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    return digest.hexdigest()


def bridge_source(raw):
    require(type(raw) is bytes and b'public final class AppSessionIdentity {' in raw,
            'exact application-owned bridge class required')
    require(hashlib.sha256(raw.replace(b'AppSessionIdentity',b'PocketSessionIdentity')).hexdigest()==ORIGINAL_BRIDGE_SHA256,
            'only the reviewed class/constructor rename is permitted; readonly body and validation must remain exact')


def readonly_getter(body):
    operations=re.findall(r'^\s*\d+:\s+(\w+)([^\n]*)$',body,re.MULTILINE)
    require([name for name,_ in operations]==['aload_0','getfield','areturn']
            and '// Field mId:Ljava/lang/String;' in operations[1][1],
            'actual SDK getId must only return its existing mId field')


def sdk_class_names(names):
    require(len(names)==len(set(names)) and names.count('org/mozilla/geckoview/GeckoSession.class')==1,
            'one actual SDK session class required')
    require(not any(name.startswith('org/mozilla/geckoview/Pocket') and name.endswith('.class') for name in names),
            'reserved SDK observer namespace must remain absent')
    require('org/mozilla/geckoview/AppSessionIdentity.class' not in names,
            'application helper must not be injected into the SDK archive')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path,required=True)
    parser.add_argument('--android-jar',type=Path,required=True)
    parser.add_argument('--sdk-jar',type=Path)
    parser.add_argument('--sdk-aar',type=Path,default=ROOT/'work/native-caret-sdk/geckoview-caret.aar')
    parser.add_argument('--sdk-receipt',type=Path,default=ROOT/'work/native-caret-sdk/sdk-build-receipt.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();javac=args.java_home/'bin/javac';javap=args.java_home/'bin/javap'
    require(all(path.is_file() and not path.is_symlink() for path in (BRIDGE,VERIFIER,javac,javap,args.android_jar,args.sdk_receipt)),
            'actual source, JDK, Android API and SDK receipt are mandatory; no skip or fabricated SDK')
    require(not (ROOT/'app/src/main/java/org/mozilla/geckoview/PocketSessionIdentity.java').exists(),
            'retired reserved application class must be absent')
    receipt=json.loads(args.sdk_receipt.read_bytes());expected=receipt.get('sdkClassesJarSha256')
    require(receipt.get('sdkBuildKind')=='source-derived-java' and type(expected) is str
            and re.fullmatch('[0-9a-f]{64}',expected),'actual derived SDK class receipt required')
    raw=BRIDGE.read_bytes();bridge_source(raw);checks=['exact readonly source and validation retained after class rename']
    for changed in (raw.replace(b'session.getId()',b'session.toString()'),
                    raw.replace(b'    return value;',b'    session.close();\n    return value;'),
                    raw.replace(b'  private AppSessionIdentity() {}',b'  private AppSessionIdentity() {}\n  static Object observer;'),
                    raw.replace(b'{1,160}',b'{1,161}')):
        require(changed!=raw,'source mutation must apply')
        try:bridge_source(changed)
        except ValueError:checks.append('readonly source mutant rejected')
        else:raise AssertionError('Observer-capable or weakened bridge mutation accepted')
    original=VERIFIER.read_text();tree=ast.parse(original)
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='verify_receipts')
    require(hashlib.sha256(ast.get_source_segment(original,function).encode()).hexdigest()==ORIGINAL_RECEIPTS_SHA256,
            'all original caret receipt/archive/observer gates must remain verbatim')
    observers=next(node.value for node in tree.body if isinstance(node,ast.Assign)
                   and any(isinstance(target,ast.Name) and target.id=='OBSERVERS' for target in node.targets))
    require(ast.literal_eval(observers)==OBSERVER_NAMES,'original observer descriptors must remain unchanged')
    checks.append('original complete caret receipt function and observer descriptors unchanged')
    inputs={str(path.resolve()):sha(path) for path in (BRIDGE,VERIFIER,javac,javap,args.android_jar,args.sdk_receipt)}
    with tempfile.TemporaryDirectory(prefix='app-session-actual-sdk-') as temporary:
        base=Path(temporary)
        if args.sdk_jar is not None:
            jar=args.sdk_jar;require(jar.is_file() and not jar.is_symlink(),'ordinary actual SDK classes JAR required')
            inputs[str(jar.resolve())]=sha(jar)
        else:
            aar=args.sdk_aar;require(aar.is_file() and not aar.is_symlink(),'actual built SDK AAR required')
            inputs[str(aar.resolve())]=sha(aar)
            require(inputs[str(aar.resolve())]==receipt.get('sdkAarSha256'),'actual SDK AAR differs from build receipt')
            with ZipFile(aar) as archive:
                require(archive.namelist().count('classes.jar')==1 and archive.getinfo('classes.jar').file_size<=24*1024*1024,
                        'one bounded actual SDK classes member required')
                jar=base/'classes.jar';jar.write_bytes(archive.read('classes.jar'))
        require(sha(jar)==expected,'actual SDK classes differ from the build receipt')
        with ZipFile(jar) as archive:names=archive.namelist();sdk_class_names(names)
        checks.append('actual receipt-bound SDK has neither application bridge nor reserved observer classes')
        for injected in ('org/mozilla/geckoview/PocketSessionIdentity.class',
                         'org/mozilla/geckoview/PocketGeckoEditableTrace.class',
                         'org/mozilla/geckoview/AppSessionIdentity.class'):
            try:sdk_class_names(names+[injected])
            except ValueError:checks.append('SDK class-index mutation rejected')
            else:raise AssertionError('Application/observer SDK class-index mutation accepted')
        dump=subprocess.run([str(javap),'-p','-c','-classpath',str(jar),'org.mozilla.geckoview.GeckoSession'],
                            capture_output=True,text=True,check=True,timeout=30)
        match=re.search(r'(?m)^  java\.lang\.String getId\(\);\n    Code:\n((?:[ \t]+[0-9]+:[^\n]*\n)+)',dump.stdout)
        require(match is not None,'actual package-private SDK getId bytecode unavailable')
        body=match.group(1);readonly_getter(body);checks.append('actual SDK getter bytecode is a single readonly field return')
        for changed in (body.replace('getfield','invokevirtual'),body.replace('mId:','observer:'),body+'       5: invokestatic #1\n'):
            try:readonly_getter(changed)
            except ValueError:checks.append('getter bytecode mutation rejected')
            else:raise AssertionError('Observer-capable getter bytecode mutation accepted')
        classes=base/'classes';classes.mkdir();empty=base/'empty-source';empty.mkdir()
        command=[str(javac),'-encoding','UTF-8','-source','8','-target','8','-proc:none',
                 '-classpath',str(jar)+':'+str(args.android_jar),'-sourcepath',str(empty),'-d',str(classes),str(BRIDGE)]
        compiled=subprocess.run(command,capture_output=True,text=True,timeout=45)
        require(compiled.returncode==0,'actual SDK/API bridge compile failed: '+compiled.stderr[-3000:])
        require([str(path.relative_to(classes)) for path in classes.rglob('*.class')]==['org/mozilla/geckoview/AppSessionIdentity.class'],
                'compile must emit only the application-owned helper, never SDK replacements')
        checks.append('unmodified helper compiles against actual SDK and Android API without app or SDK doubles')
        bridge_dump=subprocess.run([str(javap),'-p','-c','-classpath',str(classes)+':'+str(jar)+':'+str(args.android_jar),
                                    'org.mozilla.geckoview.AppSessionIdentity'],capture_output=True,text=True,check=True,timeout=30)
        require(len(re.findall(r'invokevirtual[^\n]*GeckoSession.getId:',bridge_dump.stdout))==1,
                'compiled application helper must call the actual SDK getter exactly once')
        checks.append('compiled application helper contains exactly one SDK getId call')
        require(sha(jar)==expected,'actual SDK JAR changed during inspection/compilation')
    require(all(path.is_file() and sha(path)==digest for path,digest in ((Path(name),digest) for name,digest in inputs.items())),
            'source, original guard or actual dependency changed during proof')
    checks.append('SDK, source, receipt and original guard bytes remained unchanged')
    report=dict(schema=1,status='passed',passed=len(checks),checks=checks,sourceFiles={str(BRIDGE.relative_to(ROOT)):sha(BRIDGE)},
        actualSdkClassesJarSha256=expected,sdkReceiptSource=receipt.get('sourceCommit',receipt.get('sdkBuildSource')),
        inputSha256=inputs,executionInputsUnchanged=True,actualSdkApiCompilation=True,actualSdkGetIdReadonlyBytecode=True,
        actualApplicationBridgeOnly=True,originalCaretVerifierUnmodified=True,syntheticSdk=False,syntheticAppClasses=False,
        actualAndroidExecution=False,actualGeckoExecution=False,actualNativeGetIdExecution=False,
        scope='Actual SDK JAR/class index and getter bytecode inspection plus current application bridge API compile. No Gecko instance, observer hook, SDK/native archive mutation or Android/runtime acceptance.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],sdkJarSha256=expected,actualAndroidExecution=False)))


if __name__=='__main__':main()
