# Actual Java IP bootstrap and native completion boundary

Run `python3 tests/gecko-ip-transport-host/run.py --java-home /path/to/jdk17 --json-jar /path/to/real-json.jar --output /tmp/ip-transport.json` for each supported real JSON jar.

Current complete GeckoWebView declarations are extracted verbatim, with only
explicit SDK/OS/app boundary type names changed. The real controller, store,
spec, strict IP policy, callback registry, process route lease registry, network
pool identity, address policies and hash implementation compile in full. The
existing core host supplies declared Context/catalog/plain atomic-vault adapters.
Current native port/message delegates execute, including extension-environment,
exact request-id, native port, token, route and source checks. The actual route
watcher's memory Snapshot/update/updateLinks methods also execute.

The combined sequence exercises SDK window readiness, geo packet publication,
strict geo result parsing, native context read, native effective IANA apply,
actual store writer publication and UI ownership completion. Real route leases
must remain held across every native and writer boundary, then release only at
the actual final gate or retirement. Guard, proxy/DNS/network, runtime, session,
open gate, document, configuration, owner, timeout and close changes deny stale
work. First route availability and visible-document preservation run actual
lifecycle methods. Initial timeout failure stops the spinner without invoking
network recovery and retains its exact target. Late actual error/progress/location
delegates cannot overwrite that failure. Only a new explicit navigation can run
the actual `loadUrl`/retry/full `reopenIpCurrent` sequence, retire the old window,
then query/apply/commit again before the retained target reaches SDK `loadUri`.
SDK window creation/open/close/surface and `loadUri` effects remain declared
boundaries; existing live tasks, drafts and visible documents prevent replacement.

No Gecko, HTTP, native BC, page Date/Intl or Worker executes on this JVM. UA,
native ACK and geo body inputs are synthetic. Extension HTTP principal and HTTP
request-id authorization, omitted credentials and redirect/read cancellation
belong to the separately mandatory actual-JavaScript producer suites; Java's
native-message sender and callback-id tests do not substitute for those. No
org.mozilla fake SDK classes are introduced. Handler time and SDK/OS objects are
named boundaries; SQLite and Android Keystore are not modeled as real crypto.

Each semantic mutation separately compiles after its pristine focused case
passes, then must fail a precise actual-path assertion. Compile errors, unrelated
failures and mutant success cannot satisfy a control. Generated sources,
commands and logs are retained. All explicit source and JSON inputs must remain
hash-identical throughout the run; a changed producer requires a fresh result.

This suite performs no public-service request. A separate live host-side
ipwho.is schema probe was rejected by automatic approval review because that
domain and disclosure of the host's egress IP were not explicitly authorized.
That live check remains unperformed and must not be moved to CI as a workaround.
Only controlled synthetic geo inputs execute here; public-service reachability
and geolocation remain unverified. This execution limit adds no extra product
approval flow.
