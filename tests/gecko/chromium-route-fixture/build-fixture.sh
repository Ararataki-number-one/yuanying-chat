#!/usr/bin/env bash
set -euo pipefail

fixture_dir=$(cd -- "$(dirname -- "$0")" && pwd)
sdk_dir="${ANDROID_SDK_ROOT:-${ANDROID_HOME:?Set ANDROID_SDK_ROOT or ANDROID_HOME}}"
tools_dir="$sdk_dir/build-tools/37.0.0"
jdk_dir="${JAVA_HOME:?Set JAVA_HOME to JDK 25}"
export PATH="$jdk_dir/bin:$PATH"
android_api="$sdk_dir/platforms/android-37.1/android.jar"
cefrium_input="${1:?Input verified Cefrium SDK AAR or classes.jar}"
output="${2:?Output path for unsigned instrumentation APK}"
target="${3:-local.pocketchat}"
case "$target" in
    local.pocketchat|local.pocketchat.test) ;;
    *) printf '%s\n' 'Unexpected fixture target' >&2; exit 2 ;;
esac
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/classes" "$work/dex" "$work/assets"
cp "$fixture_dir/../assets/network-fixture.p12" "$work/assets/chromium-proxy-fixture.p12"

case "$cefrium_input" in
    *.aar)
        cefrium_api="$work/cefrium.jar"
        unzip -p "$cefrium_input" classes.jar > "$cefrium_api"
        ;;
    *.jar)
        cefrium_api="$cefrium_input"
        ;;
    *)
        printf '%s\n' 'Expected Cefrium SDK AAR or classes.jar' >&2
        exit 2
        ;;
esac

"$jdk_dir/bin/javac" --release 17 -cp "$android_api:$cefrium_api" \
    -d "$work/classes" "$fixture_dir/RouteFixture.java" "$fixture_dir/LoopbackProxy.java"
"$tools_dir/d8" -JXmx384m --min-api 29 --lib "$android_api" --classpath "$cefrium_api" \
    --output "$work/dex" "$work/classes/local/pocketchat/chromiumfixture/"*.class
sed "s/android:targetPackage=\"local.pocketchat\"/android:targetPackage=\"$target\"/" \
    "$fixture_dir/AndroidManifest.xml" > "$work/AndroidManifest.xml"
"$tools_dir/aapt2" link -I "$android_api" -A "$work/assets" --manifest "$work/AndroidManifest.xml" -o "$work/manifest.apk"
zip -jq "$work/manifest.apk" "$work/dex/classes.dex"
"$tools_dir/zipalign" -f 4 "$work/manifest.apk" "$output"
