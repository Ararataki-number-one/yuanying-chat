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
  tests/browser-runtime/NativeCapabilityManifestTest.java \
  tests/browser-runtime/EnvironmentResourcePolicyTest.java
"$task_java" -cp "$task_output/classes" local.pocketchat.NativeCapabilityManifestTest | tee "$task_output/native-capability-host-results.json"
"$task_java" -cp "$task_output/classes" local.pocketchat.EnvironmentResourcePolicyTest | tee "$task_output/resource-policy-host-results.json"
python3 -m unittest discover -s tests -p identity_capabilities_test.py
python3 tools/gecko/check_identity_capabilities.py | tee "$task_output/inventory-results.json"
if [[ -f third-party/sdk/native-capability-prototype.json ]]; then
  python3 tools/gecko/check_identity_capabilities.py --prototype third-party/sdk/native-capability-prototype.json
fi
if [[ -f third-party/sdk/environment-resource-budget.json ]]; then
  python3 tools/gecko/check_identity_capabilities.py --resource-budget third-party/sdk/environment-resource-budget.json
fi
