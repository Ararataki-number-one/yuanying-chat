package local.pocketchat;

import android.content.Context;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.AtomicFile;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ExecutorService;
import org.json.*;

/** Independent, foreground-requested public history. Never owns a transfer/job/browser. */
final class ReleaseHistory {
  private static ReleaseHistory instance;
  static synchronized ReleaseHistory get(Context c){if(Profiles.processSlot()!=0)throw new IllegalStateException("历史记录仅由应用主进程管理");if(instance==null)instance=new ReleaseHistory(Profiles.global(c));return instance;}
  final Context context;final AtomicFile cache;final ExecutorService worker=AppUpdateManager.backgroundExecutor("release-history");
  List<ReleaseHistoryPolicy.Entry> entries=Collections.emptyList();long revision=1,fetchedAt,clientSerial,client,epoch;int origin=-1,nextPage=1;boolean cacheLoaded,loading,eof;String error="";
  volatile AppUpdateRoute.Factory active;
  volatile AppUpdateRoute.Opener opener=AppUpdateRoute.OFFICIAL;
  volatile AppUpdateTransfer.ConnectionFactory direct=AppUpdateTransfer.OFFICIAL;
  ReleaseHistory(Context context){this.context=context;cache=new AtomicFile(new File(new File(context.getNoBackupFilesDir(),"release-history"),"history.json"));}
  synchronized long attach(int slot){if(!AppUpdates.validSlot(slot))return 0;long previous=client;client=++clientSerial;origin=slot;if(previous!=0)cancelLocked();return client;}
  synchronized void detach(long owned){if(owned==0||owned!=client)return;client=0;cancelLocked();}
  void cancelLocked(){epoch++;loading=false;AppUpdateRoute.Factory connection=active;active=null;if(connection!=null)connection.finished();revision++;}
  synchronized Bundle status(){Bundle b=new Bundle();b.putLong("revision",revision);b.putLong("fetchedAt",fetchedAt);b.putInt("count",entries.size());b.putBoolean("loading",loading);b.putBoolean("loaded",cacheLoaded);b.putBoolean("eof",eof);b.putBoolean("capped",entries.size()>=ReleaseHistoryPolicy.MAX_ENTRIES||nextPage>ReleaseHistoryPolicy.MAX_PAGE);b.putString("error",error);return b;}
  synchronized List<ReleaseHistoryPolicy.Entry> visible(int maximum,String ceiling){List<ReleaseHistoryPolicy.Entry> out=new ArrayList<>();boolean bound=ReleaseHistoryPolicy.VERSION.matcher(ceiling).matches();for(ReleaseHistoryPolicy.Entry e:entries){if(bound&&ReleaseHistoryPolicy.compare(e.version,ceiling)>0)continue;out.add(e);if(out.size()>=Math.min(maximum,ReleaseHistoryPolicy.MAX_ENTRIES))break;}return Collections.unmodifiableList(out);}
  void load(long owned,int wanted,boolean force){final long request;final int slot;
    synchronized(this){if(owned==0||owned!=client||loading)return;request=++epoch;slot=origin;loading=true;error="";revision++;}
    worker.execute(()->run(owned,request,slot,Math.max(10,Math.min(100,wanted)),force));
  }
  synchronized boolean cancelled(long owned,long request){return owned!=client||request!=epoch||Thread.currentThread().isInterrupted();}
  void run(long owned,long request,int slot,int wanted,boolean force){AppUpdateRoute.Factory factory=null;
    try{
      readCache();if(cancelled(owned,request))return;
      int page;List<ReleaseHistoryPolicy.Entry> result;boolean refreshing;
      synchronized(this){long now=System.currentTimeMillis();boolean fresh=fetchedAt>0&&now>=fetchedAt&&now-fetchedAt<AppUpdatePolicy.DAY;if(!force&&entries.size()>=wanted&&fresh)return;refreshing=force||entries.size()>=wanted&&!fresh;if(!refreshing&&(eof||entries.size()>=100||nextPage>100))return;page=refreshing?1:nextPage;result=entries;}
      AppUpdateRoute.Selection selection=AppUpdateRoute.select(context,slot,null);
      if(AppUpdateRoute.INTERNAL.equals(selection.scope.source)&&selection.lease==null)throw new IOException("环境网络尚未连接，暂时无法读取历史记录");
      factory=new AppUpdateRoute.Factory(context,selection,opener,direct,ReleaseHistoryPolicy.url(page),AppUpdateRoute.Purpose.HISTORY);
      synchronized(this){if(cancelled(owned,request)){factory.finished();return;}active=factory;}
      boolean finished=false;int target=wanted;long operationDeadline=SystemClock.elapsedRealtime()+60000;
      for(int scanned=0;scanned<ReleaseHistoryPolicy.SCAN_PAGES&&page<=ReleaseHistoryPolicy.MAX_PAGE;scanned++){
        if(cancelled(owned,request)||SystemClock.elapsedRealtime()>operationDeadline)throw new IOException("历史读取已结束");
        String text=readPage(factory,page,owned,request);JSONArray raw=new JSONArray(text);List<ReleaseHistoryPolicy.Entry> parsed=ReleaseHistoryPolicy.parse(text);result=ReleaseHistoryPolicy.merge(result,parsed);page++;
        if(raw.length()<ReleaseHistoryPolicy.PAGE_SIZE){finished=true;break;}
        // A refresh first revalidates one recent window; older cache remains explicitly sourced.
        if(refreshing?parsed.size()>=10:result.size()>=target)break;
      }
      if(cancelled(owned,request))return;
      long now=System.currentTimeMillis();String cacheError="";try{writeCache(result,page,finished,now);}catch(IOException unavailable){cacheError="历史已取得，本地缓存暂未保存";}
      synchronized(this){if(cancelled(owned,request))return;entries=result;nextPage=page;eof=finished;fetchedAt=now;error=cacheError;revision++;}
    }catch(Exception unavailable){synchronized(this){if(!cancelled(owned,request)){error="历史记录暂时无法加载，已保留本地记录";revision++;}}}
    finally{if(factory!=null)factory.finished();synchronized(this){if(active==factory)active=null;if(epoch==request){loading=false;revision++;}}}
  }
  String readPage(AppUpdateRoute.Factory factory,int page,long owned,long request)throws IOException {
    String url=ReleaseHistoryPolicy.url(page);long deadline=SystemClock.elapsedRealtime()+20000;HttpURLConnection connection=factory.open(url);
    try{connection.setInstanceFollowRedirects(false);connection.setUseCaches(false);connection.setConnectTimeout(15000);connection.setReadTimeout(15000);connection.setRequestProperty("Accept","application/vnd.github+json");connection.setRequestProperty("X-GitHub-Api-Version","2022-11-28");connection.setRequestProperty("Accept-Encoding","identity");connection.setRequestProperty("User-Agent","PocketChat-update/"+AppVersion.name(context));
      int code=connection.getResponseCode();factory.check();if(code!=200)throw new IOException("历史服务器响应异常");String encoding=connection.getContentEncoding();
      if(!ReleaseHistoryPolicy.jsonType(connection.getContentType())||encoding!=null&&!encoding.isEmpty()&&!"identity".equalsIgnoreCase(encoding)||connection.getContentLengthLong()>ReleaseHistoryPolicy.MAX_BYTES)throw new IOException("历史记录响应格式无效");
      try(InputStream in=connection.getInputStream()){return ReleaseHistoryPolicy.text(ReleaseHistoryPolicy.read(in,ReleaseHistoryPolicy.MAX_BYTES,()->{if(cancelled(owned,request)||SystemClock.elapsedRealtime()>deadline)return true;try{factory.check();return false;}catch(IOException lost){return true;}}));}
    }finally{connection.disconnect();factory.released(connection);}
  }
  void readCache(){synchronized(this){if(cacheLoaded)return;}
    List<ReleaseHistoryPolicy.Entry> saved=Collections.emptyList();long time=0;int page=1;boolean end=false;
    try(InputStream input=cache.openRead()){
      JSONObject json=new JSONObject(ReleaseHistoryPolicy.text(ReleaseHistoryPolicy.read(input,ReleaseHistoryPolicy.MAX_BYTES,()->false)));
      if(json.optInt("schema")!=1||!ReleaseHistoryPolicy.API.equals(json.optString("source")))throw new IOException("历史缓存格式无效");JSONArray rows=json.getJSONArray("entries");if(rows.length()>100)throw new IOException("历史缓存过大");List<ReleaseHistoryPolicy.Entry> parsed=new ArrayList<>();
      for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);String tag=row.getString("tag"),body=row.getString("body");long id=row.getLong("id"),published=row.getLong("published");if(!ReleaseHistoryPolicy.stableTag(tag)||id<=0||body.length()>ReleaseNotes.MAX_TEXT||published<0)throw new IOException("历史缓存内容无效");parsed.add(new ReleaseHistoryPolicy.Entry(id,tag,body,published));}
      saved=ReleaseHistoryPolicy.merge(Collections.emptyList(),parsed);page=json.getInt("nextPage");if(page<1||page>101)throw new IOException("历史缓存页码无效");time=json.getLong("fetchedAt");end=json.optBoolean("eof");
    }catch(Exception ignored){saved=Collections.emptyList();time=0;page=1;end=false;/* Missing/corrupt cache cannot affect update state. */}
    synchronized(this){if(!cacheLoaded){entries=saved;nextPage=page;fetchedAt=time;eof=end;cacheLoaded=true;revision++;}}
  }
  void writeCache(List<ReleaseHistoryPolicy.Entry> records,int page,boolean end,long now)throws IOException {
    try{JSONArray rows=new JSONArray();for(ReleaseHistoryPolicy.Entry e:records)rows.put(e.json());byte[] bytes;
      while(true){boolean trimmed=rows.length()<records.size();JSONObject json=new JSONObject().put("schema",1).put("source",ReleaseHistoryPolicy.API).put("nextPage",trimmed?1:page).put("eof",!trimmed&&end).put("fetchedAt",now).put("entries",rows);bytes=json.toString().getBytes(StandardCharsets.UTF_8);if(bytes.length<=ReleaseHistoryPolicy.MAX_BYTES)break;if(rows.length()==0)throw new IOException("历史缓存过大");JSONArray shorter=new JSONArray();for(int i=0;i<rows.length()-1;i++)shorter.put(rows.get(i));rows=shorter;}
      FileOutputStream out=cache.startWrite();try{out.write(bytes);out.getFD().sync();cache.finishWrite(out);try(InputStream saved=cache.openRead()){if(!Arrays.equals(bytes,ReleaseHistoryPolicy.read(saved,ReleaseHistoryPolicy.MAX_BYTES,()->false)))throw new IOException("历史缓存尚未完成保存");}}catch(Exception failure){cache.failWrite(out);throw new IOException("历史缓存保存失败",failure);}
    }catch(JSONException invalid){throw new IOException("历史缓存格式无效",invalid);}
  }
}
