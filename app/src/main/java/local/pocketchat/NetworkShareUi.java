package local.pocketchat;

import android.app.Activity;import android.content.*;import android.net.Uri;import android.widget.*;
import org.json.*;import java.nio.charset.StandardCharsets;

/** Export only selected nodes. Core reparse binds extracted bytes to the chosen identity. */
final class NetworkShareUi {
  interface Load { NetworkShareCodec.Bundle run()throws Exception; }
  static void manual(Activity a,JSONObject row){prepare(a,()->new NetworkShareCodec.Bundle(row.optString("name"),null,NetworkShareCodec.manual(row)),"","");}
  static void node(Activity a,JSONObject source,String name){
    String role=source.optString("role"),key=NetworkSourceSelection.fingerprint(source,name);
    prepare(a,()->{NetworkCatalog fresh=new NetworkCatalog(a);JSONObject current=fresh.subscription(role,source.optString("id"));
      if(current==null||!key.equals(NetworkSourceSelection.fingerprint(current,name))||!source.optString("url").equals(current.optString("url")))throw NetworkShareCodec.invalid();
      JSONObject n=NetworkShareCodec.extract(fresh.cache(current),name,role);return new NetworkShareCodec.Bundle(n.optString("name"),NetworkCatalog.ENTRY.equals(role)?n:null,NetworkCatalog.EXIT.equals(role)?n:null);
    },NetworkCatalog.ENTRY.equals(role)?key:"",NetworkCatalog.EXIT.equals(role)?key:"");
  }
  static void nodeMenu(Activity a,JSONObject source,String name){ReferenceUi.Modal d=new ReferenceUi.Modal(a,NetworkWorkspaceUi.nodeName(name));String title=NetworkCatalog.EXIT.equals(source.optString("role"))?"分享出口":"分享入口";DesignUi.action(d.body,title,false,()->{d.dismiss();node(a,source,name);});d.buttons("关闭",d::dismiss,"",()->{});d.show();}
  static void route(Activity a,WindowNetworkState state){
    if(!state.internal){ReferenceUi.message(a,"分享整条线路","此环境未配置入口与固定出口。");return;}
    JSONObject config=NetworkCatalog.copy(state.config);String chosen=state.entry.isEmpty()?config.optString("entry"):state.entry;
    String expected=config.optString("entry").equals(chosen)?config.optString("entryNodeKey"):config.optJSONObject("entryPoolNodeKeys")==null?"":config.optJSONObject("entryPoolNodeKeys").optString(chosen);
    if(chosen.isEmpty()||expected.isEmpty()){ReferenceUi.message(a,"分享整条线路","请先为环境选择入口并保存，再分享当前线路。");return;}
    prepare(a,()->{
      SecretStore vault=new SecretStore(Profiles.context(a,state.slot));
      return NetworkSourceSelection.withActiveSnapshot(vault.context,()->{
        if(!NativeNetwork.transportFingerprint(config).equals(NativeNetwork.transportFingerprint(vault.settings())))throw new java.io.IOException("线路已变化，请重新打开分享。");
        JSONObject e=NetworkShareCodec.extract(vault.get("subscription"),chosen,NetworkCatalog.ENTRY),x;
        if(NativeNetwork.subscribedExit(config))x=NetworkShareCodec.extract(vault.get("exit-subscription"),config.optString("exitNodeName"),NetworkCatalog.EXIT);
        else x=NetworkShareCodec.manual(J.obj("name",config.optString("exitName",config.optString("exitHost")),"host",config.optString("exitHost"),"port",config.optInt("exitPort"),"user",config.optString("exitUser"),"password",config.optString("exitPassword")));
        return new NetworkShareCodec.Bundle(state.name+"线路",e,x);
      });
    },expected,NativeNetwork.subscribedExit(config)?config.optString("exitNodeKey"):"");
  }
  static void prepare(Activity a,Load load,String entryKey,String exitKey){
    ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"准备分享");wait.note("正在读取所选节点…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();
    NetworkWorkspaceUi.libraryWork(()->{try{NetworkShareCodec.Bundle b=load.run();NetworkShareCodec.decode(b.encode());a.runOnUiThread(()->{if(!a.isDestroyed()&&wait.isShowing())verify(a,wait,b,0,entryKey,exitKey);});}catch(Exception e){a.runOnUiThread(()->failure(a,wait));}});
  }
  static void verify(Activity a,ReferenceUi.Modal wait,NetworkShareCodec.Bundle b,int index,String entryKey,String exitKey){
    if(index==2){wait.dismiss();show(a,b);return;}JSONObject node=index==0?b.entry:b.exit;String expected=index==0?entryKey:exitKey;
    if(node==null){verify(a,wait,b,index+1,entryKey,exitKey);return;}
    NativeNetwork.previewSubscription(a,index==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,"",NetworkShareCodec.provider(node),(ok,msg,names,details,bytes)->{
      if(a.isDestroyed()||!wait.isShowing())return;
      if(!ok||details.length()!=1||!expected.isEmpty()&&!expected.equals(details.optJSONObject(0).optString("configFingerprint"))){failure(a,wait);return;}
      verify(a,wait,b,index+1,entryKey,exitKey);
    });
  }
  static void failure(Activity a,ReferenceUi.Modal wait){if(a.isDestroyed()||!wait.isShowing())return;wait.body.removeAllViews();wait.note("暂时无法分享所选节点。请确认节点仍有效；包含不支持的协议参数时不会省略参数分享。");wait.buttons("关闭",wait::dismiss,"",()->{});wait.resize();}
  static void show(Activity a,NetworkShareCodec.Bundle bundle){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"route".equals(bundle.kind)?"分享整条线路":"entry".equals(bundle.kind)?"分享入口":"分享出口");d.note(bundle.summary());d.note("包含连接账号和密码，不包含 ChatGPT 登录或聊天数据。");
    if("route".equals(bundle.kind)){d.note("分享当前线路中的一个入口和固定出口，接收方默认手动指定入口。");DesignUi.action(d.body,"仅分享入口",false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(bundle.entry.optString("name"),bundle.entry,null));});DesignUi.action(d.body,"仅分享出口",false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(bundle.exit.optString("name"),null,bundle.exit));});}
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);
    DesignUi.action(d.body,"复制配置",false,()->{try{((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("网络配置",bundle.encode()));d.dismiss();}catch(Exception e){error.setText("配置未复制，请重试。");d.resize();}});
    d.buttons("取消",d::dismiss,"分享文件",()->{d.primary().setEnabled(false);NetworkWorkspaceUi.libraryWork(()->{try{Uri uri=NetworkShareProvider.create(a,bundle.encode());a.runOnUiThread(()->{if(a.isDestroyed()||!d.isShowing())return;try{Intent send=new Intent(Intent.ACTION_SEND).setType(NetworkShareCodec.MIME).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);send.setClipData(ClipData.newUri(a.getContentResolver(),"网络配置",uri));a.startActivity(Intent.createChooser(send,"分享网络配置"));d.dismiss();}catch(Exception e){error.setText("没有可用的分享应用，可以复制配置发送。");d.primary().setEnabled(true);d.resize();}});}catch(Exception e){a.runOnUiThread(()->{if(!a.isDestroyed()&&d.isShowing()){error.setText("分享文件未生成，请重试。");d.primary().setEnabled(true);d.resize();}});}});});d.show();
  }
}
