# Compact address capsule and reading dock

## Design

This change follows the requested four-action layout: **环境 / 网络 / 下载 / 阅读**.
The three destinations share a floating glass capsule. Reading uses a separate
circular glass button on its right, with a book icon and the short label 阅读;
its accessibility label is 进入专注阅读模式. Both containers are 56 dp high at the
default font size, separated by 12 dp. The complete row is centered and capped at
320 dp at the default font size, rather than filling the screen. Its width and
height grow for larger text, and its width is constrained by the available window. The
reading circle is always square, and each destination retains a 48 dp minimum
touch target. The outer bar still participates in the existing keyboard and
focus-reading visibility rules.

The expanded environment control is centered at 208 dp wide and 44 dp high by
default, fitting within narrower windows and growing vertically for larger text.
Both compact and expanded forms use a globe icon and retain a 48 dp minimum
touch height through their existing host/delegate. The compact visual pill stays
smaller inside that touch area. Long environment names remain single-line and
ellipsized; the full name and both actions are exposed to accessibility services.
The globe and name form one centered group with an 8 dp gap in the expanded
control. Regular-weight text is 14 sp there and 12 sp in the compact control.
Changing the name first clears its previous centering padding, so compact
wrap-content measurement does not accumulate whitespace.

The user rejected the smoked-gray revision as too dark. The current light-mode
chrome uses a clear, lightly white-tinted center with dark text and quiet gray
icons. Dock icon/label blocks remain centered as a unit, including the separate
reading circle. Background wrappers do not overwrite that content padding. The
native loading/error explanation remains narrower, with adjacent recovery
actions when their measured labels fit; its actual status, network rules and
action handlers remain unchanged. A subsequent visual review found the paired
edges and lower bevel still resembled a raised plastic button. The current
revision removes that second rim and continuous bevel, softens the exterior
shadow, and uses regular 11 sp dock labels with 20 dp icons (19 dp for the
optically wider book). Inactive destination icons and labels share the same
muted ink. The separate reading action uses the product blue with a very pale
blue interior, giving the quiet layout one accent without marking reading as
active.

The latest material reference is [Glasswork](https://github.com/kubai087/glasswork),
whose [material CSS](https://github.com/kubai087/glasswork/blob/main/glass.css)
and [installation guide](https://github.com/kubai087/glasswork/blob/main/INSTALL.md)
describe clear glass with a thin edge, localized reflections and dark ink:

- A low-opacity white center in light mode, without a dark backing plate or
  painted cyan/rainbow bands.
- A single 0.5 dp neutral boundary, reduced to roughly 5–6% black in light mode.
  Short upper-left and lower-right white catches add local reflection without
  another complete ring.
- One feathered contact shadow strictly outside the glass, replacing the two
  hard shadow bands. The platform outline has no filled shadow. A 4 dp optical
  inset leaves room around the material while preserving the control bounds.
- One material for the address capsule and floating navigation dock.
- Theme-aware dark ink in light mode. Selected destinations use the existing
  product blue and a restrained translucent blue wash. Touch feedback follows
  the theme even for already-open windows.
- No continuous decorative animation, audio, or screenshot loop.

This is an independent native Canvas adaptation of the reference's visual
principles. Its wallpaper colors are not copied into the conversation page;
the plain app background stays light. No WebGL renderer, third-party runtime,
or packaged Skill has been installed.

The contact shadow is generated on a small software bitmap Canvas only when
the drawable bounds or theme change. A 2.5 dp BlurMaskFilter softens a shape
offset down by 0.75 dp; CLEAR then removes the actual body's interior. Drawing
reuses that cache, leaving the View hardware accelerated and the transparent
center untinted by the shadow. Old bitmaps are not manually recycled while a
RenderThread display list might still reference them. This follows Android's
[documented distinction between bitmap and hardware canvases](https://developer.android.com/develop/ui/views/graphics/hardware-accel).

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

## Motion and feedback

Feedback is tied to actual input and navigation changes. There is no idle
floating, pulsing or repeating highlight animation.

- The address capsules and ordinary dock controls compress slightly on press
  (0.98 scale, about 100 ms) and settle on release (about 240 ms).
- The separate reading surface has a slightly more expressive response
  (0.94 scale and a 1.5-degree tilt, settling in about 260 ms). Its blue accent
  identifies an available action; the native selected state still reports
  whether focus reading is actually active.
- One faint blue selection background moves between the three destination
  buttons when the real selected page changes. First selection fades in;
  returning to the conversation fades out. Ordinary conversation remains
  unselected.

These effects do not consume touch events, replace click/long-press handlers,
or delay navigation. Rapid input retargets the current animation. Disabled or
detached controls reset, and disabled system animations use direct state
changes. Real layout changes settle the selection shape, and hidden controls
are returned to their resting transform. The dock also settles delayed native
release callbacks received while hidden; no repeating animation is scheduled.
The original control frames remain the layout and accessibility targets.

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

Material revisions are reviewed against that baseline with the same
diagnostic. The capture runs in light mode at font scale 1.0; dark mode and
large-font behavior are outside this screenshot's evidence. A separate optional
screenrecord in the same source-bound run demonstrates native short presses,
destination changes and a cancelled reading gesture. It records the actual
screen at half resolution and retains the original MP4 with its hash; it is
not a rendered mockup or a measurement of frame rate or touch latency. Static
screenshot success and optional recording success are reported separately.
The existing full host job also has historical-input and frozen-fixture failures,
so a successful Android screenshot does not make the entire PR green.

The frozen v1 collapse and experience device workloads depend on the removed
Chat/Settings tabs and assume capsule taps only expand chrome. Their exact input
counts and historical source/evidence contracts have not been rewritten. The
current Java fixtures identify navigation contract 2 and reject v1 invocation
explicitly; a separately versioned runner must exercise address-dialog dismissal,
more-menu navigation and Back. Existing byte-preservation gates may consequently
report the intentional fixture change. No old device result is claimed for this UI.
