# Native compilation of the ten UX rounds

This check compiles every complete Java source listed in `production-sources.json` together against an actual Android SDK `android.jar`, using JDK 17. The list covers the changed shell, download, environment, continuity, saved-file lease sources, and the follow-up frame coalescing, indexed search, refresh gate, and row-presentation performance sources. It remains reproducible after the changes are committed; it does not depend on an uncommitted Git diff.

```bash
python3 tests/ux-native-compile/run.py \
  --java-home /path/to/jdk17 \
  --android-jar /path/to/android-sdk/platforms/android-37.1/android.jar \
  --output work/ux-native-check
```

`BoundaryGenerator.java` parses the repository's other application classes with the JDK compiler API and writes compilation-only application boundaries under the output directory. It preserves their declared API signatures, inheritance, and literal constants, removes initializers, and replaces method bodies with `UnsupportedOperationException`. Browser members whose signatures require Mozilla types are omitted. It defines no `org.mozilla` package and supplies no replacement Gecko SDK. The production files being checked are read directly, without rewriting or copying their bodies into a surrogate.

The Chromium sources also require the actual AndroidX WebKit dependency jar. Pass it with `--classpath-jar /path/to/webkit/classes.jar`; this option is repeatable and each dependency hash is recorded. The expanded network-provider scope uses two explicitly erased application-boundary fields: `GeckoWebView.current` is an opaque `Object` for identity comparisons, and `GeckoWebView.surface` is an Android `View` for inherited input-fence methods. No Mozilla methods or runtime classes are supplied by these boundaries.

The generated helpers are never executed. This catches Java syntax, Android API use, and cross-feature application method/field integration errors in the listed files. It does not validate browser internals, resource linking, native libraries, APK assembly, Android lifecycle behavior, or device rendering. A passing receipt explicitly reports `fullAppBuild: false` and `actualAndroidExecution: false`; full Gradle and device checks remain necessary for an installable release.

`receipt.json` records the exact production source hashes, Android API hash, compiler version, source commit/dirty state, boundary generator hash, and actual command. It also hashes the application boundary source inputs before and after compilation, and fails if concurrent edits change an execution input. `javac.log` contains compiler diagnostics. Do not ship generated helper classes in the application.
