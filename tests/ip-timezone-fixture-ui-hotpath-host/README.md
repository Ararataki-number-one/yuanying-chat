This independent JVM host compiles the complete current integration Application
and Scopes. It executes the actual parent Application/profile cache, Profiles
context selection, ProfileContext.getApplicationContext chain and timezone
Store Repository constructor before a declared catalog-transaction/load boundary.
Android main-thread/Looper, catalog and vault are explicit host collaborators;
marker files and atomic moves use real temporary files. It does not execute
Android, SQLite, Keystore, Gecko or native timezone APIs.

Repeated main-thread context lookup must perform zero catalog/vault/filesystem
or store operations. Original explicit startup seeding remains. Subsequent
background Repository construction must recheck UUID/generation/deletion and
marker ownership before the loader transaction; slot-only caching is rejected.
Existing revision1 IP/custom/corrupt bytes remain untouched, and profile6's
actual missing-record allocator/nonce marker preserves default IP behavior.

The embedded complete Application is exact public source
6ee06aced87581e52aa301431f8996ed46d666b8, used only as a compiled negative
regression. No Git ancestor fetch or historical projection supplies positive
execution. Four further compiled active-code mutants remove the main-thread guard,
background identity revalidation, full UUID/generation cache key, or explicit
startup seeding. The original setup/process suites remain
separate and retain their assertions and budgets.

Run with JDK17 and each real JSON jar:
`python3 tests/ip-timezone-fixture-ui-hotpath-host/run.py --java-home JDK17 --json-jar JSON_JAR --output REPORT.json`.
