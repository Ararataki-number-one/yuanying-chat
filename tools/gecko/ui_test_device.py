"""Isolate an unrelated system notification source on CI emulators only.

This never changes PocketChat, its notifications, the UI workload, or assertions.
It is not a diagnosis that a notification caused a previous failed gesture.
"""
import re

SYSTEM_PACKAGE = 'com.google.android.apps.wellbeing'


def prepare(adb, *, ci, serial):
    result = dict(schema=1, scope='ci-emulator-foreign-notification-isolation',
                  package=SYSTEM_PACKAGE, applicationNotificationsChanged=False,
                  workloadChanged=False, previousFailureCauseProven=False,
                  deviceMutation=False)
    if ci is not True:
        return dict(result, status='not-ci-unchanged')
    if not isinstance(serial, str) or re.fullmatch(r'emulator-[0-9]+', serial) is None:
        raise RuntimeError('UI isolation requires an explicit CI emulator')
    if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != '1':
        raise RuntimeError('UI isolation requires a confirmed emulator')

    def installed(disabled=False):
        arguments = ['shell', 'pm', 'list', 'packages']
        if disabled:
            arguments.append('-d')
        arguments.extend(['--user', '0', SYSTEM_PACKAGE])
        rows = adb(*arguments).splitlines()
        # The filter can match similarly named packages; they are never mutated.
        return 'package:' + SYSTEM_PACKAGE in [line.strip() for line in rows]

    if not installed():
        return dict(result, status='foreign-package-absent')
    was_disabled = installed(disabled=True)
    adb('shell', 'am', 'force-stop', '--user', '0', SYSTEM_PACKAGE)
    if not was_disabled:
        adb('shell', 'pm', 'disable-user', '--user', '0', SYSTEM_PACKAGE)
    if not installed(disabled=True):
        raise RuntimeError('Foreign notification source isolation was not confirmed')
    return dict(result, status='foreign-package-disabled', previouslyDisabled=was_disabled,
                deviceMutation=True)
