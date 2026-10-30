package local.pocketchat;

import org.json.JSONObject;
import java.util.*;
import java.util.function.Supplier;

/** Remember rendered inputs only; callers must still replace the action payload. */
final class DownloadRowBinding {
  static final class Frame {
    final Locale locale=Locale.getDefault();final TimeZone zone=TimeZone.getDefault();final int red,cyan,green;
    Frame(int red,int cyan,int green){this.red=red;this.cyan=cyan;this.green=green;}
    boolean same(Frame other){return other!=null&&red==other.red&&cyan==other.cyan&&green==other.green&&locale.equals(other.locale)&&zone.equals(other.zone);}
  }
  static final class Stamp {
    final String name,state,reason,location,environment;final long time,received,total;final boolean stale;final Frame frame;
    Stamp(JSONObject row,long now,String environment,Frame frame){
      name=row.optString("name","文件");state=row.optString("state");reason=row.optString("reason");location=row.optString("location","原先选择的保存位置");
      time=row.optLong("time");received=row.optLong("received");total=row.optLong("total",-1);this.environment=environment;this.frame=frame;stale=stale(row,now);
    }
    boolean matches(JSONObject row,long now,String environment,Frame frame){
      return this.frame.same(frame)&&Objects.equals(this.environment,environment)&&name.equals(row.optString("name","文件"))&&state.equals(row.optString("state"))&&reason.equals(row.optString("reason"))&&location.equals(row.optString("location","原先选择的保存位置"))&&time==row.optLong("time")&&received==row.optLong("received")&&total==row.optLong("total",-1)&&stale==stale(row,now);
    }
  }
  private Stamp applied;private long formattedTime=Long.MIN_VALUE;private boolean formattedSaved;private Locale formattedLocale;private TimeZone formattedZone;private String formatted;
  Stamp next(JSONObject row,long now,String environment,Frame frame){return applied!=null&&applied.matches(row,now,environment,frame)?null:new Stamp(row,now,environment,frame);}
  void applied(Stamp stamp){applied=stamp;}
  static boolean stale(JSONObject row,long now){return !"saved".equals(row.optString("state"))&&DownloadListPolicy.busy(row.optString("state"))&&row.optLong("updated")>0&&now-row.optLong("updated")>15000;}
  String time(JSONObject row,Supplier<String> format){
    long value=row.optLong("time");boolean saved="saved".equals(row.optString("state"));Locale locale=Locale.getDefault();TimeZone zone=TimeZone.getDefault();
    if(formatted!=null&&formattedTime==value&&formattedSaved==saved&&locale.equals(formattedLocale)&&zone.equals(formattedZone))return formatted;
    String next=format.get();formattedTime=value;formattedSaved=saved;formattedLocale=locale;formattedZone=zone;formatted=next;return next;
  }
}
