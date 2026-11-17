"""New browser-only evidence contract after retiring native send/result detection.

Historical readers retain their original assertions. This contract requires fresh
Android observations and the retained transcript, file, input and navigation checks;
old reply-completion receipts cannot be translated into this schema.
"""
ANDROID_CHECKS = frozenset(('A busy website composer remains browser-owned without a pending result task',
 'A current websocket-failed alert remains a page error without a result task',
 'A different official conversation creates no native result task',
 'A real late Gecko inspection callback is cancelled after navigation changes',
 'A rendered historical socket alert does not become the current browser error',
 'Actual Android input waits for visible IME and unchanged viewport, composer and caret',
 'Actual Android tap and keyboard input preserve the existing composer draft',
 'Actual Gecko observation asset rejects retired action fill',
 'Actual Gecko observation asset rejects retired action latest',
 'Actual Gecko observation asset rejects retired action message-regenerate-submit',
 'Actual Gecko observation asset rejects retired action model-open',
 'Actual Gecko observation asset rejects retired action model-select',
 'Actual Gecko observation asset rejects retired action page-navigate',
 'Actual Gecko observation asset rejects retired action poll',
 'Actual Gecko observation asset rejects retired action submit',
 'Actual browser lifecycle starts with the existing document and no result task',
 'Actual browser route 0 does not create or restore a reply task',
 'Actual browser route 1 does not create or restore a reply task',
 'Actual browser route 2 does not create or restore a reply task',
 'Actual browser route 3 does not create or restore a reply task',
 'Actual browser route 4 does not create or restore a reply task',
 'Actual native inspection reports a current socket fault without monitoring a reply',
 'Actual user input neither sends a message nor changes the synthetic login',
 'An actual homepage route has no native send binding',
 'An empty homepage hydration shell has no native result observation',
 'An interactive empty homepage creates no send completion state',
 'An unchanged on-demand transcript returns no repeated message bodies',
 'An unchanged transcript reuses cached markdown and file metadata',
 'Baseline sample 0 actually transfers its long body',
 'Baseline sample 1 actually transfers its long body',
 'Baseline sample 10 actually transfers its long body',
 'Baseline sample 11 actually transfers its long body',
 'Baseline sample 2 actually transfers its long body',
 'Baseline sample 3 actually transfers its long body',
 'Baseline sample 4 actually transfers its long body',
 'Baseline sample 5 actually transfers its long body',
 'Baseline sample 6 actually transfers its long body',
 'Baseline sample 7 actually transfers its long body',
 'Baseline sample 8 actually transfers its long body',
 'Baseline sample 9 actually transfers its long body',
 'Browser navigation never stops, reloads, resubmits or changes draft and login',
 'Browser readiness inspection never rebuilds markdown or files',
 'Clearing a page socket alert clears the browser error without creating a task',
 'Connection invalidation preserves browser draft and login without result state',
 'Current browser inspection DOM reads are at least 95 percent below the historical polling workload',
 'Current browser inspection bridge payload is at least 95 percent below the historical polling workload',
 'Current browser inspection sample 0 reads page readiness without a result task',
 'Current browser inspection sample 0 transfers no reply body or completion fields',
 'Current browser inspection sample 1 reads page readiness without a result task',
 'Current browser inspection sample 1 transfers no reply body or completion fields',
 'Current browser inspection sample 10 reads page readiness without a result task',
 'Current browser inspection sample 10 transfers no reply body or completion fields',
 'Current browser inspection sample 11 reads page readiness without a result task',
 'Current browser inspection sample 11 transfers no reply body or completion fields',
 'Current browser inspection sample 2 reads page readiness without a result task',
 'Current browser inspection sample 2 transfers no reply body or completion fields',
 'Current browser inspection sample 3 reads page readiness without a result task',
 'Current browser inspection sample 3 transfers no reply body or completion fields',
 'Current browser inspection sample 4 reads page readiness without a result task',
 'Current browser inspection sample 4 transfers no reply body or completion fields',
 'Current browser inspection sample 5 reads page readiness without a result task',
 'Current browser inspection sample 5 transfers no reply body or completion fields',
 'Current browser inspection sample 6 reads page readiness without a result task',
 'Current browser inspection sample 6 transfers no reply body or completion fields',
 'Current browser inspection sample 7 reads page readiness without a result task',
 'Current browser inspection sample 7 transfers no reply body or completion fields',
 'Current browser inspection sample 8 reads page readiness without a result task',
 'Current browser inspection sample 8 transfers no reply body or completion fields',
 'Current browser inspection sample 9 reads page readiness without a result task',
 'Current browser inspection sample 9 transfers no reply body or completion fields',
 'Dark appearance applies the official Gecko runtime preference',
 'Dark appearance preserves actual document login draft and URL',
 'Generated file changes invalidate on-demand attachment metadata',
 'Historical baseline sample 0 executes its original bound polling workload',
 'Historical baseline sample 1 executes its original bound polling workload',
 'Historical baseline sample 10 executes its original bound polling workload',
 'Historical baseline sample 11 executes its original bound polling workload',
 'Historical baseline sample 2 executes its original bound polling workload',
 'Historical baseline sample 3 executes its original bound polling workload',
 'Historical baseline sample 4 executes its original bound polling workload',
 'Historical baseline sample 5 executes its original bound polling workload',
 'Historical baseline sample 6 executes its original bound polling workload',
 'Historical baseline sample 7 executes its original bound polling workload',
 'Historical baseline sample 8 executes its original bound polling workload',
 'Historical baseline sample 9 executes its original bound polling workload',
 'Later text changes invalidate the on-demand transcript cursor',
 'Light appearance applies the official Gecko runtime preference',
 'Light appearance preserves actual document login and unsent draft',
 'Manual website recovery durably archives its captured draft before checking newer typing',
 'Manual website recovery durably archives the old route draft before rejecting a later navigation',
 'Navigation during manual recovery prevents a stale reload and preserves the new route',
 'On-demand transcript keeps the entire 105k reply, both stream tails, code and file',
 'Original-only bridge starts with the actual existing Gecko document',
 'Production browser inspection has no send or result task',
 'Production browser snapshots preserve document login, unsent draft and no-send invariant',
 'Production inspection keeps the full 242-message transcript',
 'Public native bridge rejects retired action fill',
 'Public native bridge rejects retired action latest',
 'Public native bridge rejects retired action message-regenerate-submit',
 'Public native bridge rejects retired action model-open',
 'Public native bridge rejects retired action model-select',
 'Public native bridge rejects retired action page-navigate',
 'Public native bridge rejects retired action poll',
 'Public native bridge rejects retired action submit',
 'Reattaching an edited cached body refreshes the actual Gecko transcript',
 'Removing a sibling file card invalidates the actual Gecko transcript metadata',
 'Renaming a sibling file card refreshes actual Gecko metadata and transcript downloads',
 'Restoring a virtualized user message leaves website send ownership unchanged',
 'Restoring the same document preserves browser readiness without task binding',
 'Retired document event bound on route 0 cannot create a result task',
 'Retired document event bound on route 1 cannot create a result task',
 'Retired document event bound on route 2 cannot create a result task',
 'Retired document event bound on route 3 cannot create a result task',
 'Retired document event bound on route 4 cannot create a result task',
 'Retired document event intent on route 0 cannot create a result task',
 'Retired document event intent on route 1 cannot create a result task',
 'Retired document event intent on route 2 cannot create a result task',
 'Retired document event intent on route 3 cannot create a result task',
 'Retired document event intent on route 4 cannot create a result task',
 'Retired document event stop on route 0 cannot create a result task',
 'Retired document event stop on route 1 cannot create a result task',
 'Retired document event stop on route 2 cannot create a result task',
 'Retired document event stop on route 3 cannot create a result task',
 'Retired document event stop on route 4 cannot create a result task',
 'Retired document event uncertain on route 0 cannot create a result task',
 'Retired document event uncertain on route 1 cannot create a result task',
 'Retired document event uncertain on route 2 cannot create a result task',
 'Retired document event uncertain on route 3 cannot create a result task',
 'Retired document event uncertain on route 4 cannot create a result task',
 'Retired native actions leave the entire website DOM, composer, selection, route and login unchanged',
 'Reusing a stable message ID on a new node cannot retain the previous body',
 'SPA restoration and socket faults preserve typed draft, login and no-send state',
 'Same-route empty DOM does not create a native send or result task',
 'Semantic checks preserve the synthetic login, draft and no-send invariant',
 'Sibling file cards appear in incremental transcript downloads',
 'Sibling generated file cards invalidate the actual Gecko transcript revision',
 'Text mutations preserve the cached message topology',
 'The complete final body is durably saved by the production transcript worker',
 'The late-callback race captures an actual readable Gecko response',
 'The late-callback race changes the actual document route',
 'The recovery race navigates the actual Gecko document while its archive is pending',
 'The single Android input burst delivers exact ordered trusted keys and real input events',
 'Theme roundtrip preserves the same browser session and navigation epoch',
 'Two streaming mutations rebuild only the current transcript entry',
 'Typing during manual recovery prevents reload and preserves the newer browser draft',
 'Virtualizing one user message does not create a pending result check',
 'Website conversation allocation remains browser navigation without a result task',
 'Websocket error words in ordinary historical text remain ordinary browser content',
 'baseline accepts an actual Android scroll while its versioned read workload is active',
 'baseline installs its real versioned observation assets',
 'baseline loads all 242 messages including the 105k latest reply',
 'baseline preserves the draft, synthetic session cookie and send count',
 'current accepts an actual Android scroll while its versioned read workload is active',
 'current installs its real versioned observation assets',
 'current loads all 242 messages including the 105k latest reply',
 'current preserves the draft, synthetic session cookie and send count'))

