# Native protection controller host

`python3 tests/profile_native_protection_test.py` executes current production
members extracted from `GeckoWebView.java`, plus the actual pure Java protection
and URL policies. Set `PROFILE_JAVA` to the real JDK executable when needed.

The original 98 controller checks and 60 extension-background checks retain
their assertions and time budgets. The controller uses a small `HashMap` JSON
adapter; it does not consume either JSON jar and is not a dual-parser test.
Handler scheduling, Gecko sessions, network routes and application lifecycle
are controlled boundaries. It does not execute Android or Gecko.

The original controller cases explicitly assume the independent add-on is
enabled. Eight separate checks execute the current disabled-navigation guard
and its real load, restore, delegate, popup and bootstrap call sites. Navigation
failure reporting is a counted application boundary; actual add-on lifecycle
and native navigation are not verified. Replacing the extracted real guard
with an unconditional admission is a compiled behavioral negative control.

Timezone readiness remains an independent default-system boundary. The three
current intent maps and claim/clear/has helpers are extracted unchanged;
custom timezone preparation and its native acknowledgements are exercised by
their dedicated policy hosts.
