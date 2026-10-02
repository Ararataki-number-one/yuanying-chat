package local.pocketchat;

import android.content.*;
import android.net.*;
import org.json.*;
import java.io.*;
import java.util.*;

/** Profile-local preferences; defaults retain existing behavior. */
final class AppPrefs {
  static final String[] KEYS={"autoHistory","saveDraft","restoreScroll","backgroundWait","replyNotice","downloadNotice","networkNotice","wifiDownloads","cleanTemporaryCache"};
  static final String[] LABELS={"自动同步可见历史会话","保存本机输入草稿","恢复网页滚动位置","后台等待回复","回复完成通知","文件保存完成通知","网络中断提醒","仅在 Wi-Fi 下载文件","自动清理 30 天以上的无引用中间文件"};
  static boolean enabled(Context c,String key){return c.getSharedPreferences("chat",0).getBoolean(key,!key.equals("wifiDownloads")&&!key.equals("cleanTemporaryCache"));}
  static JSONObject values(Context c){JSONObject out=new JSONObject();for(String key:KEYS)try{out.put(key,enabled(c,key));}catch(Exception ignored){}return out;}
  static void apply(Context c,JSONObject options){SharedPreferences.Editor edit=c.getSharedPreferences("chat",0).edit();for(String key:KEYS)if(options.opt(key) instanceof Boolean)edit.putBoolean(key,options.optBoolean(key));edit.commit();}
  static boolean wifiConfirmed(Context c){try{ConnectivityManager cm=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);Network active=cm.getActiveNetwork();NetworkCapabilities caps=active==null?null:cm.getNetworkCapabilities(active);return caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);}catch(Exception e){return false;}}
  static void requireDownloadNetwork(Context c)throws IOException{if(enabled(c,"wifiDownloads")&&!wifiConfirmed(c))throw new IOException("仅 Wi-Fi 下载已开启，当前未确认 Wi-Fi，请连接 Wi-Fi 后继续");}
  static void maintainCache(Context c){SharedPreferences prefs=c.getSharedPreferences("chat",0);long now=System.currentTimeMillis();if(!enabled(c,"cleanTemporaryCache")||now-prefs.getLong("temporaryCacheChecked",0)<24L*60*60*1000)return;prefs.edit().putLong("temporaryCacheChecked",now).apply();java.util.concurrent.ExecutorService worker=java.util.concurrent.Executors.newSingleThreadExecutor();worker.execute(()->{temporaryCache(c,now,true);worker.shutdown();});}
  static JSONObject temporaryCache(Context c,long now,boolean remove){Set<String> protectedNames=new HashSet<>();JSONObject result=J.obj("count",0,"bytes",0,"removed",0,"protected",0);try{JSONArray rows=new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]"));for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null)protectedNames.add(row.optString("partial"));}}catch(Exception ignored){}
    try{File root=c.getCacheDir().getCanonicalFile();File[] files=root.listFiles();if(files==null)return result;long bytes=0;int count=0,removed=0,kept=0;for(File file:files){if(!file.isFile()||!file.getName().matches("download-[A-Za-z0-9-]+[.]part")||!root.equals(file.getCanonicalFile().getParentFile()))continue;if(protectedNames.contains(file.getName())){kept++;continue;}if(file.lastModified()<=0||file.lastModified()>now-30L*24*60*60*1000)continue;count++;bytes+=file.length();if(remove&&file.delete())removed++;}return J.obj("count",count,"bytes",bytes,"removed",removed,"protected",kept);}catch(Exception e){return result;}
  }
}
