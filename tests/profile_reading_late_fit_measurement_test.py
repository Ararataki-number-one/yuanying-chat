"""Exercise late viewport and compositor measurements using production BrowserReading."""

import unittest
from unittest.mock import patch

import profile_reading_fit_completion_test as fit_host


JAVA_HOST = r'''
package local.pocketchat;

import android.view.MotionEvent;

public final class ReadingFitCompletionHost {
  private static final float EARLY_SCALE = 2.6418769f;
  private static final float FITTED_SCALE = 2.6086957f;

  private static void check(boolean passed, String description) {
    if (!passed) throw new AssertionError(description);
  }

  private static ChatSession initiallyFitted(int viewportWidth, float scale) {
    ChatSession session = new ChatSession(new ChatSession.Prefs());
    session.web.width = 945;
    session.web.scale = scale;
    session.web.scrollY = 320;
    session.web.measuredViewportRequired = true;
    BrowserReading reading = new BrowserReading(session);
    session.web.reading = reading;
    reading.configure(true);
    reading.started(session.web.url);
    reading.visible(session.web.url);
    reading.fit();
    reading.viewportMeasured(viewportWidth);
    session.handler.drain();
    check(session.web.alignCalls == 1 && session.web.zoomCalls == 0,
        "The first valid measured fit consumes one pending alignment");
    session.web.scrollY = 477;
    return session;
  }

  public static void main(String[] args) {
    ChatSession settled = initiallyFitted(358, EARLY_SCALE);
    settled.web.reading.viewportMeasured(362);
    settled.handler.drain();
    check(settled.web.zoomCalls == 1 && Math.abs(settled.web.lastFactor - 945f / 362 / EARLY_SCALE) < .00001f,
        "A late layout measurement beyond the physical fit tolerance must request a correction");
    settled.web.scale = FITTED_SCALE;
    settled.web.reading.nativeScaleMeasured();
    settled.handler.drain();
    check(settled.web.zoomCalls == 1 && settled.web.alignCalls == 1 && settled.web.scrollY == 477,
        "Late convergence preserves the current scroll and never realigns the old anchor");

    ChatSession compositor = initiallyFitted(362, FITTED_SCALE);
    compositor.web.scale = EARLY_SCALE;
    compositor.web.reading.nativeScaleMeasured();
    compositor.handler.drain();
    check(compositor.web.zoomCalls == 1 && compositor.web.alignCalls == 1,
        "Late compositor scale also stays inside the original one-time fit intent");

    ChatSession exhausted = initiallyFitted(358, EARLY_SCALE);
    exhausted.web.reading.viewportMeasured(362);
    for (int i = 0; i < 6; i++) {
      exhausted.web.reading.nativeScaleMeasured();
      exhausted.handler.drain();
    }
    check(exhausted.web.zoomCalls == 3 && exhausted.web.alignCalls == 1,
        "Ignored corrections remain bounded without another alignment");

    ChatSession touched = initiallyFitted(358, EARLY_SCALE);
    touched.web.reading.touch(new MotionEvent(MotionEvent.ACTION_DOWN, 1, 100, 100));
    touched.web.reading.touch(new MotionEvent(MotionEvent.ACTION_UP, 1, 100, 100));
    touched.web.reading.viewportMeasured(362);
    touched.web.reading.nativeScaleMeasured();
    touched.handler.drain();
    check(touched.web.zoomCalls == 0 && touched.web.alignCalls == 1 && touched.web.scrollY == 477,
        "A real touch retires the earlier fit before the late measurement arrives");
  }
}
'''


class LateFitMeasurementTests(unittest.TestCase):
    def test_late_measurement_corrects_fit_without_consuming_alignment_twice(self):
        with patch.object(fit_host, 'JAVA_HOST', JAVA_HOST):
            result = fit_host.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
