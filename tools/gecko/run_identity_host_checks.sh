#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$task_root"
task_output="work/identity-host"
mkdir -p "$task_output/classes"
task_java="${IDENTITY_JAVA:-java}"
if command -v javac >/dev/null 2>&1; then
  task_compiler=(javac)
else
  task_compiler=("$task_java" -m jdk.compiler/com.sun.tools.javac.Main)
fi
"${task_compiler[@]}" -encoding UTF-8 -d "$task_output/classes" \
  app/src/main/java/local/pocketchat/NativeCapabilityManifest.java \
  app/src/main/java/local/pocketchat/EnvironmentResourcePolicy.java \
  app/src/main/java/local/pocketchat/BrowserSettingsPolicy.java \
  tests/browser-runtime/NativeCapabilityManifestTest.java \
  tests/browser-runtime/EnvironmentResourcePolicyTest.java
"$task_java" -cp "$task_output/classes" local.pocketchat.NativeCapabilityManifestTest | tee "$task_output/native-capability-host-results.json"
"$task_java" -cp "$task_output/classes" local.pocketchat.EnvironmentResourcePolicyTest | tee "$task_output/resource-policy-host-results.json"
# Reuse the repository workflow's verified functional JSON library. Android's
# platform jar supplies stubs and cannot execute these asset rejection controls.
task_json="${IDENTITY_JSON_JAR:-${PROFILE_JSON_JAR:-work/profile-host/json.jar}}"
if [[ ! -f "$task_json" && -f work/gecko-integration/catalog-json.jar ]]; then task_json=work/gecko-integration/catalog-json.jar; fi
python3 - "$task_json" <<'PYSDK'
import hashlib,pathlib,sys
path=pathlib.Path(sys.argv[1])
if not path.is_file():raise SystemExit('Set IDENTITY_JSON_JAR to the verified functional JSON-java jar.')
allowed={'3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed','3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796'}
if hashlib.sha256(path.read_bytes()).hexdigest() not in allowed:raise SystemExit('SDK receipt host JSON dependency differs from the pinned workflow inputs.')
PYSDK
"${task_compiler[@]}" -encoding UTF-8 -cp "$task_json:$task_output/classes" -d "$task_output/classes" \
  app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java \
  tests/sdk-receipt-host/android/content/Context.java \
  tests/sdk-receipt-host/android/content/res/AssetManager.java \
  tests/sdk-receipt-host/local/pocketchat/NormalCaretSdkReceiptHostTest.java
"$task_java" -cp "$task_output/classes:$task_json" local.pocketchat.NormalCaretSdkReceiptHostTest | tee "$task_output/sdk-receipt-host-results.json"
python3 -m unittest discover -s tests -p identity_capabilities_test.py
python3 tools/gecko/check_identity_capabilities.py | tee "$task_output/inventory-results.json"
if [[ -f third-party/sdk/native-capability-prototype.json ]]; then
  python3 tools/gecko/check_identity_capabilities.py --prototype third-party/sdk/native-capability-prototype.json
fi
if [[ -f third-party/sdk/environment-resource-budget.json ]]; then
  python3 tools/gecko/check_identity_capabilities.py --resource-budget third-party/sdk/environment-resource-budget.json
fi