NOTIFICATION_CHECKS = frozenset(('A private visibility endpoint rejects an obsolete process PID',
 'A real local-only deny-all core owns the proxy foreground service',
 'A real visible app Activity suppresses file completion reminders',
 'A saved download cannot re-alert after dismissal',
 'A visible Activity is proved by real started lifecycle count',
 'Already visible file completions are remembered without posting',
 'An already running default process exposes real zero-Activity lifecycle over private IPC',
 'An empty proxy service withdraws its foreground card without stopping a proxy',
 'An enabled legacy reply policy is migrated off without enabling result detection',
 'An obsolete reply service restart cannot resume detection or post a foreground card',
 'An upgraded pending reply becomes history without a live detection task',
 'Android accepts the obsolete service restart intent for the real profile owner',
 'Background file completion reminders are off by default',
 'Background file completion stays quiet until the user opts in',
 'Browser and network child processes cannot count as visible UI',
 'Explicit file notification opt-in is admitted after real Home',
 'File opt-in never enables result detection or reply notifications',
 'Foreground downloads stay quiet even after opting in',
 'Foreground file completions never become delayed background alerts',
 'Home retains the real proxy without creating a reply observation service',
 'Independent environments retain distinct file notification routes',
 'Network service keeps a legitimate foreground notification',
 'Opted-in background file completion opens the exact saved task',
 'Opting out removes file completion cards across environments',
 'Proxy service does not revive reply detection',
 'Real Home is proved by stopped Activity lifecycle despite browser process priority',
 'Real Home leaves the UI in background while required services keep running',
 'Stopping the owned proxy generation closes the real fixture core',
 'The notified local file is fully published and readable',
 'The proxy foreground notice stays off the lock screen',
 'Upgrade removes old noisy foreground channels',
 'Upgrade removes retired reply cards across environments',
 'network-background-quiet-v2 remains silent at MIN or system-required LOW'))

