package local.pocketchat;

import org.json.JSONObject;
import java.util.Map;

/** A slot is a location, not proof that a historical file belongs to its new owner. */
final class DownloadOwnerLabels {
  static final String UNKNOWN="归属待确认";
  static final class Owner {
    final int slot,generation;final String id,name;final boolean created,deleting,resetting;
    Owner(int slot,String name,String id,int generation,boolean created,boolean deleting,boolean resetting){this.slot=slot;this.name=name;this.id=id;this.generation=generation;this.created=created;this.deleting=deleting;this.resetting=resetting;}
  }
  static String label(JSONObject row,Map<Integer,Owner> owners){
    String id=row.optString("environmentId");Object generation=row.opt("environmentGeneration");
    if(id.isEmpty()||!(generation instanceof Integer||generation instanceof Long)||((Number)generation).longValue()<0)return UNKNOWN;
    Owner current=owners.get(row.optInt("slot"));if(current==null||!current.created)return "原环境（已删除）";
    if(!id.equals(current.id)||((Number)generation).longValue()!=current.generation||current.resetting)return "原环境（已重建）";
    if(current.deleting)return "原环境（正在删除）";
    return current.name==null?(current.slot==0?"默认环境":"环境 "+(current.slot+1)):current.name;
  }
}
