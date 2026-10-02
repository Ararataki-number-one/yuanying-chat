package local.pocketchat;
import org.json.*;import java.util.*;import java.io.IOException;

/** Selection constraints around the existing route chooser, parser and fixed-exit chain. */
final class EntrySelection {
  static List<String> strings(JSONArray values){List<String> out=new ArrayList<>();if(values!=null)for(int i=0;i<values.length();i++){String name=values.optString(i);if(name.startsWith("Entry|")&&!out.contains(name))out.add(name);}return out;}
  static List<String> allowed(JSONObject config,List<String> nodes){
    String mode=config.optString("entryMode");if(mode.isEmpty())return new ArrayList<>(nodes);
    List<String> choices="manual".equals(mode)?Collections.singletonList(config.optString("entry")):strings(config.optJSONArray("entryPool"));
    List<String> out=new ArrayList<>();for(String node:nodes)if(choices.contains(node))out.add(node);
    String chosen=config.optString("entry");if(out.remove(chosen))out.add(0,chosen);return out;
  }
  static void validate(JSONObject config,List<String> nodes)throws IOException{
    String mode=config.optString("entryMode");if(mode.isEmpty())return;
    if(!"manual".equals(mode)&&!"random".equals(mode))throw new IOException("请选择入口方式");
    String chosen=config.optString("entry");if(!nodes.contains(chosen))throw new IOException("当前入口不属于所选订阅，请重新选择");
    if("random".equals(mode)){List<String> pool=strings(config.optJSONArray("entryPool"));if(pool.isEmpty())throw new IOException("请至少勾选一个随机入口");if(!nodes.containsAll(pool))throw new IOException("随机池包含其他订阅的入口，请重新选择");if(!pool.contains(chosen))throw new IOException("当前入口不在勾选的随机池中");}
  }
  static String random(Collection<String> pool,Random random){if(pool.isEmpty())return "";return new ArrayList<>(pool).get(random.nextInt(pool.size()));}
  static String filter(List<String> names){StringBuilder value=new StringBuilder("^(?:");for(String name:names){if(value.length()>4)value.append('|');value.append(NativeNetwork.literalRegex(name));}return value.append(")$").toString();}
}
