package local.pocketchat;

import java.util.*;
import org.json.*;

/** Pending browser selections. Unknown evidence is distinct from observed upload work. */
final class ResourceUploadState {
  static final class Batch {
    final String id=UUID.randomUUID().toString();String document;final long selectedAt;final List<String> names;
    long sequence;int stable;boolean uploading,unknown=true;
    Batch(List<String> names,String document,long selectedAt){this.names=new ArrayList<>(names);this.document=document;this.selectedAt=selectedAt;}
  }
  final LinkedHashMap<String,Batch> batches=new LinkedHashMap<>();
  long epoch=-1;
  void add(List<String> names,String document,long currentEpoch,long now){
    if(epoch!=currentEpoch){batches.clear();epoch=currentEpoch;}
    if(names.isEmpty())return;Batch batch=new Batch(names,document,now);batches.put(batch.id,batch);
  }
  boolean active(long currentEpoch){return epoch==currentEpoch&&!batches.isEmpty();}
  boolean uploading(long currentEpoch){if(epoch!=currentEpoch)return false;for(Batch batch:batches.values())if(batch.uploading)return true;return false;}
  boolean unknown(long currentEpoch){if(epoch!=currentEpoch)return false;for(Batch batch:batches.values())if(batch.unknown)return true;return false;}
  JSONArray names(){LinkedHashSet<String> names=new LinkedHashSet<>();for(Batch batch:batches.values())names.addAll(batch.names);return new JSONArray(names);}
  JSONArray snapshot(){JSONArray out=new JSONArray();for(Batch batch:batches.values())out.put(J.obj("batchId",batch.id,"documentId",batch.document,"selectedAt",batch.selectedAt,"names",new JSONArray(batch.names)));return out;}
  int stable(){int value=Integer.MAX_VALUE;for(Batch batch:batches.values())value=Math.min(value,batch.stable);return value==Integer.MAX_VALUE?0:value;}
  boolean observe(JSONObject observation,String currentDocument,long currentEpoch){
    if(epoch!=currentEpoch||currentDocument.isEmpty()||!currentDocument.equals(observation.optString("documentId"))||!observation.optBoolean("ok"))return false;
    JSONArray observed=observation.optJSONArray("batches");if(observed==null)return false;
    // Two terminal samples must come from separate observations. A duplicated
    // row must not consume both confirmations in a single malformed response.
    Set<String> observedIds=new HashSet<>();for(int i=0;i<observed.length();i++){JSONObject row=observed.optJSONObject(i);if(row==null||!observedIds.add(row.optString("batchId")))return false;}
    boolean removed=false;
    for(int i=0;i<observed.length();i++){
      JSONObject row=observed.optJSONObject(i);if(row==null)continue;Batch batch=batches.get(row.optString("batchId"));
      if(batch==null||!batch.document.isEmpty()&&!batch.document.equals(currentDocument)||row.optLong("sequence")<=batch.sequence)continue;
      JSONArray files=row.optJSONArray("files");if(files==null||files.length()!=batch.names.size())continue;
      boolean terminal=true,uploading=false,unknown=false,valid=true;
      for(int j=0;j<files.length();j++){
        JSONObject file=files.optJSONObject(j);if(file==null||!batch.names.get(j).equals(file.optString("name"))){valid=false;break;}
        String state=file.optString("state");uploading|="uploading".equals(state);
        boolean ended=Arrays.asList("ready","error","sent","removed").contains(state);terminal&=ended;unknown|=!ended&&!"uploading".equals(state);
      }
      if(!valid)continue;if(batch.document.isEmpty())batch.document=currentDocument;batch.sequence=row.optLong("sequence");batch.uploading=uploading;batch.unknown=unknown;batch.stable=terminal?batch.stable+1:0;
      if(batch.stable>=2){batches.remove(batch.id);removed=true;}
    }
    return removed;
  }
}
