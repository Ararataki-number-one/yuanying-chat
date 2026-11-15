# Gecko environment context callback regression

API 32 inherits `Context.registerComponentCallbacks()` through `ContextWrapper`.
The framework method calls `getApplicationContext().registerComponentCallbacks()`.
The Gecko adapter intentionally returns itself from `getApplicationContext()`;
its profile base also resolves to a cached profile context. Either inherited
dispatch or simple delegation to that profile therefore recurses.

The production adapter forwards only callback registration and unregistration
through the existing `Profiles.global(getBaseContext())` helper. Its application
identity, profile storage, and service isolation remain unchanged.

Run with a real JDK 17:

```sh
python tests/gecko-environment-context-host/run.py \
  --java-home /absolute/path/to/jdk-17 \
  --output /absolute/path/to/context-callbacks.json
```

The harness executes the complete current adapter and selected current profile
methods. Android type names are replaced with explicitly named host boundaries.
The Android 12L callback methods and callback controller are taken from the
`android-12.1.0_r1` AOSP source; source URLs and SHA-256 receipts are recorded in
`android32-callbacks.json`. The controller retains its Apache 2.0 license header.
These are JVM checks, not Android or Gecko runtime execution.

Cases verify callback delivery, exact unregistration, cached profile identity,
separate preferences and directories, ordinary and executor service routing,
isolated service instance names, and unsupported child-process rejection for
environments 0, 2, and 7. Four compiled counterexamples reject inherited API 32
recursion, delegation to the still-isolated profile base, lost unregistration,
and replacing the adapter's application context with the global application.
Real emulator startup remains the end-to-end acceptance gate.
