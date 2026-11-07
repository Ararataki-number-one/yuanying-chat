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

## Curved glass material and native backdrop

The earlier translucent fill, hairline boundary and travelling path highlights
still read as ordinary rounded controls. This revision replaces that material
with a continuous signed-distance field (SDF), bevel normals, Fresnel-weighted
reflection, directional rim light and an inner caustic. The actual silhouette,
normal field, light and native refraction share the same local deformation.

On API 33+, `GlassLensRenderer` runs `assets/ui/liquid-glass.agsl` through a
material-only RenderNode. Text and icons are drawn afterwards by their existing
native views. No effect is installed on the control's full View tree.

- The soft curved bevel occupies up to 12 dp inside the edge (24% of the shorter
  visible side), rather than using an equal-width dark or bright outline.
- The center is a transparent coating with about 10% white veil in light mode.
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

`GlassBackdrop` records only the independent native panel. The footer and Gecko
are never in that source. Source invalidation/scroll/layout increases a revision
and invalidates weakly registered glass controls; there is no pre-draw loop or
idle timer. Capture and notification have re-entry guards. Recordings are
bounded to the glass region plus 18 dp overscan and cached by source, revision,
relative host position, size and appearance. Sampling coordinates are clamped
inside that recorded area. Native pixels pass through a 3.5 dp blur and a Snell
refraction model (glass-like index 1.45), with very small edge color separation.
There is no full-surface dimming or automatic pure-white-to-gray transform.

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

- A short press immediately supplies optical pressure, gathering the remaining
  response over 110 ms. Pointer movement retargets the existing run without
  resetting its animation clock, using an 85 ms follow response thereafter.
- A local 3 dp outward bend and 0.9 dp opposite response stay inside the 4 dp
  optical inset. The SDF, normal field, caustic and sampled pixels all use it.
- On release the optical focus travels up to 32 dp along the perimeter and
  settles over 480 ms. This reuses the existing finite input response.
- Gray system ripple remains transparent on these material surfaces. Actual
  hotspots propagate through the RippleDrawable wrapper; three destination
  buttons share their parent's press state, while reading has a separate source.
- The actual selected destination uses the existing 240 ms transition with a
  5.5% blue wash. Conversation has no falsely selected destination; reading's
  3.5% accent identifies the action without asserting that it is active.

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

The separate native backdrop preview runs after the original 20-second movie.
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
