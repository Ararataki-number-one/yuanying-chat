# Compact address capsule and reading dock

## Design

This change follows the requested four-action layout: **环境 / 网络 / 下载 / 阅读**.
The three destinations share a floating glass capsule. Reading uses a separate
circular glass button on its right, with a book icon and the short label 阅读;
its accessibility label is 进入专注阅读模式. Both containers are 56 dp high at the
default font size. The three-destination capsule itself is centered on the usable
screen axis; reading sits independently at the trailing edge. The outer bar has
16 dp horizontal margins, and the capsule prefers 228 dp with at least 8 dp
between it and reading. At 412 dp screen width, the capsule center is 206 dp,
its width is 228 dp, and the gap is 20 dp. This replaces centering the combined
3+1 row, which placed the three-destination capsule 34 dp left of the screen axis.

`GlassNavigationRow` reserves equal side space around the capsule, with reading
occupying the trailing space. It measures the real native labels and chooses
equal action widths that retain their natural size and 48 dp touch targets.
The capsule narrows to fit smaller windows (200 dp on a 360 dp window and 160 dp
on a 320 dp window at default text size). If a single row cannot fit the controls,
reading moves to a second row at the trailing edge while the capsule stays
centered. Width and height also grow for larger text. The
reading circle is always square, and each destination retains a 48 dp minimum
touch target. The outer bar still participates in the existing keyboard and
focus-reading visibility rules.

The expanded environment control is centered, with a content-measured width from
168 to 208 dp and a default height of 44 dp, fitting within narrower windows and
growing vertically for larger text.
Both compact and expanded forms use a globe icon and retain a 48 dp minimum
touch height through their existing host/delegate. The compact visual pill stays
smaller inside that touch area. Long environment names remain single-line and
ellipsized; the full name and both actions are exposed to accessibility services.
The globe and name form one centered group with an 8 dp gap in the expanded
control. Medium-weight text is 15 sp there and 12 sp in the compact control.
Changing the name first clears its previous centering padding, so compact
wrap-content measurement does not accumulate whitespace.

## Page hierarchy and visual rhythm

