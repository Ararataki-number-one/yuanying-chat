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

The light material reference is [Glasswork](https://github.com/kubai087/glasswork),
whose [material CSS](https://github.com/kubai087/glasswork/blob/main/glass.css)
and [installation guide](https://github.com/kubai087/glasswork/blob/main/INSTALL.md)
describe clear glass with a thin edge, localized reflections and dark ink:

- A low-opacity white center in light mode, without a dark backing plate or
  painted cyan/rainbow bands.
- A single 0.5 dp neutral boundary, reduced to roughly 5–6% black in light mode.
  Short localized white catches add local reflection without
  another complete ring.
- One feathered contact shadow strictly outside the glass, replacing the two
  hard shadow bands. The platform outline has no filled shadow. A 4 dp optical
  inset leaves room around the material while preserving the control bounds.
- One material for the address capsule and floating navigation dock.
- Theme-aware dark ink in light mode. Selected destinations use the existing
  product blue and a restrained translucent blue wash. Touch feedback follows
  the theme even for already-open windows.
- No continuous decorative animation, audio, or screenshot loop.

The subsequent material interaction follows the pointer-driven light and
finite perimeter flow in the user's [Lens reference renderer](https://github.com/ruiqichenbiec/design-systems/blob/main/lens/lab/design-system/internal/renderer.js).
Its pointer changes light direction, pressure changes reflection strength,
and a finite flow envelope travels along the rim. The native implementation
adapts these principles rather than its WebGL renderer or page sampling.

This is an independent native Canvas adaptation of the references' visual
principles. Their wallpaper colors are not copied into the conversation page;
the plain app background stays light. No WebGL renderer, third-party runtime,
or packaged Skill has been installed.

The contact shadow is generated on a small software bitmap Canvas only when
the drawable bounds or theme change. A 2.5 dp BlurMaskFilter softens a shape
offset down by 0.75 dp; CLEAR then removes the actual body's interior. Drawing
reuses that cache, leaving the View hardware accelerated and the transparent
center untinted by the shadow. Drawing also clips the cached shadow outside the
current deformed contour, so a moving edge cannot expose shadow inside the face.
Old bitmaps are not manually recycled while a
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

The user found the earlier scale/rotation feedback insufficiently liquid.
That whole-View transform is removed. Text, icons, layout and hit regions now
stay fixed while the material's own light and contour respond to the touch.
There is no idle floating, pulsing or repeating highlight animation.

- Pressing immediately supplies a visible local reflection, then gathers the
  remaining pressure in about 110 ms. Moving the pointer retargets the live
  light animation without restarting its clock; subsequent movement uses an
  85 ms response from its current state. The visible
  band covers part of the perimeter, limited to 28–64 dp; a small inner caustic
  and a cool, localized edge facet give it depth on the light background. The
  facet's peak alpha is about 29%; it is clipped to a narrow inside edge, never
  applied to the glass face. The white highlight and inner caustic stay thin.
- A local outward bend of at most about 3 dp, with a 0.9 dp opposite response,
  stays within the existing 4 dp material inset. It changes only the drawn glass.
- Release carries the reflection up to 32 dp along the edge and fades it into
  the stationary light over 480 ms with a gradual fade. The small contour response
  settles once. Normal-size review of the first capture motivated the stronger
  local edge and a fix for repeated MOVE events starving a restarted animator.
  A second actual capture still read as nearly stationary at normal size; this
  motivates the more visible localized bend and cool edge, with the same native
  gesture retained for comparison. These are material changes, not View scaling.
- The system's gray ripple is transparent on these material surfaces. Hotspots
  are explicitly forwarded through the RippleDrawable wrapper. Three buttons
  share the dock's material state; the reading action uses its own circular
  material. Child state is aggregated without clearing a sibling's native press.
- The real destination selection still moves over 240 ms, now using a lighter
  5.5% blue wash. Ordinary conversation remains unselected. Reading's 3.5% blue
  accent identifies the action without falsely marking reading as active.

These effects do not consume touch events, replace click/long-press handlers,
or delay navigation. Disabled system animations use direct optical state changes.
Visibility, detach, disabled state, appearance and actual geometry changes end
the finite material animation. Paths and shader matrices are reused during
motion; shadow bitmaps are never rebuilt by an animation frame. Hidden controls
also settle delayed release callbacks. All feedback uses public APIs available
from the app's minSdk 26; there is no new runtime or continuous screenshot loop.

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
