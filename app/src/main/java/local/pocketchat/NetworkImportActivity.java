package local.pocketchat;

import android.app.*;import android.content.*;import android.net.Uri;import android.os.Bundle;import android.view.*;import android.widget.*;
import org.json.*;import java.io.*;import java.nio.charset.StandardCharsets;

/** Preview first. Import mutates only the network library; application remains explicit. */
public final class NetworkImportActivity extends ThemedActivity {
  static final int PICK=780;
  FrameLayout host;NetworkWorkspaceUi workspace;ReferenceUi.Modal current;
  @Override public void onCreate(Bundle state){super.onCreate(state);if(android.os.Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);DesignUi.chrome(this);LinearLayout root=DesignUi.column(this);root.setBackgroundColor(ReferenceUi.BG);ReferenceUi.insets(this,root,null);LinearLayout heading=DesignUi.row(this);heading.setPadding(DesignUi.dp(this,8),DesignUi.dp(this,8),DesignUi.dp(this,16),DesignUi.dp(this,8));heading.addView(ReferenceUi.iconButton(this,"back","返回",this::finish),new LinearLayout.LayoutParams(DesignUi.dp(this,48),DesignUi.dp(this,48)));heading.addView(ReferenceUi.text(this,"导入网络",20,DesignUi.TEXT,true),new LinearLayout.LayoutParams(0,-2,1));root.addView(heading);host=new FrameLayout(this);root.addView(host,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);workspace=new NetworkWorkspaceUi(this,host);
    Intent intent=getIntent();Uri uri=null;if(Intent.ACTION_VIEW.equals(intent.getAction()))uri=intent.getData();else if(Intent.ACTION_SEND.equals(intent.getAction())){try{uri=intent.getParcelableExtra(Intent.EXTRA_STREAM);}catch(Exception ignored){}}
    if(uri!=null)read(uri);else if(Intent.ACTION_SEND.equals(intent.getAction())&&intent.hasExtra(Intent.EXTRA_TEXT)){CharSequence text=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);parse(text==null?"":text.toString());}else menu();
  }
  @Override protected void onDestroy(){if(workspace!=null)workspace.close();super.onDestroy();}
  void menu(){ReferenceUi.Modal d=new ReferenceUi.Modal(this,"导入网络");current=d;d.cancel=this::finish;d.note("打开 .pocketnet 文件，或粘贴别人分享的配置。预览前不会改变当前网络。");
    DesignUi.action(d.body,"选择分享文件",false,()->{try{Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");startActivityForResult(intent,PICK);}catch(ActivityNotFoundException e){d.note("此设备没有文件选择器，请粘贴配置导入。");d.resize();}});
    DesignUi.action(d.body,"粘贴配置",false,()->{d.dismiss();paste();});d.buttons("取消",this::finish,"",()->{});d.show();
  }
  void paste(){ReferenceUi.Modal d=new ReferenceUi.Modal(this,"粘贴网络配置");current=d;EditText input=DesignUi.input(d.body,"分享配置","","粘贴收到的配置");input.setSingleLine(false);input.setMaxLines(6);input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(NetworkShareCodec.LIMIT)});d.buttons("取消",()->{d.dismiss();menu();},"预览",()->{String text=input.getText().toString();d.dismiss();parse(text);});d.show();}
  @Override protected void onActivityResult(int req,int result,Intent data){super.onActivityResult(req,result,data);if(req==PICK&&result==RESULT_OK&&data!=null&&data.getData()!=null){if(current!=null)current.dismiss();read(data.getData());}}
  void read(Uri uri){loading();NetworkWorkspaceUi.libraryWork(()->{try{
    if(!"content".equals(uri.getScheme())||uri.getAuthority()==null||uri.getAuthority().startsWith(getPackageName()+".")&&!uri.getAuthority().equals(getPackageName()+".network-shares"))throw NetworkShareCodec.invalid();
    String text;try(InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw NetworkShareCodec.invalid();byte[] bytes=J.read(in,NetworkShareCodec.LIMIT);text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)).toString();}
    parseWorker(text);
  }catch(Exception e){runOnUiThread(this::invalid);}});}
  void loading(){if(current!=null)current.dismiss();current=new ReferenceUi.Modal(this,"读取分享配置");current.cancel=this::finish;current.note("正在读取…");current.buttons("取消",this::finish,"",()->{});current.show();}
  void parse(String text){loading();NetworkWorkspaceUi.libraryWork(()->parseWorker(text));}
  void parseWorker(String text){try{NetworkShareCodec.Bundle bundle=NetworkShareCodec.decode(text);runOnUiThread(()->{if(!isFinishing()&&!isDestroyed()){current.dismiss();preview(bundle);}});}catch(Exception e){runOnUiThread(this::invalid);}}
  void invalid(){if(isFinishing()||isDestroyed())return;if(current!=null)current.dismiss();ReferenceUi.Modal d=new ReferenceUi.Modal(this,"无法导入");current=d;d.cancel=this::finish;d.note("文件不可读取、配置不完整或版本不支持。请重新选择 .pocketnet 分享文件，或让发送方重新分享。");d.buttons("关闭",this::finish,"重新选择",()->{d.dismiss();menu();});d.show();}
  void preview(NetworkShareCodec.Bundle bundle){
    ReferenceUi.Modal d=new ReferenceUi.Modal(this,"导入预览");current=d;d.cancel=this::finish;d.note(bundle.name);d.note(bundle.summary());d.note((bundle.entry==null?"":"1 个入口")+(bundle.entry!=null&&bundle.exit!=null?" · ":"")+(bundle.exit==null?"":"1 个固定出口"));d.note("只导入网络配置，保留登录与草稿。出口需要在本机重新核验。");
    TextView error=ReferenceUi.text(this,"",12,ReferenceUi.RED,false);d.body.addView(error);final boolean[] busy={false};
    DesignUi.action(d.body,"导入并选择环境",false,()->{if(busy[0])return;busy[0]=true;save(bundle,d,error,true,()->busy[0]=false);});
    d.buttons("取消",this::finish,"只保存到网络库",()->{if(busy[0])return;busy[0]=true;save(bundle,d,error,false,()->busy[0]=false);});d.show();
  }
  void save(NetworkShareCodec.Bundle b,ReferenceUi.Modal d,TextView error,boolean configure,Runnable retry){
    error.setText("正在检查节点…");error.setTextColor(ReferenceUi.MUTED);d.primary().setEnabled(false);d.resize();JSONObject[] records=new JSONObject[2];byte[][] payloads=new byte[2][];
    parseNode(b,0,records,payloads,d,error,configure,retry);
  }
  void parseNode(NetworkShareCodec.Bundle b,int i,JSONObject[] records,byte[][] payloads,ReferenceUi.Modal d,TextView error,boolean configure,Runnable retry){
    if(isFinishing()||isDestroyed()||!d.isShowing())return;
    if(i==2){NetworkWorkspaceUi.libraryWork(()->{try{NetworkCatalog catalog=new NetworkCatalog(this);JSONObject ids=catalog.importLocalSources(records[0],payloads[0],records[1],payloads[1]);runOnUiThread(()->{if(isFinishing()||isDestroyed()||!d.isShowing())return;d.dismiss();if(configure)chooseEnvironment(ids);else finish();});}catch(Exception e){runOnUiThread(()->saveError(d,error,retry));}});return;}
    JSONObject node=i==0?b.entry:b.exit;if(node==null){parseNode(b,i+1,records,payloads,d,error,configure,retry);return;}
    byte[] raw=NetworkShareCodec.provider(node);NativeNetwork.previewSubscription(this,i==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,"",raw,(ok,message,names,details,bytes)->{
      if(isFinishing()||isDestroyed()||!d.isShowing())return;if(!ok||names.length()!=1||details.length()!=1){saveError(d,error,retry);return;}
      records[i]=J.obj("name",node.optString("name"),"nodes",names,"nodeDetails",details);payloads[i]=raw;parseNode(b,i+1,records,payloads,d,error,configure,retry);
    });
  }
  void saveError(ReferenceUi.Modal d,TextView error,Runnable retry){if(isFinishing()||isDestroyed()||!d.isShowing())return;retry.run();error.setText("节点无法解析或保存，原环境未改变。请检查配置后重试。");error.setTextColor(ReferenceUi.RED);d.primary().setEnabled(true);d.resize();}
  void chooseEnvironment(JSONObject ids){
    ReferenceUi.Modal d=new ReferenceUi.Modal(this,"选择应用环境");current=d;d.cancel=this::finish;d.note("配置已保存到网络库。选择环境后仍需点击“保存并应用”；其他一端保留原选择。");
    NetworkWorkspaceUi.libraryWork(()->{JSONArray windows=WindowNetworkState.windows(this);NetworkCatalog catalog=new NetworkCatalog(this);runOnUiThread(()->{
      if(isFinishing()||isDestroyed()||!d.isShowing())return;workspace.catalog=catalog;workspace.windows=windows;
      for(int i=0;i<windows.length();i++){JSONObject item=windows.optJSONObject(i);JSONObject row=item.optJSONObject("row");int slot=row.optInt("slot");DesignUi.action(d.body,Profiles.display(this,slot),false,()->{
        d.dismiss();workspace.show(0);NetworkWorkspaceUi.EditorSession editor=workspace.editInternal(item);if(editor==null)return;
        JSONObject entry=catalog.subscription(NetworkCatalog.ENTRY,ids.optString(NetworkCatalog.ENTRY)),exit=catalog.subscription(NetworkCatalog.EXIT,ids.optString(NetworkCatalog.EXIT));
        if(entry!=null){editor.draft.subscription(entry.optString("id"),catalog);editor.draft.mode="manual";editor.draft.chooseEntry(NetworkSourceSelection.names(entry).get(0),catalog);}
        if(exit!=null){String name=NetworkSourceSelection.names(exit).get(0);editor.draft.exitSubscription(exit.optString("id"),catalog);editor.draft.exitNode(NetworkSourceSelection.fingerprint(exit,name),name,catalog);}
        editor.refresh.run();
      });}if(windows.length()==0)d.note("暂时没有可用环境，请先创建环境，再从网络库选择这些节点。");d.resize();
    });});d.buttons("稍后配置",this::finish,"",()->{});d.show();
  }
}
