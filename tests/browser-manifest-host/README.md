# Manifest runtime-name grammar

`run.py --java-home /path/to/jdk --output work/name-checks.json` checks literal
package, process and task-affinity names in the main, integration, update and
input-driver manifests, plus the generated Gecko manifest when present.
The mandatory browser workflow contract test runs it before Android phases.

`AospManifestNames.java` contains three unmodified method excerpts from AOSP
Android 15 `PackageParser.java`; the original URL, full-source hash and excerpt
hashes are recorded in `aosp-provenance.json`. Its filename-only dependency is
an explicit throwing boundary, because task/process callers do not request
filename validation. This executes the actual name-grammar methods on a JVM.
It does not execute Android PackageManager, validate the entire APK manifest,
or replace the mandatory installation and device acceptance checks.

Fifteen positive/negative controls include the rejected original
`local.pocketchat.test.browser-probe` affinity, valid `browser_probe`, private
process names, illegal hyphens, leading digits, slashes and whitespace.
