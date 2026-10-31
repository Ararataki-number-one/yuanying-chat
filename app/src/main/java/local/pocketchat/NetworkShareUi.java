package local.pocketchat;

import android.app.Activity;import android.content.*;import android.net.Uri;import android.widget.*;
import org.json.*;

/** Scope is selected before storage; a partial route remains a route until explicit narrowing. */
final class NetworkShareUi {
  interface Load { NetworkShareCodec.Bundle run()throws Exception; }
  interface RouteLoad { Prepared run()throws Exception; }
  static final String WARNING="配置包含代理连接凭据，请仅分享给信任的人。";
  static final class Prepared {
    final String name,scope;final JSONObject[] nodes=new JSONObject[2];final String[] keys={"",""};final boolean[] verified=new boolean[2];
    final NetworkSharePreparation.Failure[] problems=new NetworkSharePreparation.Failure[2];
    NetworkSharePreparation.Frozen frozen;
    Prepared(String name){this(name,"route");}
    Prepared(String name,String scope){this.name=name;this.scope=scope;}
    Prepared(NetworkShareCodec.Bundle b){this(b.name,b.kind);nodes[0]=b.entry;nodes[1]=b.exit;}
    boolean wants(int i){return "route".equals(scope)||(i==0?"entry":"exit").equals(scope);}
    boolean complete(){for(int i=0;i<2;i++)if(wants(i)&&(!verified[i]||nodes[i]==null))return false;return true;}
  }
  static String side(int i){return i==0?"入口":"出口";}
  static NetworkSharePreparation.Failure problem(String stage,String code,int i){return NetworkSharePreparation.fail(stage,code,i==0?"entry":"exit");}
  static String readFailure(int index,Exception error){return problem("SUBSCRIPTION_CACHE","UNREADABLE",index).shortReason();}
  static JSONObject selected(NetworkCatalog catalog,JSONObject source,byte[] bytes,String name,String role,String key)throws Exception {
    JSONObject cached=null;try{cached=catalog.shareCandidate(source,bytes,name,key);}catch(Exception optional){}
    return cached==null?NetworkShareCodec.extract(bytes,name,role):NetworkShareCodec.node(cached,NetworkCatalog.EXIT.equals(role));
  }
  static void manual(Activity a,JSONObject row){final JSONObject frozen;try{frozen=(JSONObject)NetworkShareJson.copy(row);}catch(Exception invalid){ReferenceUi.message(a,"分享出口",problem("PARAMETER_CHECK","UNSUPPORTED",1).shortReason());return;}
    prepare(a,()->{try{JSONObject n=NetworkShareCodec.manual(frozen);return new NetworkShareCodec.Bundle(n.getString("name"),null,n);}catch(Exception invalid){throw problem("PARAMETER_CHECK","UNSUPPORTED",1);}},"","");}
  static void node(Activity a,JSONObject source,String name){
    final JSONObject row;try{row=(JSONObject)NetworkShareJson.copy(source);}catch(Exception invalid){ReferenceUi.message(a,"分享节点","配置暂时无法读取。");return;}
    String role=row.optString("role"),key=NetworkSourceSelection.fingerprint(row,name);int i=NetworkCatalog.EXIT.equals(role)?1:0;
    prepare(a,()->{
      if(!key.matches("[0-9a-f]{64}")||row.optBoolean("stale")||row.optLong("cacheAddressRevision")!=row.optLong("addressRevision"))throw problem("CONFIG_READ","VERSION_CHANGED",i);
      // The selected UI row names immutable source generations. Opening the whole
      // catalogue here would decrypt the opposite role as well.
      SecretStore store=new SecretStore(Profiles.context(a,0));String slot=row.optString("cacheSlot");if(slot.isEmpty())slot=NetworkCatalog.cacheSlot(row.optString("cacheUrl",row.optString("url")));
      byte[] bytes;try{bytes=store.get(slot);}catch(Exception failed){throw problem("SUBSCRIPTION_CACHE","UNREADABLE",i);}if(bytes==null)throw problem("SUBSCRIPTION_CACHE","ABSENT",i);
      JSONObject n=null;String index=row.optString("shareCacheSlot");if(!index.isEmpty())try{n=NetworkShareSnapshot.select(store.get(index),bytes,name,key);}catch(Exception optional){}
      try{n=n==null?NetworkShareCodec.extract(bytes,name,role):NetworkShareCodec.node(n,i==1);}catch(Exception failed){throw problem("NODE_EXTRACT","UNSUPPORTED",i);}
      return new NetworkShareCodec.Bundle(n.optString("name"),i==0?n:null,i==1?n:null);
    },i==0?key:"",i==1?key:"");
  }
  static void nodeMenu(Activity a,JSONObject source,String name){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,NetworkWorkspaceUi.nodeName(name));String title=NetworkCatalog.EXIT.equals(source.optString("role"))?"分享出口":"分享入口";
    JSONObject detail=NetworkSourceSelection.byName(source,name);String available=detail==null?"":detail.optString("shareAvailability");
    if(available.equals("unsupported-format"))d.note("此来源可以连接，但暂不支持独立分享。分享支持 Clash / Mihomo YAML 单节点；URI 或 Base64 来源请使用提供方的单节点配置。");
    else {if(available.equals("unsupported-node"))d.note("将重新提取并检查所选节点；原线路不会改变。");else if(available.equals("budget")||available.equals("unavailable"))d.note("分享时会单独读取并核验所选节点。");DesignUi.action(d.body,title,false,()->{d.dismiss();node(a,source,name);});}
    d.buttons("关闭",d::dismiss,"",()->{});d.show();
  }
  static void route(Activity a,WindowNetworkState state){
    final EnvironmentSpec.Identity owner;try{owner=new EnvironmentSpec.Identity(state.slot,(int)state.environmentGeneration,state.environmentId);}catch(Exception invalid){ReferenceUi.message(a,"分享线路","环境已变化，请重新打开网络设置。");return;}
    ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"分享线路");wait.note("正在读取可选配置…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();
    NetworkWorkspaceUi.libraryWork(()->{JSONArray sources=NetworkShareSelection.describe(Profiles.context(a,owner.slot),owner);a.runOnUiThread(()->{if(a.isDestroyed()||!wait.isShowing())return;wait.dismiss();choose(a,state,owner,sources);});});
  }
  static void choose(Activity a,WindowNetworkState state,EnvironmentSpec.Identity owner,JSONArray sources){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"分享线路");d.note("先选择分享范围与配置来源。");final String[] scope={"route"};final int[] selected={0};
    String[] scopes={"入口","出口","整条线路"};RadioGroup ranges=new RadioGroup(a);for(int i=0;i<3;i++){RadioButton b=new RadioButton(a);b.setText(scopes[i]);b.setId(i+1);ranges.addView(b);}ranges.check(3);ranges.setOnCheckedChangeListener((g,id)->scope[0]=id==1?"entry":id==2?"exit":"route");d.body.addView(ranges);
    JSONArray usable=new JSONArray();JSONObject saved=null;for(int i=0;i<sources.length();i++){JSONObject s=sources.optJSONObject(i);if(s!=null&&"saved".equals(s.optString("source")))saved=s;}usable.put(saved==null?J.obj("source","saved","unavailable",true):saved);for(int i=0;i<sources.length();i++){JSONObject s=sources.optJSONObject(i);if(s!=null&&"running".equals(s.optString("source"))&&state.connected)usable.put(s);}
    if(usable.length()==0){d.note("已保存的配置暂时无法读取，请刷新网络设置后重试。");d.buttons("关闭",d::dismiss,"",()->{});d.show();return;}
    RadioGroup versions=new RadioGroup(a);for(int i=0;i<usable.length();i++){JSONObject s=usable.optJSONObject(i);RadioButton b=new RadioButton(a);b.setId(100+i);b.setText(("saved".equals(s.optString("source"))?"已保存的配置（默认）":"正在运行的配置")+(s.optBoolean("unavailable")?" · 暂不可读取":" · v"+s.optLong("savedRevision")));versions.addView(b);}versions.check(100);versions.setOnCheckedChangeListener((g,id)->{selected[0]=id-100;d.primary().setEnabled(!usable.optJSONObject(selected[0]).optBoolean("unavailable"));});d.body.addView(versions);
    if(usable.length()>1&&!usable.optJSONObject(0).optString("configurationFingerprint").equals(usable.optJSONObject(1).optString("configurationFingerprint")))d.note("已保存的配置与正在运行的配置不同；本次只导出所选来源的同一版本。");
    d.buttons("取消",d::dismiss,"准备分享",()->{JSONObject s=usable.optJSONObject(selected[0]);if(s==null||s.optBoolean("unavailable"))return;NetworkSharePreparation.Request request=new NetworkSharePreparation.Request(owner,s.optString("source"),scope[0],s.optString("version"),"");d.dismiss();chooseEntry(a,request);});d.show();d.primary().setEnabled(!usable.optJSONObject(0).optBoolean("unavailable"));
  }
  static void chooseEntry(Activity a,NetworkSharePreparation.Request request){
    if(!request.wants(0)){prepare(a,request);return;}
    ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"准备分享");wait.note("正在读取所选入口…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();
    NetworkWorkspaceUi.libraryWork(()->{try{JSONArray options=NetworkShareSelection.entryChoices(Profiles.context(a,request.owner.slot),request);a.runOnUiThread(()->{if(a.isDestroyed()||!wait.isShowing())return;wait.dismiss();if(options.length()<=1){prepare(a,options.length()==1?request.entry(options.optJSONObject(0).optString("name")):request);return;}
      String[] names=new String[options.length()];for(int i=0;i<names.length;i++)names[i]=NetworkWorkspaceUi.nodeName(options.optJSONObject(i).optString("name"));new android.app.AlertDialog.Builder(a).setTitle("选择本次分享的入口").setItems(names,(dialog,which)->prepare(a,request.entry(options.optJSONObject(which).optString("name")))).setNegativeButton("取消",null).show();});}
      catch(Exception failed){a.runOnUiThread(()->{if(a.isDestroyed()||!wait.isShowing())return;if("route".equals(request.scope)){wait.dismiss();prepare(a,request);}else failure(a,wait,NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","entry"));});}});
  }
  static void prepare(Activity a,NetworkSharePreparation.Request request){
    ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"准备分享");wait.note("正在读取所选配置…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();
    NetworkBridge.shareSnapshot(a,request,(frozen,failed)->{if(a.isDestroyed()||!wait.isShowing())return;if(failed!=null){failure(a,wait,failed);return;}
      Prepared p=new Prepared(frozen.name,request.scope);p.frozen=frozen;extract(a,wait,p,-1);
    });
  }
  static void extract(Activity a,ReferenceUi.Modal wait,Prepared p,int only){NetworkWorkspaceUi.libraryWork(()->{for(int i=0;i<2;i++)if(p.wants(i)&&(only<0||only==i)){
    NetworkSharePreparation.Part part=p.frozen.parts[i];p.nodes[i]=null;p.verified[i]=false;p.problems[i]=part==null?problem("CONFIG_READ","ABSENT",i):part.failure;if(p.problems[i]!=null)continue;
    try{if(part.selection.optJSONObject("manual")!=null)p.nodes[i]=NetworkShareCodec.manual(part.selection.getJSONObject("manual"));else p.nodes[i]=NetworkShareCodec.extract(part.bytes,part.selection.getString("name"),i==0?"entry":"exit");p.keys[i]=part.selection.optString("key");}
    catch(Exception invalid){p.problems[i]=problem(part.selection.optJSONObject("manual")!=null?"PARAMETER_CHECK":"NODE_EXTRACT","UNSUPPORTED",i);}
    }a.runOnUiThread(()->verifyPrepared(a,wait,p,0,p.keys[0],p.keys[1]));});}
  static void prepare(Activity a,Load load,String entryKey,String exitKey){prepareRoute(a,()->new Prepared(load.run()),entryKey,exitKey);}
  static void prepareRoute(Activity a,RouteLoad load,String entryKey,String exitKey){
    ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"准备分享");wait.note("正在读取所选节点…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();
    NetworkWorkspaceUi.libraryWork(()->{try{Prepared p=load.run();a.runOnUiThread(()->{if(!a.isDestroyed()&&wait.isShowing())verifyPrepared(a,wait,p,0,entryKey,exitKey);});}catch(Exception error){a.runOnUiThread(()->failure(a,wait,error instanceof NetworkSharePreparation.Failure?(NetworkSharePreparation.Failure)error:NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","")));}});
  }
  static void verify(Activity a,ReferenceUi.Modal wait,NetworkShareCodec.Bundle b,int index,String entryKey,String exitKey){verifyPrepared(a,wait,new Prepared(b),index,entryKey,exitKey);}
  static boolean alive(Activity a,Prepared p){if(a.isDestroyed())return false;try{return p.frozen==null||ProfileCatalog.get(a).identity(p.frozen.request.owner.slot).equals(p.frozen.request.owner);}catch(Exception changed){return false;}}
  static void verifyPrepared(Activity a,ReferenceUi.Modal wait,Prepared p,int index,String entryKey,String exitKey){
    if(!alive(a,p)||!wait.isShowing())return;
    if(index==2){wait.dismiss();show(a,p);return;}
    JSONObject node=p.nodes[index];String expected=index==0?entryKey:exitKey;p.keys[index]=expected;if(!p.wants(index)||node==null||p.verified[index]){verifyPrepared(a,wait,p,index+1,entryKey,exitKey);return;}
    byte[] provider;try{node=NetworkShareCodec.node(node,index==1);p.nodes[index]=node;provider=NetworkShareCodec.provider(node);}catch(Exception invalid){p.nodes[index]=null;p.problems[index]=problem("PARAMETER_CHECK","UNSUPPORTED",index);verifyPrepared(a,wait,p,index+1,entryKey,exitKey);return;}
    NativeNetwork.previewSubscription(a,index==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,"",provider,(ok,msg,names,details,bytes)->{
      if(!alive(a,p)||!wait.isShowing())return;JSONObject detail=details==null?null:details.optJSONObject(0);
      if(!ok||names==null||names.length()!=1||details==null||details.length()!=1||detail==null||detail.optInt("configFingerprintVersion")!=1){p.nodes[index]=null;p.problems[index]=problem("PARAMETER_CHECK","NATIVE_REJECTED",index);}
      else if(!expected.isEmpty()&&!expected.equals(detail.optString("configFingerprint"))){p.nodes[index]=null;p.problems[index]=problem("PARAMETER_CHECK","IDENTITY_MISMATCH",index);}
      else{p.verified[index]=true;p.problems[index]=null;}
      verifyPrepared(a,wait,p,index+1,entryKey,exitKey);
    });
  }
  static void failure(Activity a,ReferenceUi.Modal wait,String ignored){failure(a,wait,NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE",""));}
  static void failure(Activity a,ReferenceUi.Modal wait,NetworkSharePreparation.Failure f){if(a.isDestroyed()||!wait.isShowing())return;wait.body.removeAllViews();wait.note(f.shortReason());DesignUi.action(wait.body,"查看原因",false,()->ReferenceUi.message(a,"分享原因",f.diagnostic()));wait.buttons("关闭",wait::dismiss,"",()->{});wait.resize();}
  static void show(Activity a,Prepared p){
    if(!alive(a,p))return;if(p.complete()){NetworkShareCodec.Bundle bundle=new NetworkShareCodec.Bundle(p.name,p.nodes[0],p.nodes[1]);show(a,bundle,"",p);return;}
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,title(p.scope));if("route".equals(p.scope))d.note("整条线路暂未生成。");for(int i=0;i<2;i++)if(p.wants(i)){final int side=i;NetworkSharePreparation.Failure f=p.problems[i];if(p.verified[i]&&p.nodes[i]!=null){d.note(NetworkShareUi.side(i)+"配置已准备好。");DesignUi.action(d.body,"仅分享"+NetworkShareUi.side(i),false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(p.name,side==0?p.nodes[0]:null,side==1?p.nodes[1]:null),"",p);});}
      else{d.note(f==null?NetworkShareUi.side(i)+"暂时无法导出。":f.shortReason());if(f!=null)DesignUi.action(d.body,"查看"+NetworkShareUi.side(i)+"原因",false,()->ReferenceUi.message(a,"分享原因",f.diagnostic()));if(p.frozen!=null)DesignUi.action(d.body,"重试"+NetworkShareUi.side(i),false,()->{d.dismiss();retry(a,p,side);});}}
    d.buttons("关闭",d::dismiss,"",()->{});d.show();
  }
  static void retry(Activity a,Prepared p,int side){if(side==0&&p.frozen.request.entry.isEmpty()){chooseEntry(a,p.frozen.request);return;}ReferenceUi.Modal wait=new ReferenceUi.Modal(a,"准备分享");wait.note("正在重试"+NetworkShareUi.side(side)+"…");wait.buttons("取消",wait::dismiss,"",()->{});wait.show();NetworkWorkspaceUi.libraryWork(()->{try{
      Context profile=Profiles.context(a,p.frozen.request.owner.slot);if(!NetworkShareSelection.current(profile,p.frozen.request))throw problem("CONFIG_READ","VERSION_CHANGED",side);NetworkSharePreparation.Part old=p.frozen.parts[side];if(old==null||old.failure!=null)p.frozen.parts[side]=NetworkShareSelection.retryPart(profile,p.frozen.request,side);a.runOnUiThread(()->{if(alive(a,p)&&wait.isShowing())extract(a,wait,p,side);});
    }catch(Exception changed){a.runOnUiThread(()->{if(alive(a,p)&&wait.isShowing()){p.problems[side]=problem("CONFIG_READ","VERSION_CHANGED",side);wait.dismiss();show(a,p);}});}});}
  static String title(String scope){return "route".equals(scope)?"分享整条线路":"entry".equals(scope)?"分享入口":"分享出口";}
  static void show(Activity a,NetworkShareCodec.Bundle bundle){show(a,bundle,"");}
  static void show(Activity a,NetworkShareCodec.Bundle bundle,String unavailable){show(a,bundle,unavailable,null);}
  static void show(Activity a,NetworkShareCodec.Bundle bundle,String unavailable,Prepared owner){
    NetworkWorkspaceUi.libraryWork(()->{try{String encoded=bundle.encode();a.runOnUiThread(()->export(a,bundle,encoded,owner));}catch(Exception invalid){a.runOnUiThread(()->ReferenceUi.message(a,title(bundle.kind),NetworkSharePreparation.fail("PARAMETER_CHECK","UNSUPPORTED","").shortReason()));}});
  }
  static void export(Activity a,NetworkShareCodec.Bundle bundle,String encoded,Prepared owner){
    if(a.isDestroyed()||owner!=null&&!alive(a,owner))return;ReferenceUi.Modal d=new ReferenceUi.Modal(a,title(bundle.kind));d.note(bundle.summary());d.note(WARNING);
    if(owner!=null&&owner.frozen!=null)d.note(("saved".equals(owner.frozen.request.source)?"已保存的配置":"正在运行的配置")+" · 本次选定快照");if(bundle.schemaVersion()>1)d.note("此配置需使用 2.0.17 或更新版本导入，以完整保留节点参数。");
    if("route".equals(bundle.kind)){DesignUi.action(d.body,"仅分享入口",false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(bundle.name,bundle.entry,null),"",owner);});DesignUi.action(d.body,"仅分享出口",false,()->{d.dismiss();show(a,new NetworkShareCodec.Bundle(bundle.name,null,bundle.exit),"",owner);});}
    TextView error=ReferenceUi.text(a,"",12,ReferenceUi.RED,false);d.body.addView(error);final NetworkSharePreparation.Failure[] latest={null};DesignUi.action(d.body,"查看原因",false,()->{if(latest[0]!=null)ReferenceUi.message(a,"分享原因",latest[0].diagnostic());});
    DesignUi.action(d.body,"复制配置",false,()->{if(owner!=null&&!alive(a,owner)){error.setText("环境已变化，请重新打开分享。");return;}try{((ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("网络配置",encoded));d.dismiss();}catch(Exception failed){latest[0]=NetworkSharePreparation.fail("CLIPBOARD","UNREADABLE","");error.setText(latest[0].shortReason());d.resize();}});
    d.buttons("取消",d::dismiss,"分享文件",()->{if(owner!=null&&!alive(a,owner)){error.setText("环境已变化，请重新打开分享。");return;}d.primary().setEnabled(false);NetworkWorkspaceUi.libraryWork(()->{try{Uri uri=NetworkShareProvider.create(a,encoded);a.runOnUiThread(()->{if(a.isDestroyed()||!d.isShowing()||owner!=null&&!alive(a,owner))return;try{Intent send=new Intent(Intent.ACTION_SEND).setType(NetworkShareCodec.MIME).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);send.setClipData(ClipData.newUri(a.getContentResolver(),"网络配置",uri));a.startActivity(Intent.createChooser(send,"分享网络配置"));d.dismiss();}catch(Exception failed){latest[0]=NetworkSharePreparation.fail("SYSTEM_SHARE","NO_TARGET","");error.setText(latest[0].shortReason());d.primary().setEnabled(true);d.resize();}});}catch(Exception failed){a.runOnUiThread(()->{if(!a.isDestroyed()&&d.isShowing()){latest[0]=NetworkSharePreparation.fail("FILE_GENERATE","FILE_IO","");error.setText(latest[0].shortReason());d.primary().setEnabled(true);d.resize();}});}});});d.show();
  }
}
