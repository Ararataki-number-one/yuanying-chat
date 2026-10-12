This host suite executes the production NetworkCatalog and its publication policy.
Android Context and SecretStore are fixtures; the latter deliberately uses plain
atomic files. This suite does not claim Android keystore, Gecko or public-node
coverage. Four independent JVM writers and one stale writer verify the actual
production cross-process file locks. Publication failure is injected between the
immutable provider write and atomic catalogue pointer commit.

Compile the production NetworkCatalog.java, NetworkSubscriptionCatalogPolicy.java
and J.java with all Java files in this directory, using org.json on the classpath.
Run local.pocketchat.NetworkCatalogHostTest.

The repeatable runner is `python3 tests/network-catalog-host/run.py --json-jar
/path/to/json-20240303.jar [--java-home /path/to/jdk]`. It accepts an explicit
Maven org.json JAR and does not change production dependencies or fetch files.