TRANSCRIPT_HOST_CHECKS = frozenset(('A full transcript preserves the entire long response',
 'Retired poll cannot classify or export a response',
 'Retired latest cannot classify or export a response',
 'Retired result commands do not build message or derived content caches',
 'Actual website generation still protects browser resources',
 'Read-only browser commands preserve official document, draft and cookie',
 'Unchanged transcript samples reuse long body and file representations',
 'Unchanged transcript samples reuse the message topology',
 'Nested body mutations invalidate their enclosing transcript entry',
 'Only the changed response rebuilds while its prior user is reused',
 'A text update retains the valid message list topology',
 'Removing the website stop control clears actual resource busy state',
 'Stop removal never restores a native completion result',
 'A late sibling file dirties its actual assistant transcript scope',
 'A late sibling file updates the retained transcript download metadata',
 'Renaming a sibling file replaces its transcript name',
 'Removing a sibling file clears its transcript download list',
 'A file named only through its title is retained in download metadata',
 'A title-only filename change invalidates the file scope memo',
 'Replacing a response node with the same ID rebuilds cached text',
 'A file inserted inside a response updates file and text caches',
 'A detached markdown body loses stale cached text on reattachment',
 'A virtualized turn reinserted as the same object rebuilds derived text',
 'Reattached edited user text is updated without result binding',
 'A later user message updates transcript topology without a native task',
 'Removing a virtualized message invalidates cached message lists',
 'Changing a message role updates transcript topology',
 'Restoring a message role restores the assistant transcript',
 'A route change resets the transcript cursor to the current route',
 'All transcript and retired-result commands leave website sending untouched'))

