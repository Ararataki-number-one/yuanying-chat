This host control executes the current production `AppPrefs` inventory and
`enabled`/`values`/`apply` methods, the current environment editor's actual
checkbox and save loops, and the current `NetworkRegion` probe scheduling and
admission methods. It also compiles the complete production JSON helper and
latency refresh policy. Source hashes bind every extracted input.

Use an actual JDK 17 and either existing `org.json` jar:

```sh
python3 tests/automatic-latency-host/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar \
  --output /path/to/results.json
```

The cases cover the default, persisted/user-visible disable, no queued work or
counted probe while disabled, disable after queueing and before persistence,
manual measurement, changed route/epoch/protection, cache admission, reenable,
and environment isolation. Nine separately compiled mutations must fail their
specific behavioral assertions after the pristine focused cases pass.

All platform, preference storage, checkbox, scheduling, guard, file/cache and
probe collaborators are named `Boundary` types. A probe open is a counter, not
a socket. The test neither initializes Android/Gecko nor contacts a local or
public endpoint. It does not prove actual UI rendering, encrypted persistence,
native transport, fixture acceptance, or the cause of any past device failure.
The real settings entry is `EnvironmentEditorUi`; `AppHub` is not claimed to
contain a preference loop.
