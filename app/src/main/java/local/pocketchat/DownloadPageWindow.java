package local.pocketchat;

import org.json.*;
import java.util.*;

/** Bounded native pages over the existing globally ordered snapshot. */
final class DownloadPageWindow {
  static final int LIMIT=40;
  /** One selection/revision builds this index; page navigation only copies its forty-row window. */
  static final class Index {
    final List<JSONObject> selected=new ArrayList<>();final Map<String,Integer> positions=new HashMap<>();
    Index(JSONArray ordered,int filter){for(int i=0;i<ordered.length();i++){JSONObject row=ordered.optJSONObject(i);if(row==null||!DownloadListPolicy.matches(row,filter))continue;positions.put(DownloadListPolicy.key(row),selected.size());selected.add(row);}}
  }
  final JSONArray rows=new JSONArray();final int total,start;final String previous,next,first;final boolean newer;
  DownloadPageWindow(JSONArray ordered,int filter,String anchor){this(ordered,filter,anchor,"");}
  DownloadPageWindow(JSONArray ordered,int filter,String anchor,String viewed){this(new Index(ordered,filter),anchor,viewed);}
  DownloadPageWindow(Index index,String anchor,String viewed){
    List<JSONObject> selected=index.selected;int found=index.positions.getOrDefault(anchor,-1),kept=index.positions.getOrDefault(viewed,-1);
    int chosen=found<0?(kept<0?0:kept):found;if(kept>=0&&(kept<chosen||kept>=chosen+LIMIT))chosen=kept;
    total=selected.size();start=chosen;newer=start>0;first=total==0?"":DownloadListPolicy.key(selected.get(0));
    previous=start==0?"":DownloadListPolicy.key(selected.get(Math.max(0,start-LIMIT)));
    next=start+LIMIT>=total?"":DownloadListPolicy.key(selected.get(start+LIMIT));
    for(int i=start;i<Math.min(total,start+LIMIT);i++)rows.put(selected.get(i));
  }
}