LIFECYCLE_HOST_CHECKS = frozenset(('Retired poll command rejects a previously confirmed task',
 'Retired latest command cannot read or classify a response',
 'Native submit and regenerate commands remain unavailable',
 'Page readiness works without an active reply task',
 'Page readiness contains no sent or completion classification',
 'A loading shell is ordinary page state with no pending-send outcome',
 'Hydration resumes page metadata without restoring a retired task',
 'Virtualizing the original user does not create binding state',
 'An empty question placeholder cannot reactivate send observation',
 'Editing a question stays solely in the website',
 'A later question creates no native completion or other-question classification',
 'Route / cannot resurrect retired result polling',
 'Route /c/assigned cannot resurrect retired result polling',
 'Route /c/other cannot resurrect retired result polling',
 'A current website connection error remains visible without result detection',
 'Connection errors remain recoverable through a loading shell',
 'Hidden stale connection alerts do not become active failures',
 'Clearing an error restores ordinary readiness with no resend',
 'All retired task and readiness probes preserve the login cookie and unsent draft'))


def passed_names(report, required, count_key='checkCount'):
    rows = report['checks']
    assert type(rows) is list and all(type(row) is dict and row.get('pass') is True for row in rows)
    names = [row['name'] for row in rows]
    assert len(names) == len(set(names)), 'Duplicate check receipt'
    assert report[count_key] == len(rows) >= len(required)
    assert required <= set(names), ('Missing browser-only evidence', required-set(names))
    return set(names)


def verify_browser_observation(report):
    assert type(report.get('browserObservationContract')) is int and report['browserObservationContract'] == 2
    assert report['status'] == 'passed'
    for field in ('actualAndroidExecution', 'actualGeckoExecution', 'actualAndroidTouchExecution',
                  'actualGeckoBrowserLifecycleExecution', 'actualAppearanceRoundtrip',
                  'actualInputImeSettled', 'actualSingleInputBurst'):
        assert report[field] is True, field
    passed_names(report, ANDROID_CHECKS)
    measurements = {item['variant']: item for item in report['measurements']}
    assert len(report['measurements']) == 2 and set(measurements) == {'baseline', 'current'}
    baseline, current = measurements['baseline'], measurements['current']
    assert baseline['action'] == 'historical-poll' and current['action'] == 'web-inspect'
    assert baseline['samples'] == current['samples'] == 12
    assert current['bridgeResponseBytes'] * 20 < baseline['bridgeResponseBytes']
    assert current['domReadChars'] * 20 < baseline['domReadChars']
    for key in ('derivedBuilt', 'messageListsBuilt'):
        assert current['observationBefore'][key] == current['observationAfter'][key]
    return dict(browserObservationContract=2, androidChecks=report['checkCount'],
                replyDetectionRetired=True, historicalWorkload='poll', currentWorkload='web-inspect')


