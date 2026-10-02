"""Build a same-signature instrumentation sidecar for the disposable emulator only."""
import os, pathlib, subprocess, zipfile
repo=pathlib.Path(__file__).resolve().parents[2]
setup=repo/'work/cloud-setup'; out=repo/'work/upgrade-qa'; out.mkdir(parents=True,exist_ok=True)
java=setup/'jdk/usr/lib/jvm/java-17-openjdk-amd64'; tools=setup/'build/android-15'; platform=setup/'platform/android-35/android.jar'
(out/'classes').mkdir(exist_ok=True); (out/'dex').mkdir(exist_ok=True)
manifest=out/'AndroidManifest.xml'
manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="local.pocketchat.upgradeqa" android:versionCode="1" android:versionName="1"><uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35"/><application android:label="Upgrade fixture" android:debuggable="true"/><instrumentation android:name="local.pocketchat.upgradeqa.UpgradeRegression" android:targetPackage="local.pocketchat"/></manifest>')
def run(*args): subprocess.run([str(x) for x in args],cwd=repo,check=True)
run(java/'bin/javac','-encoding','UTF-8','-source','8','-target','8','-classpath',platform,'-d',out/'classes',repo/'tests/upgrade/UpgradeRegression.java')
run(java/'bin/jar','cf',out/'classes.jar','-C',out/'classes','.')
run(java/'bin/java','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--lib',platform,'--min-api','26','--output',out/'dex',out/'classes.jar')
run(tools/'aapt2','link','-o',out/'base.apk','-I',platform,'--manifest',manifest)
with zipfile.ZipFile(out/'base.apk','a',zipfile.ZIP_DEFLATED) as archive:
    for dex in (out/'dex').glob('*.dex'): archive.write(dex,dex.name)
run(tools/'zipalign','-f','-p','4',out/'base.apk',out/'aligned.apk')
os.environ['JAVA_HOME']=str(java)
os.environ['UPGRADE_QA_SIGN_PASS']=os.environ.get('UPGRADE_QA_SIGN_PASS','android')
run(java/'bin/java','-jar',tools/'lib/apksigner.jar','sign','--ks',repo/'work/android-test/private/local-test.jks','--ks-key-alias','local','--ks-pass','env:UPGRADE_QA_SIGN_PASS','--key-pass','env:UPGRADE_QA_SIGN_PASS','--out',out/'upgrade-fixture.apk',out/'aligned.apk')
run(java/'bin/java','-jar',tools/'lib/apksigner.jar','verify',out/'upgrade-fixture.apk')
print('Built emulator-only instrumentation sidecar')
