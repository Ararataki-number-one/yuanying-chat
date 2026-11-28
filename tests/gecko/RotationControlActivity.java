package local.pocketchat;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

/** Unlocked instrumentation-only Activity used to prove the same device can rotate. */
public final class RotationControlActivity extends Activity {
  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    TextView label=new TextView(this);
    label.setText("Rotation control");
    setContentView(label);
  }
}
