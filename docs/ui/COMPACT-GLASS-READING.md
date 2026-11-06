# Compact address capsule and reading dock

## Design

This change follows the requested four-action layout: **环境 / 网络 / 下载 / 阅读**.
The expanded environment capsule occupies 84% of its former flexible center
space, with equal spaces on either side. Both compact and expanded forms use a
globe icon and retain a 48 dp minimum touch height. The compact visual pill stays
smaller inside that touch area. Long environment names remain single-line and
ellipsized; the full name and both actions are exposed to accessibility services.

The material direction comes from the user's reference, [Lens](https://ruiqichenbiec.github.io/design-systems/):

- A translucent center, a narrow directional highlight, and a weak broad reflection.
- One material for the address capsule and floating navigation dock.
- Clear text and icons above the material, with a translucent blue selection wash.
- No continuous decorative animation, audio, or screenshot loop.

See the reference's [design contract](https://github.com/ruiqichenbiec/design-systems/blob/main/lens/lab/design-system/DESIGN.md)
and [integration boundaries](https://github.com/ruiqichenbiec/design-systems/blob/main/lens/START-HERE.md).
The native drawable is an independent Canvas implementation; no WebGL renderer
or third-party runtime has been imported.

**Material boundary:** `LiquidGlassDrawable` supplies the native surface,
reflection and edge treatment. It does not sample or refract the Gecko page.
The current top and bottom chrome are siblings outside the browser viewport.
Actual page-backed refraction requires a separate change to layering and
compositor sampling. This change must not be described as live webpage blur.

## Interaction

| Control | Action |
| --- | --- |
| Tap either environment capsule | Reveal the toolbar and open the native URL/search editor with the current URL selected and the keyboard requested. |
| Long press either capsule | Open the environment switcher; consume the long press so release does not also open the URL editor. |
| 环境 | Open environment management, retaining a visible alternative to the long press. |
| 网络 | Open the network workspace for the current/recent available environment. |
| 下载 | Open the download workspace. |
| 阅读 | Return to the existing browser document and request focus reading. |
| 退出阅读, Back or Escape while reading | Restore the app chrome before navigating browser history. |

Settings remains available from the existing more menu and native workspace
headers. Native workspaces retain their existing Back controls. Normal browsing
has no selected dock destination: the four controls are actions, and browsing
itself is not a fifth tab.

The reading action hides native app chrome; it does not extract an article,
replace website content, reload the document, or submit a message. Public HTTP
and HTTPS pages accepted by the existing address policy can use it. Recognized
login pages, unavailable documents and environment diagnostics retain recovery
controls. A pending reading request becomes active when its document is ready.
Keyboard state continues to hide the normal dock. The floating exit control has
a solid background to keep it readable over arbitrary website content.

Navigation state updates on actual page/focus/theme changes. Unchanged session
notifications do not rebuild the selection backgrounds. If no environment is
available, the global network/reading actions return to environment management
instead of choosing an arbitrary slot.

## Validation and delivery status

Validated in the host environment:

| Check | Result | Scope |
| --- | --- | --- |
| Existing browser address policy | 185/185 | Complete pure Java input policy. |
| Updated default environment navigation | 77/77 | Existing production routing with explicit host boundaries. |
| Updated focus reading regression | 115/115 | Production focus methods, public-page admission, recovery controls, Back and document preservation. |
| Existing chrome scheduling regression | 38/38 | Production metadata/render scheduling with controlled queues. |
| Existing address visibility regression | 40 checks and 3 mutation controls | Production URL visibility, prefill, home, navigation and lifecycle methods. |
| Android API 35 type compilation | Passed | Complete `LiquidGlassDrawable`, `Ui` and `GeckoAddressUi`, with app-only boundary stubs and real Android API classes. |
| Whitespace validation | Passed | `git diff --check`. |

These checks are not a full application build or device acceptance. No APK has
been published. Actual keyboard timing, long-press/tap exclusion, accessibility,
large fonts, day/night rendering and visual quality still need Android device
verification before release.

The frozen v1 collapse and experience device workloads depend on the removed
Chat/Settings tabs and assume capsule taps only expand chrome. Their exact input
counts and historical source/evidence contracts have not been rewritten. The
current Java fixtures identify navigation contract 2 and reject v1 invocation
explicitly; a separately versioned runner must exercise address-dialog dismissal,
more-menu navigation and Back. Existing byte-preservation gates may consequently
report the intentional fixture change. No old device result is claimed for this UI.
