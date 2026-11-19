#!/usr/bin/env bash
# Both OS lanes consume the same x86_64 debug APK pair compiled in this CI job.
set -euo pipefail
sdk=${1:?Android API required}
mode=${2:?Test scope required}
case "$sdk:$mode" in
  33:routes) android=android13; image=android-33 ;;
  37:smoke) android=android17; image=android-37.0 ;;
  *) printf '%s\n' 'Unexpected Chromium emulator test scope' >&2; exit 2 ;;
esac
work="$PWD/work/chromium-delivery"
tools="$ANDROID_HOME/build-tools/37.0.0"
adb_bin="$ANDROID_HOME/platform-tools/adb"
serial=emulator-5554
adb_device=("$adb_bin" -s "$serial")
export ANDROID_AVD_HOME="$work/$android-avd" ANDROID_USER_HOME="$work/$android-user" ANDROID_EMULATOR_HOME="$work/$android-emulator-home"
mkdir -p "$ANDROID_AVD_HOME" "$ANDROID_USER_HOME" "$ANDROID_EMULATOR_HOME"
sudo chmod a+rw /dev/kvm
echo no | "$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" create avd --force -n chromiumdelivery -p "$ANDROID_AVD_HOME/chromiumdelivery.avd" -k "system-images;$image;google_apis;x86_64"
graphics=(-gpu swiftshader)
if (( sdk == 37 )); then
  # Android 17 SurfaceFlinger requires Gfxstream DMA color-buffer readback.
  graphics+=(-feature GLDirectMem -feature HasSharedSlotsHostMemoryAllocator)
fi
"$ANDROID_HOME/emulator/emulator" -avd chromiumdelivery -no-window -no-audio -no-snapshot -no-boot-anim -no-metrics -accel on -port 5554 "${graphics[@]}" -memory 4096 -cores 4 > "$work/$android-emulator.log" 2>&1 &
emulator_pid=$!
stop_guest() {
  local status=$?
  if (( status != 0 )); then
    timeout 15 "${adb_device[@]}" logcat -d -b crash -t 1500 -v threadtime > "$work/$android-crash.log" 2>&1 || true
    timeout 15 "${adb_device[@]}" logcat -d -b main -b system -t 3000 -v threadtime \
      AndroidRuntime:V libc:V linker:V DEBUG:V chromium:V Cefrium:V cefrium:V \
      PocketChatCefriumRouteFixture:V ActivityManager:I ActivityTaskManager:I '*:S' \
      > "$work/$android-native-logcat.txt" 2>&1 || true
  fi
  "${adb_device[@]}" emu kill >/dev/null 2>&1 || kill "$emulator_pid" 2>/dev/null || true
  wait "$emulator_pid" || true
  # This job owns these three fresh synthetic guest directories. Keep logs outside them.
  rm -rf -- "$ANDROID_AVD_HOME" "$ANDROID_USER_HOME" "$ANDROID_EMULATOR_HOME"
}
trap stop_guest EXIT
timeout 180 "${adb_device[@]}" wait-for-device
timeout 180 bash -c 'until [ "$("$1" -s "$2" shell getprop sys.boot_completed | tr -d "\r")" = 1 ] && "$1" -s "$2" shell pm path android | grep -q "^package:"; do sleep 2; done' _ "$adb_bin" "$serial"
test "$("${adb_device[@]}" shell getprop ro.kernel.qemu | tr -d '\r')" = 1
test "$("${adb_device[@]}" shell getprop ro.build.version.sdk | tr -d '\r')" = "$sdk"
if [[ "$mode" == routes ]]; then
  # Android may automatically re-enable the default provider once. Check that the
  # guest has no current WebView provider before exercising the independent engine.
  webview_state="$work/$android-webview.txt"
  if ! timeout 90 bash -c '
    set -euo pipefail
    adb_device=("$1" -s "$2")
    state="$3"
    stable=0
    while true; do
      changed=0
      for provider in com.android.webview com.google.android.webview com.android.chrome; do
        if "${adb_device[@]}" shell pm list packages -e --user 0 "$provider" |
            tr -d "\r" | grep -Fx "package:$provider" >/dev/null; then
          "${adb_device[@]}" shell pm disable-user --user 0 "$provider"
          changed=1
        fi
      done
      "${adb_device[@]}" shell dumpsys webviewupdate > "$state"
      if (( changed == 0 )) && grep -Eiq "Current WebView package.*(null|none)" "$state"; then
        stable=$((stable + 1))
        if (( stable == 2 )); then exit 0; fi
      else
        stable=0
      fi
      sleep 2
    done
  ' _ "$adb_bin" "$serial" "$webview_state"; then
    if [[ -f "$webview_state" ]]; then cat "$webview_state" >&2; fi
    echo 'No stable system-WebView-free state was observed within 90 seconds.' >&2
    exit 1
  fi
  "${adb_device[@]}" shell dumpsys webviewupdate | tee "$work/$android-webview.txt"
  grep -Ei 'Current WebView package.*(null|none)' "$work/$android-webview.txt"
