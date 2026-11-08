"""Host display-transport regressions; never substitute for Android capture.

The API32 clamp excerpt is from b5abba run42474937531/a1's original window
dump. The transport model exercises the required natural-size/rotation
protocol and readback failures; it is explicitly not an emulator result.
"""
import ast
import copy
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from glass_display import GlassDisplay, validate_display, verify_png, window_geometry


# Complete original natural-display dumps from run42479044652/a1.
API32_NATURAL = 'WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n  mLastOrientationSource=WindowedMagnification:0:31@177069308\n  deepestLastOrientationSource=ActivityRecord{cde1d7 u0 local.pocketchat.test/local.pocketchat.MainActivity t15}\n  overrideConfig={1.0 310mcc260mnc [en_US] ldltr sw412dp w412dp h868dp 480dpi nrml long port finger qwerty/v/v -nav/h winConfig={ mBounds=Rect(0, 0 - 1236, 2676) mAppBounds=Rect(0, 0 - 1236, 2676) mMaxBounds=Rect(0, 0 - 1236, 2676) mWindowingMode=fullscreen mDisplayWindowingMode=fullscreen mActivityType=undefined mAlwaysOnTop=undefined mRotation=ROTATION_0} as.2 s.93 fontWeightAdjustment=0}\n  Display: mDisplayId=0 rootTasks=5\n    init=1236x2676 480dpi cur=1236x2676 app=1236x2676 rng=1236x1164-2676x2604\n    deferred=false mLayoutNeeded=false mTouchExcludeRegion=SkRegion((0,0,1236,2676))\n\n  mLayoutSeq=287\n  mCurrentFocus=Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n  mFocusedApp=ActivityRecord{cde1d7 u0 local.pocketchat.test/local.pocketchat.MainActivity t15}\n\n  displayId=0\n  mWallpaperTarget=null\n  mLastWallpaperX=0.0 mLastWallpaperY=0.5\n\n  mSystemGestureExclusion=SkRegion()\n\n  Display areas in top down Z order:\n    * Leaf:36:36\n    * HideDisplayCutout:32:35\n      * OneHanded:32:35\n        * FullscreenMagnification:33:35\n          * Leaf:33:35\n        * Leaf:32:32\n    * WindowedMagnification:0:31\n      * HideDisplayCutout:26:31\n        * OneHanded:26:31\n          * FullscreenMagnification:29:31\n            * Leaf:29:31\n          * Leaf:28:28\n          * FullscreenMagnification:26:27\n            * Leaf:26:27\n      * Leaf:24:25\n      * HideDisplayCutout:20:23\n        * OneHanded:20:23\n          * FullscreenMagnification:20:23\n            * Leaf:20:23\n      * OneHanded:19:19\n        * FullscreenMagnification:19:19\n          * Leaf:19:19\n      * HideDisplayCutout:18:18\n        * OneHanded:18:18\n          * FullscreenMagnification:18:18\n            * Leaf:18:18\n      * OneHanded:17:17\n        * FullscreenMagnification:17:17\n          * Leaf:17:17\n      * HideDisplayCutout:0:16\n        * OneHanded:2:16\n          * ImePlaceholder:15:16\n            * ImeContainer\n          * FullscreenMagnification:2:14\n            * Leaf:3:14\n            * DefaultTaskDisplayArea\n        * OneHandedBackgroundPanel:0:1\n          * OneHanded:0:1\n            * FullscreenMagnification:0:1\n              * Leaf:0:1\n\n  Task display areas in top down Z order:\n    TaskDisplayArea DefaultTaskDisplayArea\n      mPreferredTopFocusableRootTask=Task{b74df30 #15 type=standard A=10149:local.pocketchat.test U=0 visible=true visibleRequested=true mode=fullscreen translucent=false sz=1}\n      mLastFocusedRootTask=Task{b74df30 #15 type=standard A=10149:local.pocketchat.test U=0 visible=true visibleRequested=true mode=fullscreen translucent=false sz=1}\n      Application tokens in top down Z order:\n      * Task{b74df30 #15 type=standard A=10149:local.pocketchat.test U=0 visible=true visibleRequested=true mode=fullscreen translucent=false sz=1}\n        bounds=[0,0][1236,2676]\n        * ActivityRecord{cde1d7 u0 local.pocketchat.test/local.pocketchat.MainActivity t15}\n      * Task{da3942e #1 type=home ?? U=0 visible=false visibleRequested=false mode=fullscreen translucent=true sz=1}\n        bounds=[0,0][1236,2676]\n        * Task{36c5537 #9 type=home I=com.google.android.apps.nexuslauncher/.NexusLauncherActivity U=0 rootTaskId=1 visible=false visibleRequested=false mode=fullscreen translucent=true sz=1}\n          bounds=[0,0][1236,2676]\n          * ActivityRecord{845f6ce u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t9}\n      * Task{3347b21 #2 type=undefined ?? U=0 visible=false visibleRequested=false mode=fullscreen translucent=true sz=0}\n        bounds=[0,0][1236,2676]\n      * Task{762ab46 #3 type=undefined ?? U=0 visible=false visibleRequested=false mode=multi-window translucent=true sz=0}\n        bounds=[0,0][1236,2676]\n      * Task{3567107 #4 type=undefined ?? U=0 visible=false visibleRequested=false mode=multi-window translucent=true sz=0}\n        bounds=[0,0][1236,2676]\n\n  no ScreenRotationAnimation \n\n  rootHomeTask=Task=1\n\n  PinnedTaskController\n    mIsImeShowing=false\n    mImeHeight=0\n    mAspectRatio=-1.0\n    mMinAspectRatio=0.41841003\n    mMaxAspectRatio=2.39\n    mActions=[]\n\n  DisplayFrames w=1236 h=2676 r=0\n\n  DisplayPolicy\n    mCarDockEnablesAccelerometer=true mDeskDockEnablesAccelerometer=true\n    mDockMode=EXTRA_DOCK_STATE_UNDOCKED mLidState=LID_OPEN\n    mAwake=true mScreenOnEarly=true mScreenOnFully=true\n    mKeyguardDrawComplete=true mWindowManagerDrawComplete=true\n    mHdmiPlugged=false\n    mLastAppearance=LIGHT_STATUS_BARS\n    mLastBehavior=DEFAULT\n    mShowingDream=false mDreamingLockscreen=false\n    mStatusBar=Window{6c38eb5 u0 StatusBar}\n    mExpandedPanel=Window{7b092c0 u0 NotificationShade}\n    isKeyguardShowing=false\n    mFocusedWindow=Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mTopFullscreenOpaqueWindowState=Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mStatusBarColorWindows=\n      Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mStatusBarBackgroundWindows=\n      Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mTopIsFullscreen=false\n    mForceStatusBar=false mAllowLockscreenWhenOn=false\n    mRemoteInsetsControllerControlsSystemBars=false\n    SystemGestures:\n      mDisplayCutoutTouchableRegionSize=0\n      mSwipeStartThreshold=Rect(72, 72 - 72, 72)\n      mSwipeDistanceThreshold=72\n    Looper state:\n      Looper (android.ui, tid 21) {b744b40}\n        (Total messages: 0, polling=true, quitting=false)\n\n  DisplayRotation\n    mCurrentAppOrientation=SCREEN_ORIENTATION_UNSPECIFIED\n    mLastOrientation=-1\n    mRotation=0 mDeferredRotationPauseCount=0\n    mLandscapeRotation=ROTATION_90 mSeascapeRotation=ROTATION_270\n    mPortraitRotation=ROTATION_0 mUpsideDownRotation=ROTATION_180\n    mSupportAutoRotation=true\n    WindowOrientationListener\n      mEnabled=true\n      mCurrentRotation=ROTATION_0\n      mSensorType=null\n      mSensor={Sensor name="Goldfish 3-axis Accelerometer", vendor="The Android Open Source Project", version=1, type=1, maxRange=39.300102, resolution=2.480159E-4, power=3.0, minDelay=10000}\n      mRate=2\n      AccelSensorJudge\n        mProposedRotation=0\n        mPredictedRotation=0\n        mLastFilteredX=0.0\n        mLastFilteredY=9.776321\n        mLastFilteredZ=0.812345\n        mLastFilteredTimestampNanos=174416278469 (38.527046ms ago)\n        mTiltHistory={last: 5.0}\n        mFlat=false\n        mSwinging=false\n        mAccelerating=false\n        mOverhead=false\n        mTouched=false\n        mTiltToleranceConfig=[[-25, 70], [-25, 65], [-25, 60], [-25, 65]]\n\n    mCarDockRotation=-1 mDeskDockRotation=-1\n    mUserRotationMode=USER_ROTATION_LOCKED mUserRotation=ROTATION_0 mCameraRotationMode=0 mAllowAllRotations=false\n    mDemoHdmiRotation=ROTATION_90 mDemoHdmiRotationLock=false mUndockedHdmiRotation=-1\n    mLidOpenRotation=-1\n    mFixedToUserRotation=false\n\n  InputConsumers:\n    name=recents_animation_input_consumer pid=1070 user=UserHandle{0}\n\n  WindowInsetsStateController\n    InsetsState\n      mDisplayFrame=Rect(0, 0 - 1236, 2676)\n      mDisplayCutout=DisplayCutout{insets=Rect(0, 0 - 0, 0) waterfall=Insets{left=0, top=0, right=0, bottom=0} boundingRect={Bounds=[Rect(0, 0 - 0, 0), Rect(0, 0 - 0, 0), Rect(0, 0 - 0, 0), Rect(0, 0 - 0, 0)]} cutoutPathParserInfo={CutoutPathParserInfo{displayWidth=0 displayHeight=0 density={0.0} cutoutSpec={} rotation={0} scale={0.0}}}}\n      mRoundedCorners=RoundedCorners{[RoundedCorner{position=TopLeft, radius=0, center=Point(0, 0)}, RoundedCorner{position=TopRight, radius=0, center=Point(0, 0)}, RoundedCorner{position=BottomRight, radius=0, center=Point(0, 0)}, RoundedCorner{position=BottomLeft, radius=0, center=Point(0, 0)}]}\n      mPrivacyIndicatorBounds=PrivacyIndicatorBounds {static bounds=Rect(948, 0 - 1194, 72) rotation=0}\n        InsetsSource type=ITYPE_STATUS_BAR frame=[0,0][1236,72] visible=true\n        InsetsSource type=ITYPE_LEFT_GESTURES frame=[0,0][0,0] visible=true\n        InsetsSource type=ITYPE_RIGHT_GESTURES frame=[0,0][0,0] visible=true\n        InsetsSource type=ITYPE_TOP_MANDATORY_GESTURES frame=[0,0][1236,72] visible=true\n        InsetsSource type=ITYPE_TOP_TAPPABLE_ELEMENT frame=[0,0][1236,72] visible=true\n        InsetsSource type=ITYPE_IME frame=[0,0][0,0] visible=false\n    Control map:\n      ITYPE_IME -> Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n      ITYPE_STATUS_BAR -> Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    InsetsSourceProviders:\n      ImeInsetsSourceProvider\n        mSource=InsetsSource type=ITYPE_IME frame=[0,0][0,0] visible=false\n        mControl=InsetsSourceControl type=ITYPE_IME mLeash=Surface(name=Surface(name=2b26fe9 InputMethod)/@0x73921a5 - animation-leash of insets_animation)/@0xf92154a mSurfacePosition=Point(0, 72) mInsetsHint=Insets{left=0, top=0, right=0, bottom=0} mSkipAnimationOnce=false\n        mIsLeashReadyForDispatching=true mImeOverrideFrame=[0,0][0,0]\n        mWin=Window{2b26fe9 u0 InputMethod}\n        mAdapter=ControlAdapter mCapturedLeash=Surface(name=Surface(name=2b26fe9 InputMethod)/@0x73921a5 - animation-leash of insets_animation)/@0xf92154a\n        mControlTarget=Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}\n        mImeShowing=false\n      InsetsSourceProvider\n        mSource=InsetsSource type=ITYPE_TOP_TAPPABLE_ELEMENT frame=[0,0][1236,72] visible=true\n        mIsLeashReadyForDispatching=true mImeOverrideFrame=[0,0][0,0]\n        mWin=Window{6c38eb5 u0 StatusBar}\n      InsetsSourceProvider\n        mSource=InsetsSource type=ITYPE_TOP_MANDATORY_GESTURES frame=[0,0][1236,72] visible=true\n        mIsLeashReadyForDispatching=true mImeOverrideFrame=[0,0][0,0]\n        mWin=Window{6c38eb5 u0 StatusBar}\n      InsetsSourceProvider\n        mSource=InsetsSource type=ITYPE_RIGHT_GESTURES frame=[0,0][0,0] visible=true\n        mIsLeashReadyForDispatching=true mImeOverrideFrame=[0,0][0,0]\n      InsetsSourceProvider\n        mSource=InsetsSource type=ITYPE_LEFT_GESTURES frame=[0,0][0,0] visible=true\n        mIsLeashReadyForDispatching=true mImeOverrideFrame=[0,0][0,0]\n      InsetsSourceProvider\n        mSource=InsetsSource type=ITYPE_STATUS_BAR frame=[0,0][1236,72] visible=true\n        mControl=InsetsSourceControl type=ITYPE_STATUS_BAR mLeash=Surface(name=Surface(name=6c38eb5 StatusBar)/@0xd68cd5f - animation-leash of insets_animation)/@0x4ebccbb mSurfacePosition=Point(0, 0) mInsetsHint=Insets{left=0, top=72, right=0, bottom=0} mSkipAnimationOnce=false\n        mIsLeashReadyForDispatching=true mImeOverrideFrame=[0,0][0,0]\n        mWin=Window{6c38eb5 u0 StatusBar}\n        mAdapter=ControlAdapter mCapturedLeash=Surface(name=Surface(name=6c38eb5 StatusBar)/@0xd68cd5f - animation-leash of insets_animation)/@0x4ebccbb\n        mControlTarget=Window{c1546af u0 local.pocketchat.test/local.pocketchat.MainActivity}'
API35_NATURAL = 'WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\n  Display: mDisplayId=0 (organized)\n    init=1236x2676 480dpi mMinSizeOfResizeableTaskDp=220 cur=1236x2676 app=1236x2676 rng=1236x1236-2676x2676\n    deferred=false mLayoutNeeded=false\n  mLastOrientationSource=WindowedMagnification:0:31@68242196\n  deepestLastOrientationSource=ActivityRecord{9c799a2 u0 local.pocketchat.test/local.pocketchat.MainActivity t12}\n  overrideConfig={1.0 310mcc260mnc [en_US] ldltr sw412dp w412dp h892dp 480dpi nrml long port finger qwerty/v/v -nav/h winConfig={ mBounds=Rect(0, 0 - 1236, 2676) mAppBounds=Rect(0, 0 - 1236, 2676) mMaxBounds=Rect(0, 0 - 1236, 2676) mDisplayRotation=ROTATION_0 mWindowingMode=fullscreen mActivityType=undefined mAlwaysOnTop=undefined mRotation=ROTATION_0} as.2 s.107 fontWeightAdjustment=0}\n  mLayoutSeq=203\n  mCurrentFocus=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n  mFocusedApp=ActivityRecord{9c799a2 u0 local.pocketchat.test/local.pocketchat.MainActivity t12}\n\n  mHoldScreenWindow=null\n  mObscuringWindow=null\n  mLastWakeLockHoldingWindow=null\n  mLastWakeLockObscuringWindow=null\n\n  displayId=0\n  mWallpaperTarget=null\n  mLastWallpaperZoomOut=0.0\n  token WallpaperWindowToken{9ff1d30 token=android.os.Binder@5993a73}:\n    canShowWhenLocked=true\n    mWallpaperX=0.0\n    mWallpaperY=0.5\n    mWallpaperXStep=0.33333334\n    mWallpaperYStep=1.0\n    mWallpaperDisplayOffsetX=NA\n    mWallpaperDisplayOffsetY=NA\n\n  mSystemGestureExclusion=SkRegion()\n\n  Display areas in top down Z order:\n    * Leaf:36:36\n    * HideDisplayCutout:32:35\n      * OneHanded:34:35\n        * FullscreenMagnification:34:35\n          * Leaf:34:35\n      * FullscreenMagnification:33:33\n        * Leaf:33:33\n      * OneHanded:32:32\n        * Leaf:32:32\n    * WindowedMagnification:0:31\n      * HideDisplayCutout:26:31\n        * OneHanded:26:31\n          * FullscreenMagnification:29:31\n            * Leaf:29:31\n          * Leaf:28:28\n          * FullscreenMagnification:26:27\n            * Leaf:26:27\n      * Leaf:24:25\n      * HideDisplayCutout:18:23\n        * OneHanded:18:23\n          * FullscreenMagnification:18:23\n            * Leaf:18:23\n      * OneHanded:17:17\n        * FullscreenMagnification:17:17\n          * Leaf:17:17\n      * HideDisplayCutout:16:16\n        * OneHanded:16:16\n          * FullscreenMagnification:16:16\n            * Leaf:16:16\n      * OneHanded:15:15\n        * FullscreenMagnification:15:15\n          * Leaf:15:15\n      * HideDisplayCutout:0:14\n        * OneHanded:0:14\n          * ImePlaceholder:13:14\n            * ImeContainer\n          * FullscreenMagnification:0:12\n            * Leaf:3:12\n            * DefaultTaskDisplayArea (organized)\n            * Leaf:0:1\n\n  Task display areas in top down Z order:\n    TaskDisplayArea DefaultTaskDisplayArea\n      overrideConfig={0.0 ?mcc0mnc ?localeList ?layoutDir ?swdp ?wdp ?hdp ?density ?lsize ?long ?ldr ?wideColorGamut ?orien ?uimode ?night ?touch ?keyb/?/? ?nav/? winConfig={ mBounds=Rect(0, 0 - 0, 0) mAppBounds=null mMaxBounds=Rect(0, 0 - 0, 0) mDisplayRotation=undefined mWindowingMode=fullscreen mActivityType=undefined mAlwaysOnTop=undefined mRotation=undefined} ?fontWeightAdjustment}\n      mPreferredTopFocusableRootTask=Task{465b272 #12 type=standard A=10209:local.pocketchat.test}\n      mLastFocusedRootTask=Task{465b272 #12 type=standard A=10209:local.pocketchat.test}\n      Application tokens in top down Z order:\n      * Task{465b272 #12 type=standard A=10209:local.pocketchat.test U=0 visible=true visibleRequested=true mode=fullscreen translucent=false sz=1}\n        bounds=[0,0][1236,2676]\n        * ActivityRecord{9c799a2 u0 local.pocketchat.test/local.pocketchat.MainActivity t12}\n      * Task{c5e9b2 #1 type=home U=0 visible=false visibleRequested=false mode=fullscreen translucent=true sz=1}\n        bounds=[0,0][1236,2676]\n        * Task{a3b8291 #7 type=home I=com.google.android.apps.nexuslauncher/.NexusLauncherActivity U=0 rootTaskId=1 visible=false visibleRequested=false mode=fullscreen translucent=true sz=2}\n          bounds=[0,0][1236,2676]\n          * ActivityRecord{f9644b8 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t7}\n          * TaskFragment{adc9102 mode=multi-window organizerUid=10179 organizerProc=com.google.android.apps.nexuslauncher}\n            bounds=[0,0][1236,2676]\n      * Task{b1fc8fe #2 type=undefined U=0 visible=false visibleRequested=false mode=fullscreen translucent=true sz=2}\n        bounds=[0,0][1236,2676]\n        * Task{f8a52ac #4 type=undefined U=0 rootTaskId=2 visible=false visibleRequested=false mode=multi-window translucent=true sz=0}\n          bounds=[0,2676][1236,4014]\n        * Task{e3a285f #3 type=undefined U=0 rootTaskId=2 visible=false visibleRequested=false mode=multi-window translucent=true sz=0}\n          bounds=[0,0][1236,2676]\n\n  no ScreenRotationAnimation \n\n  rootHomeTask=Task=1\n\n  PinnedTaskController\n    mIsImeShowing=false\n    mImeHeight=0\n    mMinAspectRatio=0.41841003\n    mMaxAspectRatio=2.39\n\n  DisplayFrames w=1236 h=2676 r=0\n\n  DisplayPolicy\n    mCarDockEnablesAccelerometer=true mDeskDockEnablesAccelerometer=true\n    mDockMode=EXTRA_DOCK_STATE_UNDOCKED mLidState=LID_OPEN\n    mAwake=true mScreenOnEarly=true mScreenOnFully=true\n    mKeyguardDrawComplete=true mWindowManagerDrawComplete=true\n    mHdmiPlugged=false\n    mLastAppearance=LIGHT_STATUS_BARS LIGHT_NAVIGATION_BARS\n    mLastBehavior=DEFAULT\n    mShowingDream=false mDreamingLockscreen=false\n    mStatusBar=Window{8a1a733 u0 StatusBar}\n    mExpandedPanel=Window{688f716 u0 NotificationShade}\n    isKeyguardShowing=false\n    mNavigationBar=Window{89b57b8 u0 Taskbar}\n    mNavBarOpacityMode=2\n    mNavigationBarCanMove=false\n    mNavigationBarPosition=4\n    mLeftGestureHost=Window{89b57b8 u0 Taskbar}\n    mTopGestureHost=Window{8a1a733 u0 StatusBar}\n    mRightGestureHost=Window{89b57b8 u0 Taskbar}\n    mBottomGestureHost=Window{89b57b8 u0 Taskbar}\n    mFocusedWindow=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mTopFullscreenOpaqueWindowState=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mSystemBarColorApps={ActivityRecord{9c799a2 u0 local.pocketchat.test/local.pocketchat.MainActivity t12}}\n    mNavBarColorWindowCandidate=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mNavBarBackgroundWindowCandidate=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mLastStatusBarAppearanceRegions=\n      AppearanceRegion{LIGHT_STATUS_BARS bounds=[0,0][1236,2676]}\n    mLastLetterboxDetails=\n    mStatusBarBackgroundWindows=\n      Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n    mTopIsFullscreen=false\n    mImeInsetsConsumed=false\n    mForceShowNavigationBarEnabled=false mAllowLockscreenWhenOn=false\n    mRemoteInsetsControllerControlsSystemBars=false\n    mDecorInsetsInfo:\n      ROTATION_0={nonDecorInsets=[0,0][0,0], overrideNonDecorInsets=[0,0][0,72], configInsets=[0,0][0,0], overrideConfigInsets=[0,72][0,72], nonDecorFrame=[0,0][1236,2676], overrideNonDecorFrame=[0,0][1236,2604], configFrame=[0,0][1236,2676], overrideConfigFrame=[0,72][1236,2604]}\n      ROTATION_90={nonDecorInsets=[0,0][0,0], overrideNonDecorInsets=[0,0][0,72], configInsets=[0,0][0,0], overrideConfigInsets=[0,72][0,72], nonDecorFrame=[0,0][2676,1236], overrideNonDecorFrame=[0,0][2676,1164], configFrame=[0,0][2676,1236], overrideConfigFrame=[0,72][2676,1164]}\n      ROTATION_180={nonDecorInsets=[0,0][0,0], overrideNonDecorInsets=[0,0][0,72], configInsets=[0,0][0,0], overrideConfigInsets=[0,72][0,72], nonDecorFrame=[0,0][1236,2676], overrideNonDecorFrame=[0,0][1236,2604], configFrame=[0,0][1236,2676], overrideConfigFrame=[0,72][1236,2604]}\n      ROTATION_270={nonDecorInsets=[0,0][0,0], overrideNonDecorInsets=[0,0][0,72], configInsets=[0,0][0,0], overrideConfigInsets=[0,72][0,72], nonDecorFrame=[0,0][2676,1236], overrideNonDecorFrame=[0,0][2676,1164], configFrame=[0,0][2676,1236], overrideConfigFrame=[0,72][2676,1164]}\n    SystemGestures:\n      mDisplayCutoutTouchableRegionSize=0\n      mSwipeStartThreshold=Rect(72, 72 - 72, 72)\n      mSwipeDistanceThreshold=72\n\n  DisplayRotation\n    mCurrentAppOrientation=SCREEN_ORIENTATION_UNSPECIFIED\n    mLastOrientation=-1\n    mRotation=0 mDeferredRotationPauseCount=0\n    mLandscapeRotation=ROTATION_90 mSeascapeRotation=ROTATION_270\n    mPortraitRotation=ROTATION_0 mUpsideDownRotation=ROTATION_180\n    mSupportAutoRotation=true\n    WindowOrientationListener\n      mEnabled=true\n      mCurrentRotation=ROTATION_0\n      mSensorType=null\n      mSensor={Sensor name="Goldfish 3-axis Accelerometer", vendor="The Android Open Source Project", version=1, type=1, maxRange=39.300102, resolution=2.480159E-4, power=3.0, minDelay=10000}\n      mRate=2\n      AccelSensorJudge\n        mProposedRotation=0\n        mPredictedRotation=0\n        mLastFilteredX=0.0\n        mLastFilteredY=9.776321\n        mLastFilteredZ=0.812345\n        mLastFilteredTimestampNanos=185169653056 (3.375994ms ago)\n        mTiltHistory={last: 5.0}\n        mFlat=false\n        mSwinging=false\n        mAccelerating=false\n        mOverhead=false\n        mTouched=false\n        mTiltToleranceConfig=[[-25, 70], [-25, 65], [-25, 60], [-25, 65]]\n\n    mCarDockRotation=-1 mDeskDockRotation=-1\n    mUserRotationMode=USER_ROTATION_LOCKED mUserRotation=ROTATION_0 mCameraRotationMode=0 mAllowAllRotations=unknown\n    mDemoHdmiRotation=ROTATION_90 mDemoHdmiRotationLock=false mUndockedHdmiRotation=-1\n    mLidOpenRotation=-1\n    mFixedToUserRotation=false\n  FoldController\n    mPauseAutorotationDuringUnfolding=false\n    mShouldDisableRotationSensor=false\n    mShouldIgnoreSensorRotation=false\n    mLastDisplaySwitchTime=0\n    mLastHingeAngleEventTime=0\n    mDeviceState=FOLDED\n\n    RotationLockHistory\n      11-08 12:19:30.141: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=UiAutomationConnection#restoreRotationStateLocked\n      11-08 12:19:34.309: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=UiAutomationConnection#restoreRotationStateLocked\n      11-08 12:19:36.824: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=DisplayRotationReversionController#revertOverride\n      11-08 12:19:47.408: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=DisplayRotationReversionController#revertOverride\n      11-08 12:19:55.400: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=DisplayRotationReversionController#revertOverride\n      11-08 12:20:02.107: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=UiAutomationConnection#restoreRotationStateLocked\n      11-08 12:20:04.094: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=DisplayRotationReversionController#revertOverride\n      11-08 12:20:11.393: mode=USER_ROTATION_LOCKED, rotation=ROTATION_0, caller=UiAutomationConnection#restoreRotationStateLocked\n\n  InputConsumers:\n    name=recents_animation_input_consumer pid=1214 user=UserHandle{0}\n\n  WindowInsetsStateController\n    InsetsState\n      mDisplayFrame=Rect(0, 0 - 1236, 2676)\n      mDisplayCutout=DisplayCutout{insets=Rect(0, 0 - 0, 0) waterfall=Insets{left=0, top=0, right=0, bottom=0} boundingRect={Bounds=[Rect(0, 0 - 0, 0), Rect(0, 0 - 0, 0), Rect(0, 0 - 0, 0), Rect(0, 0 - 0, 0)]} cutoutPathParserInfo={CutoutPathParserInfo{displayWidth=0 displayHeight=0 physicalDisplayWidth=0 physicalDisplayHeight=0 density={0.0} cutoutSpec={} rotation={0} scale={0.0} physicalPixelDisplaySizeRatio={0.0}}} sideOverrides=null}\n      mRoundedCorners=RoundedCorners{[RoundedCorner{position=TopLeft, radius=0, center=Point(0, 0)}, RoundedCorner{position=TopRight, radius=0, center=Point(0, 0)}, RoundedCorner{position=BottomRight, radius=0, center=Point(0, 0)}, RoundedCorner{position=BottomLeft, radius=0, center=Point(0, 0)}]}\n      mRoundedCornerFrame=Rect(0, 0 - 0, 0)\n      mPrivacyIndicatorBounds=PrivacyIndicatorBounds {static bounds=Rect(948, 0 - 1194, 72) rotation=0}\n      mDisplayShape=DisplayShape{ spec=-1249681527 displayWidth=1236 displayHeight=2676 physicalPixelDisplaySizeRatio=1.0 rotation=0 offsetX=0 offsetY=0 scale=1.0}\n        InsetsSource id=8ded0001 type=navigationBars frame=[0,2604][1236,2676] visible=true flags=SUPPRESS_SCRIM|ANIMATE_RESIZING sideHint=BOTTOM boundingRects=null\n        InsetsSource id=8ded0004 type=systemGestures frame=[0,0][90,2676] visible=true flags= sideHint=LEFT boundingRects=null\n        InsetsSource id=8ded0005 type=mandatorySystemGestures frame=[0,2580][1236,2676] visible=true flags= sideHint=BOTTOM boundingRects=null\n        InsetsSource id=8ded0006 type=tappableElement frame=[0,0][0,0] visible=true flags= sideHint=NONE boundingRects=null\n        InsetsSource id=8ded0024 type=systemGestures frame=[1146,0][1236,2676] visible=true flags= sideHint=RIGHT boundingRects=null\n        InsetsSource id=3 type=ime frame=[0,0][0,0] visible=false flags= sideHint=NONE boundingRects=null\n        InsetsSource id=25710000 type=statusBars frame=[0,0][1236,72] visible=true flags= sideHint=TOP boundingRects=null\n        InsetsSource id=25710005 type=mandatorySystemGestures frame=[0,0][1236,72] visible=true flags= sideHint=TOP boundingRects=null\n        InsetsSource id=25710006 type=tappableElement frame=[0,0][1236,72] visible=true flags= sideHint=TOP boundingRects=null\n    Control map:\n      Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}:\n        InsetsSourceControl: {3 mType=ime mSurfacePosition=Point(0, 72) mInsetsHint=Insets{left=0, top=0, right=0, bottom=936}}\n        InsetsSourceControl: {8ded0001 mType=navigationBars initiallyVisible mSurfacePosition=Point(0, 2604) mInsetsHint=Insets{left=0, top=0, right=0, bottom=72}}\n        InsetsSourceControl: {25710000 mType=statusBars initiallyVisible mSurfacePosition=Point(0, 0) mInsetsHint=Insets{left=0, top=72, right=0, bottom=0}}\n    InsetsSourceProviders:\n      InsetsSourceProvider\n        mSource=InsetsSource id=25710006 type=tappableElement frame=[0,0][1236,72] visible=true flags= sideHint=TOP boundingRects=null\n        mSourceFrame=Rect(0, 0 - 1236, 72)\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{8a1a733 u0 StatusBar}\n      InsetsSourceProvider\n        mSource=InsetsSource id=25710005 type=mandatorySystemGestures frame=[0,0][1236,72] visible=true flags= sideHint=TOP boundingRects=null\n        mSourceFrame=Rect(0, 0 - 1236, 72)\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{8a1a733 u0 StatusBar}\n      InsetsSourceProvider\n        mSource=InsetsSource id=25710000 type=statusBars frame=[0,0][1236,72] visible=true flags= sideHint=TOP boundingRects=null\n        mSourceFrame=Rect(0, 0 - 1236, 72)\n        mControl=InsetsSourceControl mId=25710000 mType=statusBars mLeash=Surface(name=Surface(name=8a1a733 StatusBar)/@0x1045869 - animation-leash of insets_animation)/@0xfbfd655 mInitiallyVisible=true mSurfacePosition=Point(0, 0) mInsetsHint=Insets{left=0, top=72, right=0, bottom=0} mSkipAnimationOnce=false\n        mInsetsHint=Insets{left=0, top=72, right=0, bottom=0}\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{8a1a733 u0 StatusBar}\n        mAdapter=ControlAdapter mCapturedLeash=Surface(name=Surface(name=8a1a733 StatusBar)/@0x1045869 - animation-leash of insets_animation)/@0xfbfd655\n        mControlTarget=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n      ImeInsetsSourceProvider\n        mSource=InsetsSource id=3 type=ime frame=[0,0][0,0] visible=false flags= sideHint=NONE boundingRects=null\n        mSourceFrame=Rect(0, 2676 - 1236, 2676)\n        mControl=InsetsSourceControl mId=3 mType=ime mLeash=Surface(name=Surface(name=74c773 InputMethod)/@0x8312a9 - animation-leash of insets_animation)/@0x2ba586a mInitiallyVisible=false mSurfacePosition=Point(0, 72) mInsetsHint=Insets{left=0, top=0, right=0, bottom=936} mSkipAnimationOnce=false\n        mInsetsHint=Insets{left=0, top=0, right=0, bottom=936} stale\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{74c773 u0 InputMethod}\n        mAdapter=ControlAdapter mCapturedLeash=Surface(name=Surface(name=74c773 InputMethod)/@0x8312a9 - animation-leash of insets_animation)/@0x2ba586a\n        mControlTarget=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n        mImeShowing=false        showImePostLayout not scheduled, mImeRequester=null\n\n      InsetsSourceProvider\n        mSource=InsetsSource id=8ded0024 type=systemGestures frame=[1146,0][1236,2676] visible=true flags= sideHint=RIGHT boundingRects=null\n        mSourceFrame=Rect(1146, 0 - 1236, 2676)\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{89b57b8 u0 Taskbar}\n      InsetsSourceProvider\n        mSource=InsetsSource id=8ded0006 type=tappableElement frame=[0,0][0,0] visible=true flags= sideHint=NONE boundingRects=null\n        mSourceFrame=Rect(0, 0 - 0, 0)\n        mOverrideFrames={2011=Rect(0, 2604 - 1236, 2676), 2031=Rect(0, 0 - 0, 0)}\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{89b57b8 u0 Taskbar}\n      InsetsSourceProvider\n        mSource=InsetsSource id=8ded0005 type=mandatorySystemGestures frame=[0,2580][1236,2676] visible=true flags= sideHint=BOTTOM boundingRects=null\n        mSourceFrame=Rect(0, 2580 - 1236, 2676)\n        mOverrideFrames={2011=Rect(0, 2604 - 1236, 2676), 2031=Rect(0, 2580 - 1236, 2676)}\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{89b57b8 u0 Taskbar}\n      InsetsSourceProvider\n        mSource=InsetsSource id=8ded0004 type=systemGestures frame=[0,0][90,2676] visible=true flags= sideHint=LEFT boundingRects=null\n        mSourceFrame=Rect(0, 0 - 90, 2676)\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{89b57b8 u0 Taskbar}\n      InsetsSourceProvider\n        mSource=InsetsSource id=8ded0001 type=navigationBars frame=[0,2604][1236,2676] visible=true flags=SUPPRESS_SCRIM|ANIMATE_RESIZING sideHint=BOTTOM boundingRects=null\n        mSourceFrame=Rect(0, 2604 - 1236, 2676)\n        mOverrideFrames={2011=Rect(0, 2604 - 1236, 2676), 2031=Rect(0, 2604 - 1236, 2676)}\n        mControl=InsetsSourceControl mId=8ded0001 mType=navigationBars mLeash=Surface(name=Surface(name=89b57b8 Taskbar)/@0x4f677a9 - animation-leash of insets_animation)/@0xc44215b mInitiallyVisible=true mSurfacePosition=Point(0, 2604) mInsetsHint=Insets{left=0, top=0, right=0, bottom=72} mSkipAnimationOnce=false\n        mInsetsHint=Insets{left=0, top=0, right=0, bottom=72}\n        mIsLeashReadyForDispatching=true mHasPendingPosition=false\n        mWindowContainer=Window{89b57b8 u0 Taskbar}\n        mAdapter=ControlAdapter mCapturedLeash=Surface(name=Surface(name=89b57b8 Taskbar)/@0x4f677a9 - animation-leash of insets_animation)/@0xc44215b\n        mControlTarget=Window{4b017dd u0 local.pocketchat.test/local.pocketchat.MainActivity}\n  InsetsPolicy\n    status: WINDOW_STATE_SHOWING\n    nav: WINDOW_STATE_SHOWING'


