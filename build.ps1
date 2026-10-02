param([switch]$Test,[switch]$Development,[switch]$Personal,[string]$PersonalDefaultsFile,[string]$ToolsRoot)
if($Personal -and ($Test -or $Development)){throw "Personal defaults are only allowed in the release build"}
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$workspaceRoot=$projectRoot
if(!$ToolsRoot){$ToolsRoot=Join-Path $workspaceRoot 'work/android-tools'}
$javaRoot=(Get-ChildItem (Join-Path $toolsRoot 'java') -Directory | Select-Object -First 1).FullName
$buildRoot=(Get-ChildItem (Join-Path $toolsRoot 'build') -Directory | Select-Object -First 1).FullName
$platformRoot=(Get-ChildItem (Join-Path $toolsRoot 'platform') -Directory | Select-Object -First 1).FullName
$env:JAVA_HOME=$javaRoot
$env:PATH="$javaRoot/bin;$env:PATH"
$variant=if($Personal){'personal'}elseif($Test){'test'}elseif($Development){'development'}else{'release'}
$outDir=Join-Path $workspaceRoot "work/android-test/build-1.4.1-$variant"
New-Item -ItemType Directory -Force "$outDir/classes","$outDir/dex","$outDir/assets" | Out-Null
Copy-Item "$projectRoot/app/src/main/assets/*" "$outDir/assets" -Recurse -Force
if($Personal){
  $packer=Join-Path $workspaceRoot 'work/android-ui/PackagePersonalDefaults.exe'
  if(!(Test-Path -LiteralPath $packer)){throw 'Personal preset packer is not available. Use the standard build for distributable source.'}
  if($PersonalDefaultsFile){
    $privateJson=Get-Content -LiteralPath $PersonalDefaultsFile -Raw | ConvertFrom-Json
    foreach($name in @('subscriptionUrl','exitHost','exitPort','exitUser','exitPassword')){if(!$privateJson.PSObject.Properties[$name]){throw 'Personal profile is incomplete'}}
    Copy-Item -LiteralPath $PersonalDefaultsFile -Destination (Join-Path $outDir 'assets/personal-network.json') -Force
    'Personal defaults packaged from the existing Android profile; values not printed.'
  }else{
    & $packer (Join-Path $workspaceRoot 'outputs/gpt-pro-helper') (Join-Path $outDir 'assets/personal-network.json')
    if($LASTEXITCODE -ne 0){throw 'Personal defaults could not be packaged'}
  }
}
$manifest=Get-Content "$projectRoot/app/src/main/AndroidManifest.xml" -Raw
if($Development){$manifest=$manifest.Replace('android:debuggable="false"','android:debuggable="true"')}
$sources=@(Get-ChildItem "$projectRoot/app/src/main/java" -Filter *.java -Recurse | ForEach-Object {$_.FullName})
$libraries=@(Get-ChildItem "$projectRoot/libs" -Filter *.jar | ForEach-Object {$_.FullName})
if($Test){
  $manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.DownloadCenterTestActivity" android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden" /><activity android:name="local.pocketchat.WindowHomeTestActivity" android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden" /><activity android:name="local.pocketchat.DefaultDownloadTestActivity" android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden" /></application>')
  $manifest=$manifest.Replace('local.pocketchat.saved-downloads','local.pocketchat.test.saved-downloads')
  $manifest=$manifest.Replace('package="local.pocketchat"','package="local.pocketchat.test"').Replace('android:debuggable="false"','android:debuggable="true"').Replace('android:label="元婴期院士"','android:label="元婴期院士测试"').Replace('local.pocketchat.MainActivity','local.pocketchat.TestActivity')
  $manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.WebEntryBenchmarkActivity" android:exported="true" /><activity android:name="local.pocketchat.StartupRouteTestActivity" android:exported="true" /><activity android:name="local.pocketchat.NetworkPriorityTestActivity" android:exported="true" /><service android:name="local.pocketchat.ShieldFixtureVpnService" android:permission="android.permission.BIND_VPN_SERVICE" android:exported="false"><intent-filter><action android:name="android.net.VpnService" /></intent-filter></service><activity android:name="local.pocketchat.EnvironmentNetworkSmokeActivity" android:exported="true" /><activity android:name="local.pocketchat.FunctionalHubTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ExpandedProfileTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ExpandedProfileProbeActivity" android:process=":profile7" android:exported="false" /><activity android:name="local.pocketchat.EnvironmentAuditTestActivity" android:exported="true" /><activity android:name="local.pocketchat.NetworkShieldTestActivity" android:exported="true" /><activity android:name="local.pocketchat.PrivacyTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ProfileSessionTestActivity" android:process=":profile1" android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden" /><activity android:name="local.pocketchat.ProfileIsolationTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ProfileProbeActivity1" android:process=":profile1" android:exported="false" /><activity android:name="local.pocketchat.ProfileProbeActivity2" android:process=":profile2" android:exported="false" /><activity-alias android:name="local.pocketchat.ProfileProbe1" android:targetActivity="local.pocketchat.ProfileProbeActivity1" android:exported="false" /><activity-alias android:name="local.pocketchat.ProfileProbe2" android:targetActivity="local.pocketchat.ProfileProbeActivity2" android:exported="false" /><activity android:name="local.pocketchat.ContinuityTestActivity" android:exported="true" /><activity android:name="local.pocketchat.NotificationTargetTestActivity" android:exported="true" android:launchMode="singleTask" android:configChanges="orientation|screenSize|keyboardHidden" /><activity-alias android:name="local.pocketchat.MainActivity" android:targetActivity="local.pocketchat.NotificationTargetTestActivity" android:exported="false" /><activity android:name="local.pocketchat.WebPerformanceTestActivity" android:exported="true" /><activity android:name="local.pocketchat.WebPerformanceBenchmarkActivity" android:exported="true" /><activity android:name="local.pocketchat.WebReplyTestActivity" android:exported="true" /><activity android:name="local.pocketchat.WebReplyBackgroundTestActivity" android:exported="true" /><activity android:name="local.pocketchat.WebReplyRecoveryTestActivity" android:exported="true" /><activity android:name="local.pocketchat.NetworkProbeActivity" android:exported="true" /></application>')
  $manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.BackgroundTestActivity" android:exported="true" /><activity android:name="local.pocketchat.DevStatusActivity" android:exported="true" /></application>')
  $manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.HistoryTestActivity" android:exported="true" /><activity android:name="local.pocketchat.PreviewTestActivity" android:exported="true" /><activity android:name="local.pocketchat.OptimizationTestActivity" android:exported="true" /><activity android:name="local.pocketchat.SavedFileTestActivity" android:exported="true" /><activity android:name="local.pocketchat.DownloadFlowTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ReaderWindowTestActivity" android:exported="true" /><activity android:name="local.pocketchat.AttachmentGateTestActivity" android:exported="true" /><activity android:name="local.pocketchat.CompactModeTestActivity" android:exported="true" /><activity android:name="local.pocketchat.NetworkMetricsTestActivity" android:exported="true" /><activity android:name="local.pocketchat.RouteQualityTestActivity" android:exported="true" /><activity android:name="local.pocketchat.DeliveryTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ImagesTestActivity" android:exported="true" /><activity android:name="local.pocketchat.DraftTestActivity" android:exported="true" /><activity android:name="local.pocketchat.ActionsTestActivity" android:exported="true" /><provider android:name="local.pocketchat.DownloadFixtureProvider" android:authorities="local.pocketchat.download-fixture" android:exported="false" android:grantUriPermissions="true" /><activity android:name="local.pocketchat.QuickSetupTestActivity" android:exported="true" /><activity android:name="local.pocketchat.RecoveryTestActivity" android:exported="true" /><activity android:name="local.pocketchat.NetworkFaultActivity" android:exported="true" /><activity android:name="local.pocketchat.CompletionTestActivity" android:exported="true" /><activity android:name="local.pocketchat.LoadingTestActivity" android:exported="true" /><activity android:name="local.pocketchat.MediaTestActivity" android:exported="true" /><provider android:name="local.pocketchat.MediaFixtureProvider" android:authorities="local.pocketchat.fixturefiles" android:exported="false" android:grantUriPermissions="true" /></application>')
  $manifest=$manifest.Replace('android:exported="true" />','android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden" />')
  $sources+=@(Get-ChildItem "$projectRoot/tests" -Filter *.java | ForEach-Object {$_.FullName})
  Copy-Item "$projectRoot/tests/fixture.html" "$outDir/assets/fixture.html" -Force
  Copy-Item "$projectRoot/tests/fixture-continuity.html" "$outDir/assets/fixture-continuity.html" -Force
  Copy-Item "$projectRoot/tests/fixture-web-reply.html" "$outDir/assets/fixture-web-reply.html" -Force
  Copy-Item "$projectRoot/tests/fixture-web-performance.html" "$outDir/assets/fixture-web-performance.html" -Force
  Copy-Item "$projectRoot/tests/fixture-history.html" "$outDir/assets/fixture-history.html" -Force
  Copy-Item "$projectRoot/tests/fixture-actions.html" "$outDir/assets/fixture-actions.html" -Force
  Copy-Item "$projectRoot/tests/fixture-media.html" "$outDir/assets/fixture-media.html" -Force
}
if($Development -and !$Test){$sources+=@(Get-Item "$projectRoot/tests/DraftRepairActivity.java" | ForEach-Object {$_.FullName});$manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.DraftRepairActivity" android:exported="true" /></application>');$sources+=@(Get-Item "$projectRoot/tests/DefaultExportActivity.java" | ForEach-Object {$_.FullName});$manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.DefaultExportActivity" android:exported="true" /></application>');$sources+=@(Get-Item "$projectRoot/tests/NetworkFaultActivity.java" | ForEach-Object {$_.FullName});$manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.NetworkFaultActivity" android:exported="true" /></application>');$sources+=@(Get-Item "$projectRoot/tests/DevStatusActivity.java" | ForEach-Object {$_.FullName});$manifest=$manifest.Replace('</application>','<activity android:name="local.pocketchat.DevStatusActivity" android:exported="true" /></application>')}
[IO.File]::WriteAllText("$outDir/AndroidManifest.xml",$manifest,[Text.UTF8Encoding]::new($false))
function Check([string]$Step){if($LASTEXITCODE -ne 0){throw "$Step failed: $LASTEXITCODE"}}
& "$buildRoot/aapt2.exe" compile --dir "$projectRoot/app/src/main/res" -o "$outDir/resources.zip"
Check 'resource compile'
& "$buildRoot/aapt2.exe" link -o "$outDir/base.apk" -I "$platformRoot/android.jar" --manifest "$outDir/AndroidManifest.xml" -A "$outDir/assets" "$outDir/resources.zip"
Check 'resource link'
& "$javaRoot/bin/javac.exe" -encoding UTF-8 -source 8 -target 8 -classpath ("$platformRoot/android.jar;"+($libraries -join ';')) -d "$outDir/classes" $sources
Check 'Java compile'
& "$javaRoot/bin/jar.exe" cf "$outDir/classes.jar" -C "$outDir/classes" .
Check 'class archive'
& "$javaRoot/bin/java.exe" -cp "$buildRoot/lib/d8.jar" com.android.tools.r8.D8 --lib "$platformRoot/android.jar" --min-api 26 --output "$outDir/dex" "$outDir/classes.jar" $libraries
Check 'DEX compile'
Copy-Item "$outDir/base.apk" "$outDir/unsigned.apk" -Force
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::Open("$outDir/unsigned.apk",'Update')
try{
  foreach($entry in @($zip.Entries | Where-Object {$_.FullName.Contains('\')})){
    $name=$entry.FullName.Replace('\','/');$buffer=[IO.MemoryStream]::new();$stream=$entry.Open();$stream.CopyTo($buffer);$stream.Dispose();$entry.Delete()
    $newEntry=$zip.CreateEntry($name);$stream=$newEntry.Open();$buffer.Position=0;$buffer.CopyTo($stream);$stream.Dispose();$buffer.Dispose()
  }
  Get-ChildItem "$outDir/dex" -Filter *.dex | ForEach-Object {[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$_.FullName,$_.Name) | Out-Null}
  $nativeRoot=Join-Path $projectRoot 'app/src/main/jniLibs'
  if(Test-Path $nativeRoot){Get-ChildItem $nativeRoot -Recurse -Filter *.so | ForEach-Object {$entry='lib/'+$_.FullName.Substring($nativeRoot.Length+1).Replace('\','/');[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$_.FullName,$entry) | Out-Null}}
}finally{$zip.Dispose()}
& "$buildRoot/zipalign.exe" -f -p 4 "$outDir/unsigned.apk" "$outDir/aligned.apk"
Check 'APK alignment'
$keyDir=Join-Path $workspaceRoot 'work/android-test/private'
New-Item -ItemType Directory -Force $keyDir | Out-Null
$keyFile=Join-Path $keyDir 'local-test.jks'
if(!(Test-Path $keyFile)){
  & "$javaRoot/bin/keytool.exe" -genkeypair -keystore $keyFile -storepass android -keypass android -alias local -dname 'CN=Local Pocket Chat Prototype' -keyalg RSA -keysize 2048 -validity 3650
  Check 'signing key'
}
$distributionDir=Join-Path $workspaceRoot 'dist'
New-Item -ItemType Directory -Force $distributionDir | Out-Null
$apk=Join-Path $distributionDir $(if($Personal){'PocketChat-1.4.1-personal.apk'}elseif($Test){'PocketChat-tests.apk'}elseif($Development){'PocketChat-dev.apk'}else{'PocketChat-1.4.1.apk'})
& "$javaRoot/bin/java.exe" -jar "$buildRoot/lib/apksigner.jar" sign --ks $keyFile --ks-key-alias local --ks-pass pass:android --key-pass pass:android --out $apk "$outDir/aligned.apk"
Check 'APK sign'
& "$javaRoot/bin/java.exe" -jar "$buildRoot/lib/apksigner.jar" verify --verbose $apk
Check 'APK verify'
Get-FileHash $apk -Algorithm SHA256 | Format-List


