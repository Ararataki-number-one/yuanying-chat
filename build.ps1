param([switch]$Test,[switch]$Development,[switch]$Personal,[string]$PersonalDefaultsFile,[string]$ToolsRoot)
$ErrorActionPreference='Stop'
if($Personal -or $PersonalDefaultsFile){throw 'Gecko builds do not package private presets. Use the standard build.'}
if($Development){throw 'Use a separate development build configuration; production and integration builds disable debugging.'}
if($ToolsRoot){$env:ANDROID_HOME=$ToolsRoot}
Push-Location $PSScriptRoot
try {
  $task=if($Test){':app:assembleIntegration'}else{':app:assembleRelease'}
  if($IsLinux -or $IsMacOS){& ./gradlew $task}else{& ./gradlew.bat $task}
  if($LASTEXITCODE -ne 0){throw "Gradle build failed: $LASTEXITCODE"}
  Write-Output 'Built APKs are in app/build/outputs/apk/. Release APKs are unsigned; see docs/BUILD.md for original signing.'
} finally {Pop-Location}
