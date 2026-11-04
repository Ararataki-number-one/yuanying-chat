package local.pocketchat;

import org.json.*;
import java.util.*;

/** Bounded native pages over the existing globally ordered snapshot. */
final class DownloadPageWindow {
  static final int LIMIT=40;
  final JSONArray rows=new JSONArray();final int total,start;final String previous,next,first;final boolean newer;
  DownloadPageWindow(JSONArray ordered,int filter,String anchor){this(ordered,filter,anchor,"");}
  DownloadPageWindow(JSONArray ordered,int filter,String anchor,String viewed){
    List<JSONObject> selected=new ArrayList<>();int found=-1,kept=-1;
    for(int i=0;i<ordered.length();i++){JSONObject row=ordered.optJSONObject(i);if(row==null||!DownloadListPolicy.matches(row,filter))continue;String key=DownloadListPolicy.key(row);if(key.equals(anchor))found=selected.size();if(key.equals(viewed))kept=selected.size();selected.add(row);}
    int chosen=found<0?(kept<0?0:kept):found;if(kept>=0&&(kept<chosen||kept>=chosen+LIMIT))chosen=kept;
    total=selected.size();start=chosen;newer=start>0;first=total==0?"":DownloadListPolicy.key(selected.get(0));
    previous=start==0?"":DownloadListPolicy.key(selected.get(Math.max(0,start-LIMIT)));
    next=start+LIMIT>=total?"":DownloadListPolicy.key(selected.get(start+LIMIT));
    for(int i=start;i<Math.min(total,start+LIMIT);i++)rows.put(selected.get(i));
  }
}