def verify_transcript_host(report):
    assert report.get('contract') == 'browser-result-removal-v1'
    assert report['passed'] == report['total']
    passed_names(report, TRANSCRIPT_HOST_CHECKS, 'total')
    assert set(report['retiredSemantics']) == {'reply stable-completion gate', 'prompt binding', 'terminal result export'}
    return report['total']


def verify_lifecycle_host(report):
    assert report.get('contract') == 'browser-result-removal-v1'
    assert report['passed'] == report['total']
    assert report['browserLifecycleChecks'] == 19 and report['socketSurfaceChecks'] == 42
    positive = ('current-alert', 'global-alert', 'current-retry', 'global-retry', 'loading-global-alert')
    negative = ('ordinary-answer', 'ordinary-answer-with-reply-retry', 'ordinary-answer-with-global-retry',
                'ordinary-answer-with-shared-wrapper-retry', 'historical-alert', 'historical-retry',
                'unlabelled-historical-retry', 'user-quoted-alert', 'code-block-alert', 'inline-code-alert',
                'code-block-retry', 'hidden-alert', 'aria-hidden-alert', 'menu-alert', 'body-text-without-error-surface')
    expected = {(surface, 'Browser app server websocket '+word): surface in positive
                for word in ('closed', 'failed') for surface in positive+negative}
    expected.update({('unrelated-failure-role-alert', phrase): False
                     for phrase in ('Browser app server websocket failure', 'database authentication failed')})
    required = set(LIFECYCLE_HOST_CHECKS) | {'Socket surface '+surface+' / '+phrase+' / web-inspect'
                                          for surface, phrase in expected}
    passed_names(report, required, 'total')
    rows = report['socketSurfaces']
    assert len(rows) == len(expected)
    assert {(row['fixture'], row['phrase']) for row in rows} == set(expected)
    for row in rows:
        wanted = expected[(row['fixture'], row['phrase'])]
        assert row['action'] == 'web-inspect' and row['pass'] is row['noEffects'] is True
        assert row['expectedWebsiteSocketFailure'] is wanted
        output = row['output']
        assert output.get('websiteSocketClosed', False) is wanted and output['recoverable'] is wanted
        assert output.get('errorCode', '') == ('website_socket_closed' if wanted else '')
        assert not any(key in output for key in ('submitted', 'terminal', 'bindingLost', 'otherQuestion', 'contentObserved'))
    return report['total']


def verify_browser_notifications(report):
    assert type(report.get('notificationContract')) is int and report['notificationContract'] == 2
    assert report['status'] == 'passed' and report['actualAndroidExecution'] is True
    passed_names(report, NOTIFICATION_CHECKS)
    retired = report['replyRetirementEvidence']
    assert all(retired[key] is True for key in ('legacyPolicyMigratedOff', 'legacyPendingArchived', 'serviceStopped'))
    assert retired['requestedService'].startswith('local.pocketchat.test/')
    proxy = report['proxyEvidence']
    assert proxy['controllerReady'] is proxy['loopbackListenersConfigured'] is proxy['denyAllConfigured'] is True
    assert proxy['fixtureRemoteRequests'] is False
    before, ready, stopped = proxy['started'], proxy['ready'], proxy['stopped']
    assert before['alive'] is ready['alive'] is True and stopped['alive'] is False
    assert before['generation'] == ready['generation'] != stopped['generation']
    assert before['slot'] == ready['slot'] == 7 and before['pid'] > 1 and before['servicePid'] > 1
    assert stopped['pid'] == 0 and ready['state'] == 'running'
    foreground, home = report['foregroundEvidence'], report['homeEvidence']
    assert foreground['known'] is foreground['foreground'] is home['known'] is True
    assert home['foreground'] is False
    assert foreground['visibilitySource'] == home['visibilitySource'] == 'activity-start-stop'
    assert foreground['actualActivityStartedCount'] > 0 and home['actualActivityStartedCount'] == 0
    for evidence in (foreground, home):
        assert all(row['known'] is True and row['visible'] == (row['actualActivityStartedCount'] > 0) for row in evidence['processes'])
        main = next(row for row in evidence['processes'] if row['process'] == 'local.pocketchat.test')
        profile = next(row for row in evidence['processes'] if row['process'] == 'local.pocketchat.test:profile7')
        assert main['pid'] > 0 and main['pid'] != profile['pid']
        assert main['actualActivityStartedCount'] == 0 and main['visible'] is False
    return dict(notificationContract=2, androidChecks=report['checkCount'], replyDetectionRetired=True,
                actualFileNotifications=True, actualProxyForeground=True)


