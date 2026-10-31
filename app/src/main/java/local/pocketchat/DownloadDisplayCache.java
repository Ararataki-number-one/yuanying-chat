package local.pocketchat;

import android.content.Context;
import android.os.*;
import org.json.*;
import java.text.DateFormat;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/** Expensive complete reads stay on one worker; main receives at most forty rows. */
final class DownloadDisplayCache {
  static final ExecutorService worker=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"download-display");t.setDaemon(true);return t;});
  static final Handler main=new Handler(Looper.getMainLooper());
  static JSONArray cached;static Map<Integer,DownloadOwnerLabels.Owner> cachedOwners;static long cachedRevision=-1;
  static final LinkedHashMap<String,Page> pages=new LinkedHashMap<String,Page>(4,.75f,true){protected boolean removeEldestEntry(Map.Entry<String,Page> entry){return size()>3;}};
  static final class Page {
    final DownloadPageWindow window;final Map<Integer,String> names=new HashMap<>();final Map<String,String> times=new HashMap<>(),environmentLabels=new HashMap<>();
    final Locale locale=Locale.getDefault();final TimeZone zone=TimeZone.getDefault();final long revision;final Bundle update;
    Page(JSONArray all,Map<Integer,DownloadOwnerLabels.Owner> owners,int filter,String anchor,String viewed,long revision,Bundle update){
      window=new DownloadPageWindow(all,filter,anchor,viewed);this.revision=revision;this.update=update;
      for(DownloadOwnerLabels.Owner owner:owners.values())names.put(owner.slot,owner.name);
      DateFormat format=DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT,locale);format.setTimeZone(zone);
      for(int i=0;i<window.rows.length();i++){JSONObject row=window.rows.optJSONObject(i);String key=DownloadListPolicy.key(row);long time=row.optLong("time");times.put(key,time<=0?"时间未记录":("saved".equals(row.optString("state"))?"保存于 ":"开始于 ")+format.format(new Date(time)));environmentLabels.put(key,DownloadOwnerLabels.label(row,owners));}
    }
    Page(Page original,Bundle update){window=original.window;names.putAll(original.names);times.putAll(original.times);environmentLabels.putAll(original.environmentLabels);revision=original.revision;this.update=update;}
    boolean currentFormat(){return locale.equals(Locale.getDefault())&&zone.equals(TimeZone.getDefault());}
  }
  static void request(Context context,int filter,String anchor,String viewed,Consumer<Page> done,Consumer<RuntimeException> failure){
    Context app=Profiles.global(context);
    worker.execute(()->{try{
      long revision=DownloadLibraryChanges.revision.get();
      if(cached==null||cachedRevision!=revision){JSONArray next=DownloadDisplaySnapshot.read(app);Map<Integer,DownloadOwnerLabels.Owner> owners=DownloadDisplaySnapshot.owners(app);cached=next;cachedOwners=owners;cachedRevision=revision;pages.clear();}
      String key=filter+":"+anchor;Page prepared=pages.get(key);Bundle update=AppUpdates.call(app,"status",null);
      if(prepared==null||!prepared.currentFormat()){prepared=new Page(cached,cachedOwners,filter,anchor,viewed,cachedRevision,update);pages.put(key,prepared);}
      Page page=new Page(prepared,update);main.post(()->done.accept(page));
    }catch(RuntimeException unavailable){main.post(()->failure.accept(unavailable));}});
  }
}
