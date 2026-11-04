package local.pocketchat;

import android.app.*;import android.content.*;import android.graphics.*;import android.graphics.drawable.*;import android.net.Uri;import android.os.*;import android.view.*;import android.widget.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.AtomicLong;import java.util.function.*;import org.json.*;

/** Compile-only app boundaries. All android.* classes come from the actual SDK android.jar. */
class ThemedActivity extends Activity{}
class Profiles{static Context global(Context c){return c;}static int slot(Context c){return 0;}static Class<? extends Activity> activity(int slot){return Activity.class;}}
class MainActivity extends Activity{FileDownloads downloads;}
class FileDownloads{DownloadTasks tasks;void taskActions(JSONObject row){}}
class DownloadTasks{JSONArray rows;static String amount(long n){return "";}static String progress(JSONObject row){return "";}static String label(String state){return "";}static void put(JSONObject row,Object... entries){}}
class AppAppearance{static AlertDialog.Builder dialog(Context c){return new AlertDialog.Builder(c);}static int color(int value){return value;}}
class DesignUi{
 static int MUTED,TEXT,RED,BLUE,GREEN,CYAN,LINE,CARD;static int dp(Context c,int n){return n;}
 static LinearLayout row(Context c){return new LinearLayout(c);}static LinearLayout column(Context c){return new LinearLayout(c);}static LinearLayout card(Context c){return column(c);}static LinearLayout screen(Context c){return column(c);}static LinearLayout body(Activity a,LinearLayout root,String title,Runnable back){return column(a);}
 static TextView text(Context c,String text,int size,int color){return new TextView(c);}static Button button(Context c,String text,boolean primary,Runnable action){return new Button(c);}static int actionWidth(Button b,int min){return min;}
 static LinearLayout tabs(Context c,String[] labels,int selected,IntConsumer choice){return row(c);}static EditText searchInput(LinearLayout parent,String hint){return new EditText(parent.getContext());}static View nav(Activity a,int index,IntConsumer select,Button[] buttons){return row(a);}
 static void note(LinearLayout box,String text){}static void empty(LinearLayout box,String title,String detail,String action,Runnable run){}static AlertDialog message(Activity a,String title,String message){return null;}static ImageView icon(Context c,String key,int color,int size){return new ImageView(c);}static Drawable surface(Context c,int color,int radius,int stroke){return null;}
}
class ReferenceUi{static TextView text(Context c,String text,int size,int color,boolean bold){return new TextView(c);}static Button more(Context c,Runnable run){return new Button(c);}}
class Ui{static class Icon extends Drawable{Icon(String key,int color){}public void draw(Canvas canvas){}public void setAlpha(int alpha){}public void setColorFilter(ColorFilter filter){}public int getOpacity(){return 0;}}}
class AppUpdates{static Bundle call(Context c,String method,Bundle extras){return new Bundle();}static void open(Activity a){}}
class DownloadDisplaySnapshot{static JSONArray read(Context c){return new JSONArray();}static Map<Integer,DownloadOwnerLabels.Owner> owners(Context c){return new HashMap<>();}}
class DownloadRefreshUi{DownloadRefreshUi(Activity a,LinearLayout box,Runnable retry){}void failed(){}void clear(){}}
class SavedDownloadMetadata{static class Watch{void close(){}}static Watch watch(Context c){return new Watch();}}
class DownloadLibraryChanges{static final AtomicLong revision=new AtomicLong();static Uri uri(Context c){return Uri.EMPTY;}}
class SavedFileActions{static final int EXPORT=85;Activity a;volatile boolean closed,busy;JSONObject exporting;final ExecutorService worker=Executors.newSingleThreadExecutor();final Handler main=new Handler(Looper.getMainLooper());SavedFileActions(Activity a){this.a=a;}void show(JSONObject row){}void result(int result,Intent data){}void close(){}static void problem(Activity a,String text){}}
class DownloadLibrary{static DownloadLibrary get(Context c){return new DownloadLibrary();}JSONObject saved(JSONObject expected){return expected;}}
class SealedFileIo{interface Action<T>{T run()throws Exception;}}
class SavedFileDeletion{static <T>T lease(Context c,Uri uri,SealedFileIo.Action<T> action)throws Exception{return action.run();}static <T>T leaseAll(Context c,List<Uri> uris,SealedFileIo.Action<T> action)throws Exception{return action.run();}static void onMain(Handler main,Runnable action)throws Exception{action.run();}}
class AppSettings{static int recentSlot(Context c){return 0;}}
class WorkspaceNavigation{static void select(Activity a,int current,int next){}}
