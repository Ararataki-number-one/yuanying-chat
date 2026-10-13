This host suite executes the production NetworkCatalog and its publication policy.
Android Context and SecretStore are fixtures; the latter deliberately uses plain
atomic files. This suite does not claim Android keystore, Gecko or public-node
coverage. Four independent JVM writers and one stale writer verify the actual
production cross-process file locks. Publication failure is injected between the
immutable provider write and atomic catalogue pointer commit.

The suite contains 112 checks. Manual-exit cases distinguish historical aliases
from current endpoint duplicates, including re-adding A after editing A to B,
occupied legacy IDs, and editing to a released historical endpoint. Format cases
reject future/fractional versions, wrong list/row/node/port types, duplicate IDs,
wrong roles, malformed UTF-8 and trailing content. Fresh and stale writers must
preserve rejected documents byte for byte. Valid unversioned and version-1
catalogues migrate without changing existing source/exit identities or provider
payloads. All persistence assertions remain host-fixture checks, not evidence of
Android encryption or device execution.

Compile the production NetworkCatalog.java, NetworkSubscriptionCatalogPolicy.java
and J.java with all Java files in this directory, using org.json on the classpath.
Run local.pocketchat.NetworkCatalogHostTest.

The repeatable runner is `python3 tests/network-catalog-host/run.py --json-jar
/path/to/json-20240303.jar [--java-home /path/to/jdk]`. It accepts an explicit
Maven org.json JAR and does not change production dependencies or fetch files.