INTERACTION_HOST_CHECKS = frozenset(('Captured scroll, including a scroller without wheel events, marks interaction',
 'Active reading inspects browser readiness without result classification',
 'Browser readiness performs no synchronous markdown or file rebuild',
 'Repeated readiness and retired result commands never queue reply preparation',
 'Explicit snapshots retain the complete body and code during active reading',
 'Unchanged explicit snapshots reuse cached content during continuous interaction',
 'Body and sibling-file changes do not trigger automatic result preparation',
 'The next explicit snapshot retains the whole reply and late generated attachment',
 'Changing conversation schedules no stale result preparation',
 'A new browser route resets the explicit transcript cursor',
 'No result command can bind or finish another conversation',
 'Returning to a route keeps its complete on-demand transcript',
 'Detached DOM causes no automatic final-response conversion',
 'Restored virtualized content is freshly read with its detached edits',
 'One mutation batch visits shared ancestors once instead of once per token',
 'Batch coalescing still advances the transcript revision and preserves every token',
 'Unrelated sidebar class animation leaves message content and transcript clean',
 'Meaningful code class changes still invalidate cached markdown accurately',
 'A mixed class-first/text batch invalidates shared cached ancestors correctly',
 'The transcript publishes the changed complete reply after a mixed batch',
 'A class-first identity batch retains the new user entry without result binding',
 'Interaction scheduling is read-only and preserves the login, draft and zero-send invariant',
 'An unrelated trusted button gesture performs no full-page visibility/layout walk',
 'A trusted send gesture creates no native send intent or prompt snapshot',
 'A real send checks visibility of only matching controls, not historical buttons',
 'A subsequent different prompt remains solely in the website composer',
 'An already ready route avoids repeated URL parsing for unrelated mutations',
 'Initial Gecko scale is reported immediately',
 'Paired resize bursts schedule a single frame without synchronous viewport reads',
 'An unchanged viewport sends no redundant native scale message',
 'The coalesced resize preserves the final actual scale and viewport width',
 'A later duplicate event also leaves the final scale unchanged',
 'Leaving the page flushes a pending final scale even when animation frames stop',
 'Backgrounding flushes and cancels the pending viewport frame once',
 'Retired result command schedules no body preparation after unchanged',
 'Retired result command schedules no body preparation after later-user',
 'Retired result command schedules no body preparation after bound-user-removed',
 'Retired result command schedules no body preparation after earlier-history-user',
 'Retired result command schedules no body preparation after other-route',
 'Retired result command schedules no body preparation after detached-body',
 'Retired result command schedules no body preparation after body-changed',
 'Retired result command schedules no body preparation after sidebar-class'))


def verify_interaction_host(report):
    assert report.get('contract') == 'browser-result-removal-v1'
    assert report['passed'] == report['total']
    passed_names(report, INTERACTION_HOST_CHECKS, 'total')
    assert set(report['retiredSemantics']) == {'queued reply prewarm', 'native completion during interaction', 'send intent snapshots'}
    retired = report['retiredResults']
    assert retired['contract'] == report['contract'] and retired['actualAndroidExecution'] is False
    cases = ('unchanged', 'later-user', 'bound-user-removed', 'earlier-history-user', 'other-route',
             'detached-body', 'body-changed', 'sidebar-class')
    assert len(retired['rows']) == 8 and [row['kind'] for row in retired['rows']] == list(cases)
    for row in retired['rows']:
        assert all(row[key] is True for key in ('noResultWork', 'zeroSend', 'zeroFetch', 'cookieAndDraftPreserved'))
        assert row['snapshotUrl'] == 'https://chatgpt.com/c/'+('other' if row['kind'] == 'other-route' else 'interaction-fixture')
    return report['total']
