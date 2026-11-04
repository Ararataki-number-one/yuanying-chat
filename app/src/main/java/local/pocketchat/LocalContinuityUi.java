package local.pocketchat;

import android.content.*;
import android.content.ClipboardManager;
import android.text.*;
import android.widget.*;
import java.text.DateFormat;
import java.util.*;
import java.util.concurrent.*;

/** Dialog lifecycle and copy helpers, shared without navigating the live website. */
final class LocalContinuityUi {
  static ExecutorService reader(String name){return Executors.newSingleThreadExecutor(r->{Thread thread=new Thread(r,name);thread.setPriority(Thread.MIN_PRIORITY);return thread;});}
  static boolean current(MainActivity a,ChatSession owner){
    if(a.destroyed||a.isFinishing()||a.session!=owner||owner.deleted)return false;
    try{org.json.JSONObject row=ProfileCatalog.get(a).item(Profiles.slot(a));
      return row.optBoolean("created")&&!row.optBoolean("resetting")&&!row.optBoolean("deleting")&&row.optInt("generation",-1)==owner.environmentGeneration&&row.optString("environmentId").equals(owner.environmentId);
    }catch(RuntimeException unavailable){return false;}
  }
  static String time(long value){return value<=0?"历史副本 · 时间未记录":DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT,Locale.getDefault()).format(new Date(value));}
  static void copy(MainActivity a,ChatSession owner,String label,String text,TextView feedback){
    if(!current(a,owner))return;ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);
    if(text.length()>180000){feedback.setText("内容较长，请打开单条消息并选择所需文字复制。");return;}
    if(clipboard!=null)try{clipboard.setPrimaryClip(ClipData.newPlainText(label,text));feedback.setText("已复制，可手动粘贴");}catch(RuntimeException unavailable){feedback.setText("剪贴板暂时不可用，请重试或选择较短的文字复制。");}
  }
  static TextView text(MainActivity a,String value,int size){TextView view=DesignUi.text(a,value,size,DesignUi.TEXT);view.setTextIsSelectable(true);return view;}
  static void watch(EditText input,Runnable changed){input.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){changed.run();}public void afterTextChanged(Editable value){}});}
  static TextView status(MainActivity a,LinearLayout box){TextView text=DesignUi.text(a,"正在读取本机记录…",12,DesignUi.MUTED);text.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(text);return text;}
  static void row(MainActivity a,LinearLayout box,String title,String subtitle,Runnable action){
    LinearLayout card=DesignUi.card(a);TextView name=DesignUi.text(a,title,15,DesignUi.TEXT);name.setMaxLines(3);name.setEllipsize(TextUtils.TruncateAt.END);card.addView(name);TextView detail=DesignUi.text(a,subtitle,12,DesignUi.MUTED);detail.setMaxLines(3);detail.setEllipsize(TextUtils.TruncateAt.END);detail.setPadding(0,a.dp(6),0,0);card.addView(detail);card.setFocusable(true);card.setClickable(true);card.setContentDescription(title+"，"+subtitle);card.setOnClickListener(v->action.run());DesignUi.addCard(box,card);
  }
}
