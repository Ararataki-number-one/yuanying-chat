package local.pocketchat;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** User-initiated system document picker. This activity creates no Gecko session. */
public final class EnvironmentConfigBackupActivity extends ThemedActivity {
  static final int EXPORT=841,IMPORT=842;
  final ExecutorService worker=Executors.newSingleThreadExecutor();
  volatile long owner=1;boolean busy;int picker;byte[] pending;
  TextView result;LinearLayout body;
  @Override public void onCreate(Bundle state){
    super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    LinearLayout root=DesignUi.screen(this);body=DesignUi.body(this,root,"环境配置备份",this::finish);
    DesignUi.note(body,"备份仅包含你选择的环境名称、浏览器模板、网页语言和使用偏好。使用密码加密，请自行保管密码。");
    DesignUi.note(body,"不包含网络账号、订阅、固定出口、登录、Cookie、聊天、草稿、附件或设备密钥。恢复会创建新环境，随后需重新配置网络；现有环境保持不变。");
    DesignUi.action(body,"选择环境并备份",false,this::chooseSource);
    DesignUi.action(body,"选择备份并恢复",false,()->{if(busy||picker!=0)return;clearPending();try{picker=IMPORT;startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),IMPORT);}catch(Exception failure){picker=0;message("设备没有可用的文件选择器");}});
    result=DesignUi.text(this,"",13,DesignUi.MUTED);result.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);body.addView(result);setContentView(root);
  }
  boolean active(long serial){return serial==owner&&!isFinishing()&&!isDestroyed();}
  void message(String text){if(!isFinishing()&&!isDestroyed())result.setText(text);}
  void chooseSource(){
    if(busy||picker!=0)return;clearPending();busy=true;long serial=owner;message("正在读取环境列表…");
    worker.execute(()->{
      List<String> names=new ArrayList<>();List<EnvironmentSpec.Identity> identities=new ArrayList<>();boolean read=false;
      try{if(!active(serial))return;ProfileCatalog catalog=ProfileCatalog.get(this);JSONArray rows=catalog.list();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(!AppSettings.selectable(row))continue;identities.add(catalog.identity(row.optInt("slot")));names.add(row.optString("name"));}read=true;}catch(Exception ignored){}
      boolean complete=read;runOnUiThread(()->{if(!active(serial))return;busy=false;if(!complete){message("环境列表暂时无法读取，请重试");return;}message("");ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"选择备份环境");
        for(int i=0;i<names.size();i++){EnvironmentSpec.Identity expected=identities.get(i);DesignUi.action(dialog.body,names.get(i),false,()->{dialog.dismiss();password(true,(secret)->export(expected,secret));});}
        if(names.isEmpty())dialog.note("暂时没有可用环境，请先在环境列表创建。");dialog.buttons("取消",dialog::dismiss,"",()->{});dialog.show();
      });
    });
  }
  interface PasswordAction {void run(char[] secret);}
  void password(boolean creating,PasswordAction action){
    LinearLayout box=DesignUi.column(this);box.setPadding(DesignUi.dp(this,18),0,DesignUi.dp(this,18),DesignUi.dp(this,12));
    EditText password=DesignUi.input(box,"备份密码","","10–256 个字符");password.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);password.setSaveEnabled(false);password.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(256)});
    EditText repeat=creating?DesignUi.input(box,"再次输入密码","",""):null;if(repeat!=null){repeat.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);repeat.setSaveEnabled(false);repeat.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(256)});}
    DesignUi.note(box,creating?"密码无法找回。备份只包含模板、语言与使用偏好，恢复后需要重新配置网络。":"正确解密后会先显示预览，不会覆盖现有环境。");
    AlertDialog dialog=AppAppearance.dialog(this).setTitle(creating?"加密备份":"打开加密备份").setView(box).setNegativeButton("取消",null).setPositiveButton(creating?"选择保存位置":"解密并预览",null).create();
    dialog.setOnDismissListener(d->{password.setText("");if(repeat!=null)repeat.setText("");});dialog.show();
    dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
      int length=password.length();if(length<10||length>256){password.setError("请输入 10–256 个字符");return;}boolean matching=true;if(repeat!=null){matching=repeat.length()==length;for(int i=0;matching&&i<length;i++)matching=password.getText().charAt(i)==repeat.getText().charAt(i);}if(!matching){repeat.setError("两次密码不一致");return;}
      char[] secret=new char[length];password.getText().getChars(0,length,secret,0);dialog.dismiss();action.run(secret);
    });
  }
  void export(EnvironmentSpec.Identity expected,char[] password){
    if(busy){Arrays.fill(password,'\0');return;}busy=true;long serial=owner;message("正在加密配置…");
    worker.execute(()->{
      byte[] encrypted=null;String error="";try{if(!active(serial))return;Context source=Profiles.context(this,expected.slot);encrypted=EnvironmentConfigBackup.encrypt(EnvironmentConfigTransfer.capture(source,expected),password);}catch(Exception failure){error="配置读取或加密失败，未生成备份，请重试";}finally{Arrays.fill(password,'\0');}
      byte[] ready=encrypted;String issue=error;runOnUiThread(()->{if(!active(serial)){if(ready!=null)Arrays.fill(ready,(byte)0);return;}busy=false;if(!issue.isEmpty()){message(issue);return;}pending=ready;
        try{picker=EXPORT;startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,"PocketChat-环境配置.pocketcfg"),EXPORT);message("请选择备份保存位置");}catch(Exception failure){picker=0;clearPending();message("设备没有可用的文件保存器");}
      });
    });
  }
  @Override protected void onActivityResult(int request,int code,Intent data){
    super.onActivityResult(request,code,data);if((request!=EXPORT&&request!=IMPORT)||picker!=request)return;picker=0;
    if(code!=RESULT_OK||data==null||data.getData()==null){if(request==EXPORT)clearPending();return;}Uri uri=data.getData();
    if(!"content".equals(uri.getScheme())||uri.getAuthority()==null||uri.getAuthority().startsWith(getPackageName()+".")){if(request==EXPORT)clearPending();message("请选择系统文件提供者中的文件");return;}
    if(busy)return;busy=true;long serial=owner;
    if(request==EXPORT){byte[] bytes=pending;pending=null;if(bytes==null){busy=false;message("备份任务已失效，请重新选择环境");return;}message("正在保存备份…");worker.execute(()->{
      boolean written=false,verified=false;try{if(!active(serial))return;try(OutputStream stream=getContentResolver().openOutputStream(uri,"w")){if(stream==null)throw new IOException();stream.write(bytes);stream.flush();}written=true;
        try(InputStream stream=getContentResolver().openInputStream(uri)){byte[] reread=EnvironmentConfigBackup.read(stream);try{verified=java.security.MessageDigest.isEqual(bytes,reread);}finally{Arrays.fill(reread,(byte)0);}}
      }catch(Exception ignored){}finally{Arrays.fill(bytes,(byte)0);}
      boolean accepted=written,complete=verified;runOnUiThread(()->{if(!active(serial))return;busy=false;message(complete?"备份已保存并读回核对，请保管密码。网络配置与登录未包含在内。":accepted?"文件已交给保存器，但读回未确认，请检查备份文件并重试。":"备份写入未完成，请删除不完整文件后重试");});
    });}else{message("正在读取备份…");worker.execute(()->{
      byte[] bytes=null;try{if(!active(serial))return;try(InputStream stream=getContentResolver().openInputStream(uri)){bytes=EnvironmentConfigBackup.read(stream);}}catch(Exception ignored){}
      byte[] ready=bytes;runOnUiThread(()->{if(!active(serial)){if(ready!=null)Arrays.fill(ready,(byte)0);return;}busy=false;if(ready==null){message("备份不可读取或超过 64 KB，原环境未改变");return;}pending=ready;password(false,this::decrypt);});
    });}
  }
  void decrypt(char[] password){
    byte[] bytes=pending;pending=null;if(busy||bytes==null){Arrays.fill(password,'\0');message("请重新选择备份文件");return;}busy=true;long serial=owner;message("正在解密并验证…");
    worker.execute(()->{EnvironmentConfigBackup.Config config=null;try{if(!active(serial))return;config=EnvironmentConfigBackup.decrypt(bytes,password);}catch(Exception ignored){}finally{Arrays.fill(password,'\0');Arrays.fill(bytes,(byte)0);}
      EnvironmentConfigBackup.Config safe=config;runOnUiThread(()->{if(!active(serial))return;busy=false;if(safe==null){message("密码不正确、文件已损坏或版本不支持，原环境未改变");return;}preview(safe);});
    });
  }
  void preview(EnvironmentConfigBackup.Config config){
    ReferenceUi.Modal dialog=new ReferenceUi.Modal(this,"恢复预览");dialog.note(config.name+"\n"+config.browser.label()+"\n网页语言："+(config.browser.locales.isEmpty()?"跟随系统":String.join(", ",config.browser.locales)));
    java.util.concurrent.atomic.AtomicBoolean visible=new java.util.concurrent.atomic.AtomicBoolean(true);dialog.setOnDismissListener(d->visible.set(false));
    dialog.note("将模板与使用偏好恢复为新环境。现有环境不会被覆盖。请重新配置网络、核验固定出口并登录；恢复前不会打开网页。点击创建后若离开页面，请先在环境列表确认结果，再决定是否重试。");
    TextView error=DesignUi.text(this,"",13,DesignUi.RED);dialog.body.addView(error);
    dialog.buttons("取消",dialog::dismiss,"创建新环境",()->{
      if(busy)return;busy=true;long serial=owner;dialog.primary().setEnabled(false);error.setText("正在创建新环境…");
      worker.execute(()->{EnvironmentSpec.Identity restored=null;String issue="";try{if(!active(serial))return;JSONArray rows=ProfileCatalog.get(this).list();int slot=-1;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&!row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting")){slot=row.optInt("slot",-1);break;}}if(slot<0)throw new IOException("没有可用的环境槽位；现有环境未改变");if(!active(serial))return;restored=EnvironmentConfigTransfer.restore(this,slot,config,()->active(serial)&&visible.get());}catch(Exception failure){issue="恢复结果尚未确认，现有环境未被覆盖。请先查看环境列表，再决定是否重试。";}
        EnvironmentSpec.Identity completed=restored;String problem=issue;runOnUiThread(()->{if(!active(serial))return;busy=false;if(completed==null){if(dialog.isShowing()){dialog.primary().setEnabled(true);error.setText(problem);}else message(problem);return;}dialog.dismiss();message("新环境已创建，尚未联网。请前往环境列表重新配置网络并登录。");});
      });
    });dialog.show();
  }
  void clearPending(){if(pending!=null){Arrays.fill(pending,(byte)0);pending=null;}}
  @Override protected void onDestroy(){owner++;clearPending();worker.shutdown();super.onDestroy();}
}