API32_CLAMP = '''WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)
  Display: mDisplayId=0 rootTasks=5
    init=1236x2676 480dpi base=2472x1236 480dpi cur=2472x1236 app=2472x1236 rng=1236x1164-2472x2400
  DisplayFrames w=2472 h=1236 r=0
'''
API35_FORCED = '''WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)
  Display: mDisplayId=0 (organized)
    init=1236x2676 480dpi mMinSizeOfResizeableTaskDp=220 base=2676x1236 480dpi cur=2676x1236 app=2676x1236 rng=1236x1236-2676x2676
  DisplayFrames w=2676 h=1236 r=0
'''


class Android32DisplayModel:
    """Faithful scope: observed forced-width cap, logical rotation, settings.

    No Android rendering, lifecycle, input or device acceptance is simulated.
    """
    def __init__(self):
        self.physical = (1236, 2676)
        self.forced = None
        self.density = None
        self.mode = 'lock 0'
        self.settings = dict(font_scale='1.0', accelerometer_rotation='0', user_rotation='0')
        self.night = 'no'
        self.target_allows_rotation = True
        self.calls = []
        self.fail_next = None

    def frame(self):
        width, height = self.forced or self.physical
        rotation = int(self.mode[-1]) if self.mode.startswith('lock ') else 0
        if not self.target_allows_rotation:
            rotation = 0
        if rotation % 2:
            width, height = height, width
        return width, height, rotation

    def __call__(self, *parts, **kwargs):
        self.calls.append(parts)
        if parts == self.fail_next:
            self.fail_next = None
            raise OSError('controlled transport failure')
        if parts[:2] != ('shell', 'wm') and parts[:2] != ('shell', 'settings') and parts[:2] not in (('shell', 'am'), ('shell', 'cmd'), ('shell', 'dumpsys')):
            raise AssertionError('Unexpected input or UI mutation: ' + repr(parts))
        p = parts[1:]
        if p == ('wm', 'size'):
            text = 'Physical size: 1236x2676\n'
            if self.forced:
                text += 'Override size: %dx%d\n' % self.forced
            return text.encode()
        if p[:2] == ('wm', 'size'):
            value = p[2]
            requested = None if value == 'reset' else tuple(map(int, value.split('x')))
            self.forced = None if requested in (None, self.physical) else tuple(min(v, 2472) for v in requested)
        elif p == ('wm', 'density'):
            return ('Physical density: 480\n' + (('Override density: %d\n' % self.density) if self.density else '')).encode()
        elif p[:2] == ('wm', 'density'):
            self.density = None if p[2] in ('reset', '480') else int(p[2])
        elif p == ('wm', 'user-rotation'):
            return (self.mode + '\n').encode()
        elif p[:2] == ('wm', 'user-rotation'):
            self.mode = ' '.join(p[2:])
            self.settings['accelerometer_rotation'] = '1' if self.mode == 'free' else '0'
            if self.mode.startswith('lock '):
                self.settings['user_rotation'] = p[3]
        elif p[:3] == ('settings', 'get', 'system'):
            return (self.settings.get(p[3], 'null') + '\n').encode()
        elif p[:3] == ('settings', 'put', 'system'):
            self.settings[p[3]] = p[4]
        elif p[:3] == ('settings', 'delete', 'system'):
            self.settings.pop(p[3], None)
        elif p == ('cmd', 'uimode', 'night'):
            return ('Night mode: ' + self.night + '\n').encode()
        elif p[:3] == ('cmd', 'uimode', 'night'):
            self.night = p[3]
        elif p == ('am', 'get-config'):
            w, h, r = self.frame()
            return ('config: en-rUS-w%ddp-h%ddp-%s-%s-xxhdpi-v32\nabi: x86_64\n' %
                    (w // 3, h // 3, 'land' if w > h else 'port', 'night' if self.night == 'yes' else 'notnight')).encode()
        elif p == ('dumpsys', 'window', 'displays'):
            w, h, r = self.frame()
            base = self.forced or self.physical
            override = (' base=%dx%d %ddpi' % (*base, self.density or 480)) if self.forced or self.density else ''
            return ('  Display: mDisplayId=0 rootTasks=5\n'
                    '    init=1236x2676 480dpi%s cur=%dx%d app=%dx%d rng=0x0-0x0\n'
                    '  DisplayFrames w=%d h=%d r=%d\n' %
                    (override, w, h, w, h, w, h, r)).encode()
        else:
            raise AssertionError('Unmodeled command: ' + repr(parts))
        return b''


class GlassDisplayRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.android = Android32DisplayModel()
        self.display = GlassDisplay(self.android, self.out, lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())

    def tearDown(self):
        self.temp.cleanup()

    def test_original_api32_clamp_is_observed_not_requested_width(self):
        self.assertEqual(window_geometry(API32_CLAMP), dict(width=2472, height=1236, rotation=0, density=480))
        self.android('shell', 'wm', 'size', '2676x1236')
        observed = self.display.observe('old-command')
        self.assertEqual(observed['logical']['width'], 2472)
        with self.assertRaises(ValueError):
            validate_display(observed, 2676, 1236, 480, 0, 1, 'no')

    def test_api35_actual_forced_landscape_format_is_read_exactly(self):
        self.assertEqual(window_geometry(API35_FORCED), dict(width=2676, height=1236, rotation=0, density=480))

    def test_natural_portrait_plus_real_rotation_obtains_requested_landscape(self):
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        state = self.display.require(2676, 1236, 480, 1.0, 'no', 'rotated')
        self.assertEqual(state['logical'], dict(width=2676, height=1236, density=480, rotation=1))
        self.assertEqual(state['size'], 'Physical size: 1236x2676')
        self.assertIn(('shell', 'wm', 'size', '1236x2676'), self.android.calls)
        self.assertNotIn(('shell', 'wm', 'size', '2676x1236'), self.android.calls)
        self.assertIn(('shell', 'wm', 'user-rotation', 'lock', '1'), self.android.calls)
        self.assertTrue((self.out / state['window']['file']).is_file())

    def test_portrait_only_home_is_not_accepted_as_target_activity_rotation(self):
        self.android.target_allows_rotation = False
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        with self.assertRaises(ValueError):
            self.display.require(2676, 1236, 480, 1.0, 'no', 'home')
        self.android.target_allows_rotation = True
        self.assertEqual(self.display.require(2676, 1236, 480, 1.0, 'no', 'target')['logical']['rotation'], 1)

    def test_next_portrait_case_restores_rotation_zero_and_preserves_narrow_case(self):
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        self.display.configure(960, 2220, 480, 1.6, 'no')
        state = self.display.require(960, 2220, 480, 1.6, 'no', 'narrow')
        self.assertEqual(state['logical'], dict(width=960, height=2220, density=480, rotation=0))

    def test_natural_size_text_cannot_replace_logical_frame_or_rotation(self):
        state = self.display.observe('before')
        for values in (dict(width=2676, height=1236, rotation=0), dict(width=2472, height=1236, rotation=1)):
            bad = copy.deepcopy(state)
            bad['logical'].update(values)
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_display(bad, 2676, 1236, 480, 1, 1, 'no')

    def test_wrong_density_font_theme_orientation_or_rotation_settings_reject(self):
        self.display.configure(2676, 1236, 480, 1.3, 'yes')
        state = self.display.require(2676, 1236, 480, 1.3, 'yes', 'good')
        changes = [('density', 'wrong'), ('fontScale', 'nan'), ('fontScale', '1.0'),
                   ('configuration', 'config: en-rUS-land-notnight-v32'),
                   ('configuration', 'config: en-rUS-port-night-v32'),
                   ('rotationMode', 'free'), ('accelerometerRotation', '1'), ('userRotation', '0'),
                   ('nightMode', 'auto')]
        for key, value in changes:
            bad = copy.deepcopy(state)
            if key == 'density':
                bad['logical']['density'] = 320
            else:
                bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_display(bad, 2676, 1236, 480, 1, 1.3, 'yes')

    def test_missing_duplicate_or_disagreeing_window_readback_rejects(self):
        for raw in ('', API32_CLAMP.replace('DisplayFrames', 'UnknownFrames'), API32_CLAMP + API32_CLAMP,
                    API32_CLAMP.replace('cur=2472x1236', 'cur=2676x1236')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                window_geometry(raw)

    def test_original_png_must_match_exact_logical_dimensions(self):
        p = self.out / 'original.png'
        p.write_bytes(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 2676, 1236))
        self.assertTrue(verify_png(p, 2676, 1236)['verified'])
        p.write_bytes(p.read_bytes()[:16] + struct.pack('>II', 2472, 1236))
        with self.assertRaises(ValueError):
            verify_png(p, 2676, 1236)

    def test_restore_preserves_original_overrides_free_mode_and_settings(self):
        self.android('shell', 'wm', 'size', '1080x2160')
        self.android('shell', 'wm', 'density', '420')
        self.android('shell', 'wm', 'user-rotation', 'free')
        self.android.settings['font_scale'] = '1.15'
        self.android.night = 'yes'
        previous = self.display.observe('previous')
        self.display.configure(2676, 1236, 480, 1.0, 'no')
        restored = self.display.restore(previous, 'restored')
        for key in ('size', 'density', 'rotationMode', 'userRotation', 'accelerometerRotation', 'fontScale', 'nightMode', 'logical'):
            self.assertEqual(restored[key], previous[key], key)

    def test_auto_and_custom_night_policies_are_restored_as_policies(self):
        for policy in ('auto', 'custom'):
            with self.subTest(policy=policy):
                self.android.night = policy
                previous = self.display.observe('policy-previous')
                self.display.configure(2676, 1236, 480, 1.0, 'yes')
                restored = self.display.restore(previous, 'policy-restored')
                self.assertEqual(restored['nightMode'], policy)
                self.assertEqual(self.android.night, policy)
                self.assertIn('notnight', restored['configuration'])

    def test_failed_restore_still_attempts_other_settings_and_refuses_pass(self):
        previous = self.display.observe('previous')
        self.display.configure(2676, 1236, 480, 1.3, 'yes')
        self.android.fail_next = ('shell', 'wm', 'size', 'reset')
        with self.assertRaisesRegex(ValueError, 'restoration failed'):
            self.display.restore(previous, 'failed-restore')
        self.assertEqual(self.android.settings['font_scale'], '1.0')
        self.assertEqual(self.android.settings['user_rotation'], '0')
        self.assertEqual(self.android.night, 'no')

    def test_both_required_loading_and_seven_case_paths_share_real_setup(self):
        source = (ROOT / 'tools/gecko/glass_ui_validation.py').read_text()
        tree = ast.parse(source)
        for name in ('capture_loading_landscape', 'capture_acceptance_suite'):
            method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            calls = [n.func.attr for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'display']
            with self.subTest(path=name):
                self.assertIn('configure', calls)
                self.assertIn('require', calls)
                self.assertIn('restore', calls)
        configurations = next(n.value for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'CONFIGURATIONS' for t in n.targets))
        self.assertEqual(ast.literal_eval(configurations), (
            ('default-light', 412, 892, 1.0, 'no'), ('enlarged-light', 412, 892, 1.3, 'no'),
            ('narrow-light', 320, 740, 1.6, 'no'), ('landscape-light', 892, 412, 1.0, 'no'),
            ('default-dark', 412, 892, 1.0, 'yes'), ('enlarged-dark', 412, 892, 1.3, 'yes'),
            ('safearea-light', 412, 892, 1.0, 'no')))


class ActualDisplayFormatRegressionTest(unittest.TestCase):
    def test_complete_original_api32_and_api35_natural_dumps(self):
        fixtures = ((API32_NATURAL, 'cb619964a8eeedeb1ffb76d30f7ff4f04005ef80b24765ac7767c3b1161d23eb'),
                    (API35_NATURAL, 'a63810ac7bcaeb2a394f82f730b6a311f9684906349caa42ac5a9c23d69ded07'))
        for raw, digest in fixtures:
            with self.subTest(digest=digest):
                self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(), digest)
                self.assertEqual(window_geometry(raw), dict(width=1236, height=2676, rotation=0, density=480))

    def test_actual_override_density_takes_precedence_and_wrong_requested_density_fails(self):
        raw = API32_NATURAL.replace('480dpi cur=', '480dpi base=1236x2676 420dpi cur=', 1)
        logical = window_geometry(raw)
        self.assertEqual(logical['density'], 420)
        with tempfile.TemporaryDirectory() as directory:
            display = GlassDisplay(Android32DisplayModel(), directory,
                lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
            state = display.observe('natural')
            state['logical'] = logical
            with self.assertRaises(ValueError):
                validate_display(state, 1236, 2676, 480, 0, 1.0, 'no')

    def test_malformed_and_duplicate_base_or_current_fields_do_not_fall_back(self):
        mutations = (
            ('cur=1236x2676', 'base=broken cur=1236x2676'),
            ('cur=1236x2676', 'base=1236x2676 480dpi base=broken cur=1236x2676'),
            ('cur=1236x2676', 'base=1236x2676 480dpi base=1236x2676 480dpi cur=1236x2676'),
            ('cur=1236x2676', 'cur=1236x2676 cur=broken'),
            ('cur=1236x2676', 'cur=1236x2676 cur=1236x2676'),
            ('cur=1236x2676', 'cur=1236x2676.5'),
            ('cur=1236x2676', 'base=1236x2676 480dpi.5 cur=1236x2676'),
            ('cur=1236x2676', 'cur=broken'),
        )
        for old, new in mutations:
            with self.subTest(new=new), self.assertRaises(ValueError):
                window_geometry(API32_NATURAL.replace(old, new, 1))

    def test_malformed_or_duplicate_initial_and_frame_records_are_ambiguous(self):
        for raw in (API32_NATURAL + '\n    init=broken\n',
                    API32_NATURAL + '\n  DisplayFrames w=broken\n',
                    API32_NATURAL + '\n  DisplayFrames w=1236 h=2676 r=0\n',
                    API32_NATURAL.replace('DisplayFrames w=1236 h=2676 r=0', 'DisplayFrames w=1236 h=2676 r=4')):
            with self.subTest(raw=raw[-120:]), self.assertRaises(ValueError):
                window_geometry(raw)

    def test_bad_density_and_disagreeing_current_bounds_still_fail(self):
        mutations = (
            ('init=1236x2676 480dpi', 'init=1236x2676 0dpi'),
            ('cur=1236x2676', 'base=1236x2676 0dpi cur=1236x2676'),
            ('cur=1236x2676', 'base=0x2676 480dpi cur=1236x2676'),
            ('cur=1236x2676', 'cur=2676x1236'),
            ('480dpi cur=', '480dpi base=1236x2676 unknown-dpi cur='),
        )
        for old, new in mutations:
            with self.subTest(new=new), self.assertRaises(ValueError):
                window_geometry(API32_NATURAL.replace(old, new, 1))


if __name__ == '__main__':
    unittest.main()
