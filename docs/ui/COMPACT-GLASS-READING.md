# Compact address capsule and reading dock

## Design

This change follows the requested four-action layout: **环境 / 网络 / 下载 / 阅读**.
The three destinations share a floating glass capsule. Reading uses a separate
circular glass button on its right, with a book icon and the short label 阅读;
its accessibility label is 进入专注阅读模式. Both surfaces are 60 dp high at the
default font size, separated by 12 dp. The complete row is centered and capped at
320 dp at the default font size, rather than filling the screen. Its width and
height grow for larger text, and its width is constrained by the available window. The
reading circle is always square, and each destination retains a 48 dp minimum
touch target. The outer bar still participates in the existing keyboard and
focus-reading visibility rules.

The expanded environment capsule is centered at 208 dp wide and 44 dp high by
default, fitting within narrower windows and growing vertically for larger text.
Both compact and expanded forms use a globe icon and retain a 48 dp minimum
touch height through their existing host/delegate. The compact visual pill stays
smaller inside that touch area. Long environment names remain single-line and
ellipsized; the full name and both actions are exposed to accessibility services.

After visual review rejected the pale outlined version, the native chrome uses
smoked glass with white labels and quiet light icons. Dock icon/label blocks are
centered as a unit, including the separate reading circle. Background wrappers
do not overwrite that content padding. The native loading/error explanation is
also narrower, with adjacent recovery actions when their measured labels fit;
its actual status, network rules and action handlers remain unchanged.

The material direction comes from the user's reference, [Lens](https://ruiqichenbiec.github.io/design-systems/):

- A translucent smoke-gray center, narrow directional highlights, quiet gray
  shoulder reflections and a weak cyan return along the lower edge.
- Interrupted highlights rather than a continuous white border or rainbow rim.
- A soft contact shadow outside the glass, without a filled platform shadow
  showing through the center.
- One material for the address capsule and floating navigation dock.
- White text and light icons above the material, with a translucent light selection wash.
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

The subsequent [Android build and screenshot run](https://github.com/Ararataki-number-one/yuanying-chat/actions/runs/42238648675)
compiled the release and integration APKs, passed release lint, and captured the
actual `MainActivity` on a disposable API 35 x86_64 emulator. The source-bound
diagnostic checks the installed APK identity, opens and dismisses the real URL
editor, and retains the unmodified screenshots plus control bounds. Its fixture
has no configured VPN or live website content. It is visual review evidence, not
physical-phone, network, performance, or full interaction acceptance.

The Lens material revision is reviewed against that baseline with the same
diagnostic. The capture runs in light mode at font scale 1.0; dark mode, transient
press feedback and large-font behavior are outside this screenshot's evidence.
The existing full host job also has historical-input and frozen-fixture failures,
so a successful Android screenshot does not make the entire PR green.

The frozen v1 collapse and experience device workloads depend on the removed
Chat/Settings tabs and assume capsule taps only expand chrome. Their exact input
counts and historical source/evidence contracts have not been rewritten. The
current Java fixtures identify navigation contract 2 and reject v1 invocation
explicitly; a separately versioned runner must exercise address-dialog dismissal,
more-menu navigation and Back. Existing byte-preservation gates may consequently
report the intentional fixture change. No old device result is claimed for this UI.
