package local.pocketchat;
import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import org.json.*;

final class FeatureDialogs {
  static EditText field(MainActivity a,LinearLayout box,String title,String value,int type){EditText e=DesignUi.input(box,title,value,"");e.setInputType(type);return e;}
  static void networkAdvanced(MainActivity a){
    SecretStore vault=new SecretStore(a);JSONObject saved=vault.settings();LinearLayout box=DesignUi.column(a);box.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(16));
    DesignUi.note(box,Profiles.display(a,Profiles.slot(a))+" · 先连接订阅中的入口，再经固定出口访问 ChatGPT。");
    EditText subscription=field(a,box,"入口订阅地址（HTTPS）",saved.optString("subscriptionUrl"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
    subscription.setHint("填写 Clash / Mihomo 订阅地址");
    EditText host=field(a,box,"固定出口服务器",saved.optString("exitHost"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);host.setHint("服务器域名或 IP");
    EditText port=field(a,box,"固定出口端口",saved.has("exitPort")?saved.optString("exitPort"):"",InputType.TYPE_CLASS_NUMBER);port.setHint("1–65535");
    EditText user=field(a,box,"出口用户名",saved.optString("exitUser"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
    EditText password=field(a,box,"出口密码",saved.optString("exitPassword"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
    password.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
    DesignUi.visiblePassword(password);
    EditText[] fields={subscription,host,port,user,password};String[] baseline=new String[fields.length];for(int i=0;i<fields.length;i++)baseline[i]=fields[i].getText().toString();
    DesignUi.note(box,"保存后会重新连接此环境。用户名和密码在本机加密保存；首次下载订阅需要可用网络。");
    TextView notice=DesignUi.text(a,"",13,DesignUi.RED);notice.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("订阅与固定出口").setView(scroll).setPositiveButton("保存并连接",null).setNegativeButton("取消",null).create();
    if(vault.hasBundledDefaults())DesignUi.action(box,"恢复默认网络配置",false,()->{
      if(DesignNetworkUi.busy(a)){notice.setText("当前操作还未完成，请稍后再恢复配置。");return;}
      AppAppearance.dialog(a).setTitle("恢复默认网络配置？").setMessage("当前参数和本次填写的修改会被默认配置替换。")
        .setPositiveButton("恢复并连接",(d,w)->{try{vault.restoreBundledDefaults();dialog.dismiss();a.session.reconnect();a.status("已恢复默认网络配置");}catch(Exception e){notice.setText("恢复失败，请稍后重试。");}}).setNegativeButton("继续编辑",null).show();
    });
    dialog.show();
    DesignUi.protectEdits(a,dialog,()->{for(int i=0;i<fields.length;i++)if(!baseline[i].equals(fields[i].getText().toString()))return true;return false;});
    dialog.getButton(-1).setOnClickListener(v->{
      if(DesignNetworkUi.busy(a)){notice.setText("当前回复或操作还未完成，请结束后再保存网络配置。");return;}
      notice.setText("");for(EditText field:fields)field.setError(null);
      int number;try{number=Integer.parseInt(port.getText().toString().trim());}catch(Exception e){port.setError("请输入 1–65535 的端口");port.requestFocus();return;}
      JSONObject config=J.obj("subscriptionUrl",subscription.getText().toString().trim(),"exitHost",host.getText().toString().trim(),"exitPort",number,"exitUser",user.getText().toString(),"exitPassword",password.getText().toString());
      try{NativeNetwork.validate(config);}catch(Exception e){String reason=e.getMessage()==null?"请检查网络参数":e.getMessage();EditText invalid=reason.contains("端口")?port:reason.contains("固定出口")?host:subscription;invalid.setError(reason);invalid.requestFocus();return;}
      try{vault.save(config);a.prefs.edit().putBoolean("networkConfigured",true).putString("networkMode","internal").commit();dialog.dismiss();a.session.reconnect();}
      catch(Exception e){notice.setText("配置未能保存，请稍后重试。填写的内容仍在此处。");}
    });
  }
  static void network(MainActivity a){DesignNetworkUi.modes(a);}
  static void nodes(MainActivity a){
    NativeNetwork n=NativeNetwork.get(a);LinearLayout box=DesignUi.column(a);box.setPadding(a.dp(16),a.dp(12),a.dp(16),a.dp(16));
    TextView state=DesignUi.text(a,n.message,14,DesignUi.MUTED);state.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(state);
    LinearLayout rows=DesignUi.column(a);box.addView(rows);final boolean[] operating={false};
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("完整链路测速").setView(scroll).setPositiveButton("重新测速",null).setNegativeButton("关闭",null).create();
    final Runnable[] refresh={null};refresh[0]=()->{
      DesignUi.rebuild(rows,true,()->{
        if(n.results.length()==0)DesignUi.empty(rows,"还没有测量结果","保存内置网络配置后，点“重新测速”检查实际线路。","",null);
        for(int i=0;i<n.results.length();i++){
          JSONObject item=n.results.optJSONObject(i);if(item==null)continue;
          String name=item.optString("internalName"),title=item.optString("name"),detail=item.optInt("delay")>0?item.optInt("delay")+" ms":"本次不可用";
          if(item.optInt("samples")>0)detail+=" · 成功 "+Math.round(item.optDouble("successRate")*100)+"% · 波动 "+item.optLong("jitter")+" ms";
          LinearLayout card=DesignUi.setting(a,"globe",title,detail,name.equals(n.currentEntry)?"使用中":"",()->{
            if(operating[0]||DesignNetworkUi.busy(a)){a.status("请等待当前操作完成");return;}
            operating[0]=true;dialog.getButton(-1).setEnabled(false);a.loading.task("正在切换并检查线路…");
            n.select(name,(ok,msg)->{a.loading.dismissTask();operating[0]=false;a.status(msg);if(dialog.isShowing()){state.setText(msg);dialog.getButton(-1).setEnabled(true);refresh[0].run();}});
          });DesignUi.addCard(rows,card);
        }
      });
    };
    dialog.show();refresh[0].run();
    dialog.getButton(-1).setOnClickListener(v->{
      if(operating[0]||DesignNetworkUi.busy(a)){a.status("请等待当前操作完成");return;}
      operating[0]=true;dialog.getButton(-1).setEnabled(false);a.loading.task("正在测试线路速度…");
      n.rescan((ok,msg)->{a.loading.dismissTask();operating[0]=false;a.status(msg);if(dialog.isShowing()){state.setText(msg);dialog.getButton(-1).setEnabled(true);refresh[0].run();}});
    });
  }
  static void backgroundSettings(Activity a){boolean allowed=a.getSystemService(NotificationManager.class).areNotificationsEnabled();boolean unrestricted=((PowerManager)a.getSystemService(android.content.Context.POWER_SERVICE)).isIgnoringBatteryOptimizations(a.getPackageName());AppAppearance.dialog(a).setTitle("系统通知与电池权限").setMessage("系统通知："+(allowed?"已开启":"未开启")+"\n系统电池优化："+(unrestricted?"已忽略":"仍启用")+"\n\n后台回复检测默认关闭；开启后才会在后台检测回复。完成提醒也需主动开启；使用应用时保持安静。代理连接可独立运行，并显示静默服务提示。\n\n强制停止或省电策略可能中断检测。发送记录会保留，重新打开继续核对，不自动重发。").setPositiveButton("通知设置",(d,w)->{if(Build.VERSION.SDK_INT>=33&&a.checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)a.requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},91);else a.startActivity(new android.content.Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE,a.getPackageName()));}).setNeutralButton("电池设置",(d,w)->a.startActivity(new android.content.Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))).setNegativeButton("关闭",null).show();}
}
