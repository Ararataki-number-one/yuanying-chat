package local.pocketchat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.net.HttpURLConnection;
import java.net.URI;
import java.util.Collections;

/** Standalone instrumentation Activity. It never creates a Gecko runtime or a route. */
public final class MainActivity extends Activity {
    final Handler handler = new Handler(Looper.getMainLooper());
    final ChatSession session = new ChatSession();
    final AiDiagnosticUi diagnosticUi = new AiDiagnosticUi(this);

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (!AiDiagnosticUi.enabled(this)) {
            throw new IllegalStateException("Unexpected instrumentation package");
        }
        session.attach();
        LinearLayout content = DesignUi.column(this);
        Button tools = new Button(this);
        tools.setText("网页工具");
        tools.setContentDescription("网页工具");
        tools.setOnLongClickListener(view -> {
            diagnosticUi.show();
            return true;
        });
        content.addView(tools);
        setContentView(content);
    }

    int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        diagnosticUi.close();
        session.detach();
        super.onDestroy();
    }
}

/** Recreated with its Activity so an uncertain request cannot acquire a new owner. */
final class ChatSession {
    private static volatile ChatSession attached;
    final SyntheticWeb web = new SyntheticWeb(this);
    volatile long connectionEpoch = 1;

    static ChatSession peek() {
        return attached;
    }

    void attach() {
        attached = this;
    }

    void detach() {
        if (attached == this) attached = null;
    }
}

/** Synthetic native events in the real production evidence journal. */
final class SyntheticWeb {
    private final ChatSession owner;
    private final Object tab = new Object();
    private final AiDiagnosticEvidence.Journal events = new AiDiagnosticEvidence.Journal(() -> 0L);

    SyntheticWeb(ChatSession owner) {
        this.owner = owner;
        events.register(tab);
        events.start(tab);
        events.error(tab, AiDiagnosticEvidence.Signal.CERTIFICATE_REJECTED, 50, 2);
        events.stop(tab, false);
    }

    AiDiagnosticEvidence aiDiagnosticEvidence() {
        AiDiagnosticEvidence.Entry snapshot = events.snapshot(tab, () -> ChatSession.peek() == owner);
        return new AiDiagnosticEvidence(Collections.singletonList(snapshot));
    }
}

final class GeckoAddressUi {
    static boolean available(MainActivity activity) {
        return !activity.isFinishing() && !activity.isDestroyed()
                && ChatSession.peek() == activity.session;
    }
}

final class AppAppearance {
    static AlertDialog.Builder dialog(Context context) {
        return new AlertDialog.Builder(context);
    }
}

/** Native widgets for the fixture without the product theme and resource graph. */
final class DesignUi {
    static final int TEXT = Color.BLACK;

    static LinearLayout column(Context context) {
        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        return column;
    }

    static Button button(Context context, String label, boolean primary, Runnable action) {
        Button button = new Button(context);
        button.setText(label);
        button.setAllCaps(false);
        button.setOnClickListener(view -> action.run());
        return button;
    }

    static TextView text(Context context, String value, int size, int color) {
        TextView text = new TextView(context);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(color);
        return text;
    }

    static EditText input(LinearLayout parent, String label, String value, String hint) {
        Context context = parent.getContext();
        parent.addView(text(context, label, 14, TEXT));
        EditText input = new EditText(context);
        input.setSingleLine(true);
        input.setContentDescription(label);
        input.setText(value);
        input.setHint(hint);
        parent.addView(input);
        return input;
    }
}

final class BrowserNetworkGuard {
    private static final String FIXTURE_HOST = URI.create(AiDiagnosticRoute.ENDPOINT).getHost();

    static boolean localHost(String host) {
        // The fixture has only one synthetic destination. Never resolve a hostname.
        return !FIXTURE_HOST.equalsIgnoreCase(host);
    }
}

final class AppUpdateTransfer {
    static void disconnectLater(HttpURLConnection connection) {
        // The fake connection has no sockets and its disconnect only releases fixture state.
        connection.disconnect();
    }
}
