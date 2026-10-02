package local.pocketchat;
import android.content.*;import org.json.*;import java.io.*;import java.util.*;

/** Private metadata, without cookies or temporary signed download URLs. */
final class DownloadTasks {
 final Context context;final SharedPreferences prefs;JSONArray rows;
 DownloadTasks(Context c){context=c;prefs=c.getSharedPreferences("download-tasks",0);try{rows=new JSONArray(prefs.getString("rows","[]"));}catch(Exception e){rows=new JSONArray();}for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);DefaultDownloads.recover(context,r);String state=r.optString("state");if(Arrays.asList("downloading","preparing","saving","choosing").contains(state))put(r,"state",partial(r)!=null?"paused":"failed","reason","上次下载中断；可重新获取链接继续");}save();}
 static void put(JSONObject r,Object... pairs){try{for(int i=0;i<pairs.length;i+=2)r.put((String)pairs[i],pairs[i+1]);}catch(Exception ignored){}}
 JSONObject add(String source,String key,String conversation){JSONObject r=J.obj("id",UUID.randomUUID().toString(),"source",source,"key",key,"conversation",conversation,"name","正在获取文件","state","preparing","reason","","received",0,"total",-1,"time",System.currentTimeMillis());JSONArray next=new JSONArray();next.put(r);for(int i=0;i<rows.length();i++)next.put(rows.optJSONObject(i));rows=next;save();return r;}
 void save(){prefs.edit().putString("rows",rows.toString()).commit();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if("saved".equals(row.optString("state")))DownloadLibrary.get(context).add(context,row);}}
 File partial(JSONObject r){String n=r.optString("partial");if(!n.matches("download-[A-Za-z0-9-]+[.]part"))return null;File f=new File(context.getCacheDir(),n);return f.isFile()?f:null;}
 static String label(String state){switch(state){case "preparing":return "获取链接中";case "downloading":return "下载中";case "paused":return "已暂停";case "choosing":return "等待选择保存位置";case "saving":return "保存中";case "saved":return "已保存";case "cancelled":return "已取消";default:return "失败待处理";}}
 static String amount(long n){return Attachments.sizeLabel(n);}
 static String progress(JSONObject r){long received=r.optLong("received"),total=r.optLong("total",-1);return total>0?amount(received)+" / "+amount(total)+" · "+Math.min(100,received*100/total)+"%":amount(received);}
}
