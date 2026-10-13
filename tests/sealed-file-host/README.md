This suite executes production SealedFileIo with a small host AtomicFile behavior
fixture. The fixture deliberately preserves Android's destructive openRead .new
recovery and nonthrowing finishWrite rename failure, so the original failure is
reproduced before testing the protected path.

It tests actual JVM thread and OS file locks, independent JVM writer/reader
barriers, publication failure reporting, coordinated removal, reentrant access
to different files on a shared stripe, bounded persistent lock inodes, and legacy
.bak recovery. It does not execute Android or its Keystore; those cases are added
to NetworkSourcesIntegrationActivity and must pass the separate Android gate.

The 32 checks include an independent JVM's failed OS tryLock attempt before the
blocked reader is observed, canonical file aliases, complete prefix/payload
verification, and interruption of a queued JVM waiter. A success report has
status=passed and passed=total=executed=32. Failures record only executed checks,
exit nonzero, and claim cross-JVM execution only after that scenario completes.
The runner removes an old report before compilation and preserves a failed
runtime receipt, so a stale successful run cannot mask a current failure.

Run with `python3 tests/sealed-file-host/run.py --java-home /path/to/jdk`.
No additional Java dependencies are required.
