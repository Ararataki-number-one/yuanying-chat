package local.pocketchat;

import android.app.Activity;import android.content.*;import android.net.Uri;import android.widget.*;
import org.json.*;import java.nio.charset.StandardCharsets;

/** Export only selected nodes. Core reparse binds extracted bytes to the chosen identity. */
final class NetworkShareUi {
  interface Load { NetworkShareCodec.Bundle run()throws Exception; }
  interface RouteLoad { Prepared run()throws Exception; }
  static final class Prepared {
    final String name;final JSONObject[] nodes=new JSONObject[2];final String[] errors={"",""};
    Prepared(String name){this.name=name;}
    Prepared(NetworkShareCodec.Bundle bundle){name=bundle.name;nodes[0]=bundle.entry;nodes[1]=bundle.exit;}
  }
  static String side(int index){return index==0?"入口":"出口";}
  static String readFailure(int index,Exception error){return side(index)+"读取阶段："+NetworkShareCodec.explanation(error);}
  static JSONObject selected(NetworkCatalog catalog,JSONObject source,byte[] bytes,String name,String role,String key)throws Exception {
    JSONObject cached=null;try{cached=catalog.shareCandidate(source,bytes,name,key);}catch(Exception unavailable){/* A corrupt optional index falls back to the immutable source. */}
    return cached==null?NetworkShareCodec.extract(bytes,name,role):NetworkShareCodec.node(cached,NetworkCatalog.EXIT.equals(role));
  }
  static void manual(Activity a,JSONObject row){prepare(a,()->{JSONObject exit=NetworkShareCodec.manual(row);return new NetworkShareCodec.Bundle(exit.getString("name"),null,exit);},"","");}
  static void node(Activity a,JSONObject source,String name){
    String role=source.optString("role"),key=NetworkSourceSelection.fingerprint(source,name);
    prepare(a,()->{NetworkCatalog fresh=new NetworkCatalog(a);JSONObject current=fresh.subscription(role,source.optString("id"));
      if(!key.matches("[0-9a-f]{64}")||current==null||!key.equals(NetworkSourceSelection.fingerprint(current,name))||!source.optString("url").equals(current.optString("url")))throw NetworkShareCodec.failure("所选节点已变化，请重新打开分享。");
      JSONObject n=selected(fresh,current,fresh.cache(current),name,role,key);return new NetworkShareCodec.Bundle(n.optString("name"),NetworkCatalog.ENTRY.equals(role)?n:null,NetworkCatalog.EXIT.equals(role)?n:null);
    },NetworkCatalog.ENTRY.equals(role)?key:"",NetworkCatalog.EXIT.equals(role)?key:"");
  }
  static void nodeMenu(Activity a,JSONObject source,String name){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,NetworkWorkspaceUi.nodeName(name));String title=NetworkCatalog.EXIT.equals(source.optString("role"))?"分享出口":"分享入口";
    JSONObject detail=NetworkSourceSelection.byName(source,name);String available=detail==null?"":detail.optString("shareAvailability");
    if(available.equals("unsupported-format"))d.note("此来源可以连接，但暂不支持独立分享。分享支持 Clash / Mihomo YAML 单节点；URI 或 Base64 来源请使用提供方的单节点配置。");
    else if(available.equals("unsupported-node"))d.note("此节点暂未生成可独立分享的配置。请更新订阅，或使用提供方的单节点配置；原线路可继续使用。");
    else {if(available.equals("budget")||available.equals("unavailable"))d.note("此节点尚无分享缓存，分享时会单独读取并核验所选节点。");if(available.isEmpty())d.note("分享支持 Clash / Mihomo YAML 单节点；URI 或 Base64 来源暂不支持。更新订阅后可提前检查分享范围。");DesignUi.action(d.body,title,false,()->{d.dismiss();node(a,source,name);});}
    d.buttons("关闭",d::dismiss,"",()->{});d.show();
  }
  static void route(Activity a,WindowNetworkState state){
    if(!state.internal){ReferenceUi.message(a,"分享整条线路","此环境未配置入口与固定出口。");return;}
    JSONObject config=NetworkCatalog.copy(state.config);String chosen=state.entry.isEmpty()?config.optString("entry"):state.entry;
    String expected=config.optString("entry").equals(chosen)?config.optString("entryNodeKey"):config.optJSONObject("entryPoolNodeKeys")==null?"":config.optJSONObject("entryPoolNodeKeys").optString(chosen);
    prepareRoute(a,()->{
      SecretStore vault=new SecretStore(Profiles.context(a,state.slot));
      Prepared ready=new Prepared(state.name+"线路");final byte[][] captured=new byte[2][];
      // Existing writers take Catalog -> active snapshot. Capture only here, then
      // release the snapshot lease before any catalogue/index lookup.
      NetworkSourceSelection.withActiveSnapshot(vault.context,()->{
        if(!NativeNetwork.transportFingerprint(config).equals(NativeNetwork.transportFingerprint(vault.settings())))throw NetworkShareCodec.failure("线路已变化，请重新打开分享。");
        try{byte[] bytes=vault.get("subscription");captured[0]=bytes==null?null:bytes.clone();}catch(Exception error){ready.errors[0]=readFailure(0,error);}
        if(NativeNetwork.subscribedExit(config))try{byte[] bytes=vault.get("exit-subscription");captured[1]=bytes==null?null:bytes.clone();}catch(Exception error){ready.errors[1]=readFailure(1,error);}
        return null;
      });
      NetworkCatalog catalog=new NetworkCatalog(a);
      if(ready.errors[0].isEmpty())try{if(chosen.isEmpty()||expected.isEmpty())throw NetworkShareCodec.failure("请先选择入口并保存。");JSONObject source=catalog.subscription(NetworkCatalog.ENTRY,config.optString("entrySubscriptionId"));ready.nodes[0]=selected(catalog,source,captured[0],chosen,NetworkCatalog.ENTRY,expected);}catch(Exception error){ready.errors[0]=readFailure(0,error);}
      if(ready.errors[1].isEmpty())try{if(NativeNetwork.subscribedExit(config)){JSONObject source=catalog.subscription(NetworkCatalog.EXIT,config.optString("exitSubscriptionId"));ready.nodes[1]=selected(catalog,source,captured[1],config.optString("exitNodeName"),NetworkCatalog.EXIT,config.optString("exitNodeKey"));}
        else ready.nodes[1]=NetworkShareCodec.manual(J.obj("name",config.optString("exitName",config.optString("exitHost")),"host",config.optString("exitHost"),"port",config.optInt("exitPort"),"user",config.optString("exitUser"),"password",config.optString("exitPassword")));}catch(Exception error){ready.errors[1]=readFailure(1,error);}
      return ready;
    },expected,NativeNetwork.subscribedExit(config)?config.optString("exitNodeKey"):"");
  }
  static void prepare(Activity a,Load load,String entryKey,String exitKey){prepareRoute(a,()->new Prepared(load.run()),entryKey,exitKey);}
  static void prepareRoute(Activity a,RouteLoad load,String entryKey,String exitKey){
    ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"准备分享");wait.note("正在读取所选节点…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();
    NetworkWorkspaceUi.libraryWork(()->{try{Prepared ready=load.run();a.runOnUiThread(()->{if(!a.isDestroyed()&&wait.isShowing())verifyPrepared(a,wait,ready,0,entryKey,exitKey);});}catch(Exception error){a.runOnUiThread(()->failure(a,wait,"读取阶段："+NetworkShareCodec.explanation(error)));}});
  }
  static void verify(Activity a,ReferenceUi.Modal wait,NetworkShareCodec.Bundle b,int index,String entryKey,String exitKey){verifyPrepared(a,wait,new Prepared(b),index,entryKey,exitKey);}
  static void verifyPrepared(Activity a,ReferenceUi.Modal wait,Prepared prepared,int index,String entryKey,String exitKey){
    if(a.isDestroyed()||!wait.isShowing())return;
    if(index==2){String note=prepared.errors[0]+(prepared.errors[0].isEmpty()||prepared.errors[1].isEmpty()?"":"\n")+prepared.errors[1];
      if(prepared.nodes[0]==null&&prepared.nodes[1]==null){failure(a,wait,note.isEmpty()?"没有可分享的节点，请更新订阅后重试。":note);return;}
      wait.dismiss();show(a,new NetworkShareCodec.Bundle(prepared.name,prepared.nodes[0],prepared.nodes[1]),note);return;}
    JSONObject node=prepared.nodes[index];String expected=index==0?entryKey:exitKey;if(node==null){verifyPrepared(a,wait,prepared,index+1,entryKey,exitKey);return;}
    byte[] provider;try{node=NetworkShareCodec.node(node,index==1);prepared.nodes[index]=node;provider=NetworkShareCodec.provider(node);}catch(Exception invalid){prepared.nodes[index]=null;prepared.errors[index]=side(index)+"参数检查阶段："+NetworkShareCodec.explanation(invalid);verifyPrepared(a,wait,prepared,index+1,entryKey,exitKey);return;}
    NativeNetwork.previewSubscription(a,index==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,"",provider,(ok,msg,names,details,bytes)->{
      if(a.isDestroyed()||!wait.isShowing())return;
      if(!ok||details.length()!=1||details.optJSONObject(0)==null){prepared.nodes[index]=null;prepared.errors[index]=side(index)+"内核解析阶段：配置未通过内核检查，请确认参数完整后重试；原线路未改变。";}
      else if(!expected.isEmpty()&&!expected.equals(details.optJSONObject(0).optString("configFingerprint"))){prepared.nodes[index]=null;prepared.errors[index]=side(index)+"身份核对阶段：参数与当前线路不一致，请更新订阅并重新选择；原线路未改变。";}
      verifyPrepared(a,wait,prepared,index+1,entryKey,exitKey);
    });
  }
  static void failure(Activity a,ReferenceUi.Modal wait,String message){if(a.isDestroyed()||!wait.isShowing())return;wait.body.removeAllViews();wait.note(message);wait.buttons("关闭",wait::dismiss,"",()->{});wait.resize();}
  static void show(Activity a,NetworkShareCodec.Bundle bundle){show(a,bundle,"");}
  static void show(Activity a,NetworkShareCodec.Bundle bundle,String unavailable){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"route".equals(bundle.kind)?"分享整条线路":"entry".equals(bundle.kind)?"分享入口":"分享出口");d.note(bundle.summary());if(!unavailable.isEmpty()){d.note(unavailable);d.note("已单独核验可用的一端，可继续分享；整条线路未生成。");}d.note("包含连接账号和密码，不包含 ChatGPT 登录或聊天数据。");
    if("route".equals(bundle.kind)){d.note("分享当前线路中的一个入口和固定出口，接收方默认手动指定入口。");DesignUi.action(d.body,"仅分享入口",false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(bundle.entry.optString("name"),bundle.entry,null));});DesignUi.action(d.body,"仅分享出口",false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(bundle.exit.optString("name"),null,bundle.exit));});}
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);
    DesignUi.action(d.body,"复制配置",false,()->{try{((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("网络配置",bundle.encode()));d.dismiss();}catch(Exception e){error.setText("配置未复制，请重试。");d.resize();}});
    d.buttons("取消",d::dismiss,"分享文件",()->{d.primary().setEnabled(false);NetworkWorkspaceUi.libraryWork(()->{try{Uri uri=NetworkShareProvider.create(a,bundle.encode());a.runOnUiThread(()->{if(a.isDestroyed()||!d.isShowing())return;try{Intent send=new Intent(Intent.ACTION_SEND).setType(NetworkShareCodec.MIME).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);send.setClipData(ClipData.newUri(a.getContentResolver(),"网络配置",uri));a.startActivity(Intent.createChooser(send,"分享网络配置"));d.dismiss();}catch(Exception e){error.setText("没有可用的分享应用，可以复制配置发送。");d.primary().setEnabled(true);d.resize();}});}catch(Exception e){a.runOnUiThread(()->{if(!a.isDestroyed()&&d.isShowing()){error.setText("分享文件未生成，请重试。");d.primary().setEnabled(true);d.resize();}});}});});d.show();
  }
}