else
  # Leave the API 37 guest intact. The fixture disables WebView in the app process.
  "${adb_device[@]}" shell dumpsys webviewupdate | tee "$work/$android-webview.txt"
fi
"${adb_device[@]}" shell cmd connectivity airplane-mode enable
"${adb_device[@]}" shell svc wifi disable
"${adb_device[@]}" shell svc data disable
timeout 60 bash -c 'until "$1" -s "$2" shell dumpsys connectivity | grep -Eiq "^ *Active default network: *(none|null) *$"; do sleep 2; done' _ "$adb_bin" "$serial"

signer=$("$tools/apksigner" verify --print-certs "$work/debug/base-master.apk" | sed -nE 's/^.*certificate SHA-256 digest: ([a-f0-9]{64})$/\1/p' | sort -u)
read -r version version_code < <(python3 - <<'PY'
import pathlib,re
config=pathlib.Path('app/build.gradle').read_text()
print(re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",config)[1],re.search(r'versionCode ([0-9]+)',config)[1])
PY
)
report="$work/host-report.json"
renderer_log="$work/renderer.txt"
host_mode=()
fixture_mode=()
if [[ "$mode" == smoke ]]; then
  report="$work/android17-smoke.json"
  renderer_log="$work/android17-renderer.txt"
  host_mode=(--api37-compatibility)
  fixture_mode=(-e fixtureMode api37-process-webview-disabled)
fi
python3 tests/gecko/run_chromium_delivery.py --adb "$adb_bin" --serial "$serial" --disposable-emulator --aapt2 "$tools/aapt2" --apksigner "$tools/apksigner" --base "$work/debug/base-master.apk" --splits "$work/debug" --version "$version" --version-code "$version_code" --abi x86_64 --signer "$signer" --output "$report" "${host_mode[@]}"

wait_for_test_network() {
  "${adb_device[@]}" shell cmd connectivity airplane-mode disable
  "${adb_device[@]}" shell svc wifi enable
  "${adb_device[@]}" shell svc data enable
  timeout 90 bash -c 'until "$1" -s "$2" shell dumpsys connectivity | grep -Eq "^ *Active default network: *[0-9]+"; do sleep 2; done' _ "$adb_bin" "$serial"
}
fixture=local.pocketchat.chromiumfixture/.RouteFixture
"${adb_device[@]}" install -t "$work/fixture.apk"
wait_for_test_network
nonce=$(jq -er .runNonce "$report")
base_sha=$(jq -er .apkSet.base.sha256 "$report")
feature_sha=$(jq -er .apkSet.chromium.sha256 "$report")
timeout 300 "${adb_device[@]}" shell am instrument -w -e runNonce "$nonce" -e baseSha256 "$base_sha" -e featureSha256 "$feature_sha" "${fixture_mode[@]}" "$fixture" | tee "$renderer_log"
if [[ "$mode" == smoke ]]; then
  python3 tests/gecko/run_chromium_delivery.py join-api37-renderer --host-report "$report" --renderer-log "$renderer_log" --output "$work/android17-compatibility-results.json"
  exit 0
fi
python3 tests/gecko/run_chromium_delivery.py join-renderer --host-report "$report" --renderer-log "$renderer_log" --output "$work/chromium-debug-render.json"

"${adb_device[@]}" shell am force-stop local.pocketchat
"${adb_device[@]}" install-multiple -t "$work/integration/base-master.apk" "$work/integration/chromium-master.apk"
"${adb_device[@]}" install -r -t "$work/integration-fixture.apk"
"${adb_device[@]}" shell appops set local.pocketchat.test ACTIVATE_VPN allow
source=$(git rev-parse HEAD)
tree=$(git rev-parse 'HEAD^{tree}')
base_sha=$(sha256sum "$work/integration/base-master.apk" | cut -d ' ' -f 1)
feature_sha=$(sha256sum "$work/integration/chromium-master.apk" | cut -d ' ' -f 1)
core_sha=$(unzip -p "$work/integration/base-master.apk" 'lib/x86_64/libmihomo.so' | sha256sum | cut -d ' ' -f 1)
for route in vpn internal; do
  wait_for_test_network
  args=(-w -e fixtureMode "$route" -e sourceCommit "$source" -e sourceTree "$tree" -e runNonce "$nonce"
        -e baseSha256 "$base_sha" -e featureSha256 "$feature_sha")
  if [[ "$route" == internal ]]; then args+=(-e coreSha256 "$core_sha"); fi
  timeout 300 "${adb_device[@]}" shell am instrument "${args[@]}" "$fixture" | tee "$work/wire-$route.txt"
done
python3 tools/gecko/chromium_release_publication.py join-routes --debug "$work/chromium-debug-render.json" --vpn "$work/wire-vpn.txt" --internal "$work/wire-internal.txt" --nonce "$nonce" --base-sha "$base_sha" --feature-sha "$feature_sha" --core-sha "$core_sha" --output "$work/chromium-ondemand-device-results.json"
