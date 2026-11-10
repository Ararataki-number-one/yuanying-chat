"""Build the existing host parser cache before any timed Android action.

This prepares no device state. The original action still validates the selected
source, JDK and complete class cache, then performs every fresh native read under
its unchanged preparation deadline.
"""
import json
from pathlib import Path
import time

import chrome_header_readiness as gate


def prepare_parser(*, root, source, identity, clock=time.monotonic):
    started = clock()
    deadline = started + 20
    root = Path(root).resolve()
    binding = gate._source_bindings(root, source, identity, deadline)
    _, compiled = gate._compile_parser(root, binding, deadline)
    completed = clock()
    gate.need(completed < deadline, 'deadline')
    record = dict(schema=1, status='passed', scope='host-parser-preparation-only',
        setupOnly=True, actualAndroidExecution=False, applicationAcceptance=False,
        releaseAcceptance=False, sourceCommit=source, sourceTree=binding['sourceTree'],
        sourceSha256=binding['sourceSha256'], parserClassesSha256=compiled['parserClassesSha256'],
        setupBudgetMs=20000, elapsedMs=max(0, round((completed-started)*1000)))
    print('CHROME_PARSER_PREPARATION '+json.dumps(record, sort_keys=True, separators=(',', ':')), flush=True)
    return record