The next refinement responds to the request to learn from well-designed GitHub
applications. It uses [Read You's list typography](https://github.com/ReadYouApp/ReadYou/tree/main/fastlane/metadata/android/zh-CN/images/phoneScreenshots)
and [Readest's documented surface and action hierarchy](https://github.com/readest/readest/blob/main/apps/readest-app/DESIGN.md)
as visual references. Their frameworks, icons and source code are not imported.
The glass renderer is retained; the work here gives the surrounding content a
clearer hierarchy instead of increasing the material's opacity or shadow.

- The shorter environment capsule makes its name the focus. Auxiliary toolbar
  icons use one 21 dp visual size, preserving their existing hit regions.
- The status strip keeps unknown and previous readings explicit. Missing region
  text and a redundant waiting-for-connection suffix no longer compete with the
  state badge; complete values remain in accessibility descriptions and the
  existing network detail UI. Connected, stale and failed readings still come
  from the same WindowNetworkState instance.
- The 3+1 dock uses 56 dp controls and a centered 228 dp preferred capsule, with
  reading independently at the trailing edge and a minimum 8 dp gap. The globe, download and
  reading glyphs are 22 dp; the cube's larger optical footprint remains 20 dp.
  Only the current destination uses blue ink and medium weight. Reading has
  neutral ink and a clear face at rest, so it does not look selected or pull the
  visual emphasis away from the centered navigation. Outer spacing is 10 dp
  above and 12 dp below, with unchanged keyboard/focus visibility rules.
- Native workspaces fade content beneath the full footer toward the page
  background. This prevents sharp row actions from appearing between the pill
  and reading circle. The glass samples the independent native panel plus this
  same background fade, so faded text cannot reappear dark inside the lens.
  No footer controls are included in that sample. Empty footer gaps consume touches so
  faded rows cannot be activated through them; named navigation buttons keep
  their own actions and accessibility. Conversation layout stays unchanged.
- Native network items share a grouped surface, so environment names lead and
  metadata, route information and secondary actions sit at lower visual weight.
  All connection, ownership, pending-configuration and operation guards remain
  in the existing network model and callbacks.
- The real loading/offline surface uses a stable icon area, a clearer title and
  vertically ordered primary/secondary recovery actions. It keeps actual state
  messages and uses the spinner only while the existing state calls for it.
  Short windows retain scrolling rather than clipping the actions.

The native screenshot diagnostic uses a modest observed scroll (at most 100 dp)
after opening the actual network page. This suits the denser list without
jumping directly into its final bottom-padding area. It still records the
actual bounds, input, selected route, source/APK identity and original PNG.
The final hierarchy is observed after the still's settling delay. If exactly one
real feedback close button is present then, the capture can dismiss it once and
record its bounds and the refreshed hierarchy before the PNG. A recurring notice
is retained; this does not change connection state or suppress application errors.

The default API 35 capture now measures the actual XML button bounds on every
observed conversation and native navigation layout. It requires the first three
buttons' union to be centered within 1 physical pixel of the 1236 px screen axis,
reading to remain a separate square to their right, and all four targets to be
at least 48 dp. Group bounds, center, offset and reading bounds are retained in
the report; the ordinary chat still has no falsely selected destination. These
default-size observations do not claim device coverage for the large-text or
narrow-window fallback.

## Curved glass material and native backdrop

The earlier translucent fill, hairline boundary and travelling path highlights
still read as ordinary rounded controls. This revision replaces that material
with a continuous signed-distance field (SDF), bevel normals, Fresnel-weighted
reflection, directional rim light and an inner caustic. The actual silhouette,
normal field, light and native refraction share the same local deformation.

On API 33+, `GlassLensRenderer` runs `assets/ui/liquid-glass.agsl` through a
material-only RenderNode. Text and icons are drawn afterwards by their existing
native views. No effect is installed on the control's full View tree.

- The curved bevel occupies up to 6.5 dp inside the edge (15% of the shorter
  visible side). Additional side reflection follows the fifth power of the
  edge profile, concentrating it near the boundary instead of a wide gray face.
- The center is a transparent coating with about 4% white veil in light mode.
  Reflection uses a soft fixed environment-light model, not a captured wallpaper
  or an opaque white background. Its opacity varies with the surface normal.
- A pair of directional white glints and a weaker inner caustic emphasize the
  continuous bevel. There is no painted cyan band or complete second ring.
- Light-mode exterior shadow is capped at 3.5%, with a 1 dp vertical offset and
  a 1.8 dp decay. It is composed outside the material face. The platform outline
  has zero shadow alpha, avoiding a second filled platform shadow.
- `RuntimeShader` output is premultiplied. The API 26–32 / software fallback uses
  the same coating model in `GlassMaterialRaster`, writing straight ARGB pixels
  for `Bitmap.setPixels`. Geometry/theme caches and a per-press cache are reused;
  no bitmap is built by an animation frame. The fallback does not sample content.

### Native content behind the floating dock

In the MainActivity's native network/download workspaces, content now extends
behind the navigation. `AppHub` keeps one stable `workspace` parent containing
`GlassBackdrop panel` and a separate bottom `footer`. Its native-page layout is
weighted to fill the available content region. ScrollView content gets footer
height as bottom padding with `clipToPadding(false)`, so its last control can
still scroll above the navigation. Original padding is retained and not added
repeatedly. The navigation views never change their parent during page changes.

`GlassBackdrop` records the independent native panel and the navigation bar's
existing scroll-edge background Drawable. It never draws the footer View tree,
controls, feedback notice or Gecko. A weak reference and a layout listener keep
the shared background's coordinates current; palette changes also invalidate the
source, and detach removes the listener. Source invalidation/scroll/layout increases a revision
and invalidates weakly registered glass controls; there is no pre-draw loop or
idle timer. Capture and notification have re-entry guards. Recordings are
bounded to the glass region plus 18 dp overscan and cached by source, revision,
relative host position, size and appearance. Sampling coordinates are clamped
inside that recorded area. Native pixels pass through a 3 dp blur and a Snell
refraction model (glass-like index 1.42), with very small edge color separation.
Only the light native material adds a 6.5% soft white backing at its center,
plus up to 8% over darker source strokes, falling to zero at the curved edge.
This replaces the previous uniform 28% backing and 6.5 dp blur, preserving more
background color while the curved edge supplies the visible lens detail.
There is no full-surface dimming or automatic pure-white-to-gray transform.

Earlier actual API 35 captures confirmed the AGSL and native recording paths,
but the material still read as a soft raised control on white and overly milky
over native content. This revision reduces the central white layers, narrows
the side reflection and separates fixed environment light from local touch
light. The first clear-material capture (`70571f94`) exposed dark blurred text
inside the lens where the surrounding footer had already faded that same text.
Sampling the existing fade with the native panel fixes that mismatch while
retaining the clearer coating and touch response. Final images and runtime evidence must
be checked for this exact commit, not inferred from an earlier successful build.

### Conversation and compatibility boundaries

The conversation keeps its measured browser viewport and existing keyboard /
focus-reading behavior. Its workspace occupies only the footer's measured
height, and its native panel is hidden. Top and bottom controls use the same
transparent curved coating, without sampling or refracting Gecko. Independent
activities that use the shared navigation receive the new material but are not
rewrapped into the MainActivity's native backdrop layout in this change.

This is an Android implementation inspired by the references, not Apple's
proprietary material or an assertion of visual equivalence. A flat backdrop has
no visible detail to refract; its appearance depends on reflection and curvature.
No new third-party runtime, Compose layer or continuous screenshot loop is added.

### References and attribution

- [Apple, Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
  explains lensing, adaptive layers, material thickness and appropriate use.
- [Apple materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials)
  distinguishes regular navigation material from clear material over rich media.
- The user's [Lens renderer](https://github.com/ruiqichenbiec/design-systems/blob/main/lens/lab/design-system/internal/renderer.js)
  informs the SDF bevel/normal relationship and finite pointer-driven response.
- [QWEA0 v2.0.11 GlassLensRenderer](https://github.com/QWEA0/Liquid-Glass-Android/blob/v2.0.11/liquidglass/src/main/java/com/example/liquidglass/GlassLensRenderer.kt)
  informs the isolated RenderNode input, blur-before-lens chain, guarded source
  recording, bounded sampling and dual-lobe light. Its MIT license is retained
  in `third-party/ui/QWEA0-Liquid-Glass-Android-LICENSE`.
- [Android AGSL guidance](https://developer.android.com/develop/ui/views/graphics/agsl/using-agsl)
  and [RenderEffect](https://developer.android.com/reference/android/graphics/RenderEffect)
  define the actual Java/Canvas APIs used by the API 33+ path.

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

Text, icons, layout and hit regions stay fixed while the material's curvature
and light respond to the touch. There is no idle floating or repeating highlight.

- A short press immediately supplies a small optical response, gathering the
  remaining response over 90 ms. Pointer movement retargets the existing run without
  resetting its animation clock, using an 85 ms follow response thereafter.
- A local 3.2 dp outward bend and 0.7 dp opposite response stay inside the 4 dp
  optical inset. The SDF, normal field, caustic and sampled pixels all use it.
- The finger's position drives a separate local light field. The environment
  light receives only a small directional bias, so pressing one end does not
  relight the entire capsule. Touch and edge-deformation positions are smoothed
  independently; a new press during release continues from the current pose.
- On release the optical focus travels up to 18 dp along the perimeter and
  settles over 320 ms, with one small reverse bend and a smooth light fade.
- Gray system ripple remains transparent on these material surfaces. Actual
  hotspots propagate through the RippleDrawable wrapper; three destination
  buttons share their parent's press state, while reading has a separate source.
- The actual selected destination moves over 280 ms with a 5.5% blue wash that
  stretches by at most 12 dp along the path, then gathers under the destination.
  Conversation has no falsely selected destination; reading uses the same
  neutral resting ink and only an actual selected state receives a blue accent.

Disabled system animations use direct optical state without deformation.
Visibility, detach, disabled state, appearance and geometry changes end finite
animations. Hidden controls discard retained native background recordings.
The old-system fallback crossfades two cached material states; it does not claim
per-frame native refraction or the full GPU response. Clicks and long presses
continue through their original handlers without artificial delays.

## Validation and delivery status

Current SDF/native-backdrop revision: whitespace and capture-script syntax
checks pass. A direct GLSL translation of the material asset compiled and
rendered finite RGBA pixels under desktop EGL, including flat and test-pattern
inputs. That diagnostic is not Android AGSL execution or a product screenshot.
Current APK compilation, lint and source-bound Android captures are reported
against their exact commit in the PR; earlier captures do not validate this
new pipeline.

The movie retains four actual inputs: download, network, Back, and a reading
press released outside its control. Each must finish while the owned recorder
is running. Hierarchy reads have 20-second absolute budgets; the recorder has
a 60-second hard cap. After the reading gesture it retains at least 1.2 seconds
of release motion and a 20-second recording wall-time floor, then verifies the
owned nonce/PID before stopping. The encoded duration is reported separately,
with an explicit 12–60-second review range and an independent legacy 12–21-second
flag. The final ordinary-chat assertion runs after the movie is finalized; a
failure still fails the motion report. No failed input is retried or inferred.

The separate native backdrop preview runs after that bounded movie.
It opens the actual network workspace using observed controls, optionally scrolls
one observed native ScrollView, retains an original full-resolution PNG and XML,
and returns to conversation. Its status is separate from the original static
and movie results. GlassLens log observations are retained with the actual PID;
ready messages or absence of errors alone do not assert visual/GPU acceptance.

Historical host checks from the earlier navigation implementation:

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
