# Current resource recovery boundary

This host compiles the current resource retry, navigation ownership, navigation
deadline, web-observation route matching and resource admission methods. The
CPU, TLS, SDK runtime, main queue and Android URI are explicit host boundaries;
it does not create a Gecko runtime or execute Android or a live website.

All original 34 assertions remain, as do the 42 `resourceCheck` assertions in
`ResourcePressureIntegrationActivity` and its original absolute 60-second
startup guard. The controlled cold-allocation fixture now labels its pending
record `resource-recovery`: this is a synthetic independent resource task, not
a website send or its result. The old fixture selected a localhost page and
then injected a ChatGPT `kind=web` observation while expecting that record to
survive the cross-origin navigation. That setup does not satisfy production
`WebReplyObserver.same` / `bindingRoute` and must not weaken those origin rules.
Byte retention, no resend, admission and asynchronous startup assertions are
unchanged.

The additional six checks cover newer navigation, replaced surface, deleted
owner, initialization callback and status-only callback ownership. A real
ChatGPT same-page task passes the current `webJob`, `navigationStarted`, `same`,
`bindingRoute` and `MainActivity.chatUrl` methods and remains intact throughout
the simulated asynchronous CPU/TLS admission. Cross-page archival deliberately
throws at the declared collaborator boundary; the complete observer and its
archive behavior run in `tests/browser-navigation-lifecycle-host`.

```sh
python3 tests/resource-recovery-host/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json-20250517.jar \
  --output /path/to/resource-recovery.json
```

The original `sync-runtime-only` and `pretend-allocation-ready` mutations must
still fail their original semantic assertions. `obsolete-navigation-owner`
must fail the newer-navigation assertion. The previous whole-member historical
retry hash was removed because the retry intentionally gained ownership guards;
it is not replaced with a historical source adapter or a weaker behavior test.
