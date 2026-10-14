package local.pocketchat;

import android.inputmethodservice.InputMethodService;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.TextView;

/**
 * Integration-only passive input method for controlled SDK protocol cases.
 * This real IME window has no editor API calls, keyboard keys or state machine.
 * The existing fixture remains the sole writer of its original SDK connection.
 */
public final class ControlledCaretInputMethodService extends InputMethodService {
    @Override public View onCreateInputView() {
        TextView panel = new TextView(this);
        panel.setText("Controlled SDK protocol fixture — passive IME panel");
        panel.setGravity(android.view.Gravity.CENTER);
        panel.setFocusable(false);
        panel.setFocusableInTouchMode(false);
        panel.setClickable(false);
        panel.setLongClickable(false);
        int height = Math.round(220 * getResources().getDisplayMetrics().density);
        panel.setLayoutParams(new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height));
        return panel;
    }

    // A genuine input window remains visible even with the emulator hardware keyboard.
    @Override public boolean onEvaluateInputViewShown() { return true; }
    @Override public boolean onEvaluateFullscreenMode() { return false; }

    @Override public void onStartInput(EditorInfo info, boolean restarting) { }
    @Override public void onStartInputView(EditorInfo info, boolean restarting) { }
    @Override public void onUpdateSelection(int oldStart, int oldEnd, int start, int end,
                                            int candidatesStart, int candidatesEnd) { }

    // Android's default implementations call finishComposingText. Do not call super.
    @Override public void onFinishInputView(boolean finishingInput) { }
    @Override public void onFinishInput() { }

    // Hardware events continue through Android to the original Gecko editor.
    @Override public boolean onKeyDown(int code, KeyEvent event) { return false; }
    @Override public boolean onKeyUp(int code, KeyEvent event) { return false; }
    @Override public boolean onKeyMultiple(int code, int count, KeyEvent event) { return false; }
    @Override public boolean onKeyLongPress(int code, KeyEvent event) { return false; }
}
