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
    EditText[] fields={subscription,host,port,user,password};String[] baseline=new String[fields.length];for(int i=0;i<fields.length;i++)baseline[i]=fields[i].getText().toString();
    DesignUi.note(box,"保存后会重新连接此环境。用户名和密码在本机加密保存；首次下载订阅需要可用网络。");
    TextView notice=DesignUi.text(a,"",13,DesignUi.RED);notice.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(notice);
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("订阅与固定出口").setView(scroll).setPositiveButton("保存并连接",null).setNegativeButton("取消",null).create();
    if(vault.hasBundledDefaults())DesignUi.action(box,"恢复默认网络配置",false,()->{
      if(DesignNetworkUi.busy(a)){notice.setText("当前操作还未完成，请稍后再恢复配置。");return;}
      new AlertDialog.Builder(a).setTitle("恢复默认网络配置？").setMessage("当前参数和本次填写的修改会被默认配置替换。")
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
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("完整链路测速").setView(scroll).setPositiveButton("重新测速",null).setNegativeButton("关闭",null).create();
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
  static boolean begin(MainActivity a){if(a.session.pending!=null||a.session.submitting||a.session.operation||a.session.navigating||a.session.navigationFailed||a.session.state.optBoolean("busy")){a.status("请先等待当前任务结束");return false;}a.session.operation=true;a.session.changed();return true;}
  static void end(MainActivity a,String message){a.loading.dismissTask();a.session.escape();a.session.operation=false;a.session.setStatus(message);}
  static void models(MainActivity a){if(!begin(a))return;a.loading.task("正在读取模型与思考强度…");a.status("正在读取可用模型与强度…");a.session.asyncDriver("model-open",new JSONObject(),3000,opened->{if(!opened.optBoolean("ok")){end(a,opened.optString("reason","请先登录"));return;}a.handler.postDelayed(()->a.runDriver("model-options",new JSONObject(),o->modelPanel(a,o)),250);});}
  static void modelPanel(MainActivity a,JSONObject options){
    a.loading.dismissTask();if(a.destroyed){a.session.operation=false;return;}boolean[] switching={false};
    LinearLayout box=new LinearLayout(a);box.setOrientation(1);box.setPadding(a.dp(16),a.dp(10),a.dp(16),a.dp(16));ScrollView scroll=new ScrollView(a);scroll.addView(box);
    AlertDialog dialog=new AlertDialog.Builder(a).setTitle("模型与思考强度").setView(scroll).setNegativeButton("完成",null).create();
    String base=options.optString("baseModel");if(!base.isEmpty())a.prefs.edit().putString("selectedBaseModel",base).apply();
    JSONArray choices=options.optJSONArray("options");
    if(!options.optBoolean("slider")&&choices!=null)for(int i=0;i<choices.length();i++){String value=choices.optString(i);box.addView(a.sheetRow("",(value.equals(base)?"✓ ":"")+value,()->{switching[0]=true;dialog.dismiss();a.loading.task("正在切换模型…");a.runDriver("model-select",J.obj("text",value),r->{if(!r.optBoolean("ok")){end(a,r.optString("reason"));return;}a.handler.postDelayed(()->verifyModel(a,value),250);});}));}
    if(options.optBoolean("slider")&&options.optInt("max")>options.optInt("min")){
      if(options.optBoolean("catalogAvailable")){box.addView(a.sheetRow("chat","型号："+(base.isEmpty()?"选择型号":base),()->{switching[0]=true;dialog.dismiss();a.loading.task("正在读取可用型号…");a.session.asyncDriver("model-catalog-open",new JSONObject(),2500,r->{if(!r.optBoolean("ok")){end(a,r.optString("reason"));return;}a.runDriver("model-options",new JSONObject(),o->modelPanel(a,o));});}));}
      int min=options.optInt("min"),max=options.optInt("max");TextView current=a.label(options.optString("sliderText"),21,Ui.INK);current.setPadding(a.dp(12),a.dp(14),a.dp(12),a.dp(14));box.addView(current);TextView hint=a.label("拖动选择强度；上方显示网页确认的实际名称。",13,Ui.MUTED);hint.setPadding(a.dp(12),0,a.dp(12),a.dp(16));box.addView(hint);
      SeekBar slider=new SeekBar(a);slider.setMax(max-min);slider.setProgress(options.optInt("value")-min);slider.setContentDescription("思考强度");box.addView(slider);
      slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onProgressChanged(SeekBar v,int p,boolean user){}public void onStartTrackingTouch(SeekBar v){}public void onStopTrackingTouch(SeekBar v){int target=v.getProgress()+min;v.setEnabled(false);current.setText("正在切换…");a.session.asyncDriver("slider-set",J.obj("value",target),4000,r->{if(r.optBoolean("needsNative")){int delta=target-r.optInt("value");a.runDriver("slider-focus",new JSONObject(),focused->{if(!focused.optBoolean("ok")){v.setEnabled(true);current.setText("未找到强度控件");return;}applySlider(a,Math.abs(delta),delta>=0?KeyEvent.KEYCODE_DPAD_RIGHT:KeyEvent.KEYCODE_DPAD_LEFT,()->a.runDriver("model-options",new JSONObject(),actual->{v.setEnabled(true);v.setProgress(actual.optInt("value")-min);current.setText(actual.optString("sliderText"));if(actual.optInt("value")!=target)a.status("网页未确认目标档位");}));});}else{v.setEnabled(true);if(r.optBoolean("ok"))current.setText(r.optString("label"));else{current.setText(r.optString("reason","切换未完成"));a.runDriver("model-options",new JSONObject(),actual->v.setProgress(actual.optInt("value")-min));}}});}});
    }
    if(box.getChildCount()==0){end(a,"网页尚未返回可用模型，请稍后重试");return;}
    dialog.setOnDismissListener(d->{if(!switching[0])end(a,"正在读取模型状态…");});dialog.show();dialog.getWindow().setGravity(Gravity.BOTTOM);dialog.getWindow().setLayout(-1,-2);
  }
  static void verifyModel(MainActivity a,String expected){a.runDriver("model-options",new JSONObject(),first->{if(expected.equals(first.optString("baseModel"))){a.prefs.edit().putString("selectedBaseModel",expected).apply();end(a,"已选择 "+expected);return;}a.session.asyncDriver("model-open",new JSONObject(),3000,opened->a.runDriver("model-options",new JSONObject(),actual->{boolean confirmed=expected.equals(actual.optString("baseModel"));if(confirmed)a.prefs.edit().putString("selectedBaseModel",expected).apply();end(a,confirmed?"已选择 "+expected:"网页尚未确认型号，请重新打开面板核对");}));});}
  static void applySlider(MainActivity a,int count,int key,Runnable done){if(count<=0){a.handler.postDelayed(done,200);return;}a.session.nativeKey(key);a.handler.postDelayed(()->applySlider(a,count-1,key,done),70);}
  static void backgroundSettings(Activity a){boolean allowed=a.getSystemService(NotificationManager.class).areNotificationsEnabled();boolean unrestricted=((PowerManager)a.getSystemService(android.content.Context.POWER_SERVICE)).isIgnoringBatteryOptimizations(a.getPackageName());new AlertDialog.Builder(a).setTitle("系统通知与电池权限").setMessage("系统通知："+(allowed?"已开启":"未开启")+"\n系统电池优化："+(unrestricted?"已忽略":"仍启用")+"\n\n发送时启动前台等待服务。切到后台或熄屏后继续检测，收到回复后通知你。安卓可能限制服务时长；强制停止应用或厂商省电策略仍可能中断等待。\n\n超时后保留发送记录，重新打开继续核对，不自动重发。").setPositiveButton("通知设置",(d,w)->{if(Build.VERSION.SDK_INT>=33&&a.checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)a.requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},91);else a.startActivity(new android.content.Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE,a.getPackageName()));}).setNeutralButton("电池设置",(d,w)->a.startActivity(new android.content.Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))).setNegativeButton("关闭",null).show();}
  static void syncHistory(MainActivity a,Runnable refreshed){if(!begin(a))return;a.loading.task("正在同步历史对话…");a.status("正在同步当前工作区的全部历史对话…");a.session.asyncDriver("history-sync",new JSONObject(),600000,result->{JSONArray chats=result.optJSONArray("chats");if(chats!=null)a.conversations.merge(chats,result.optBoolean("complete"));end(a,result.optBoolean("complete")?"历史同步完成 · "+(chats==null?0:chats.length())+" 个对话":result.optString("reason","历史未完全同步，可稍后重试"));refreshed.run();});}
  static void chatActions(MainActivity a,JSONObject chat,Runnable refresh){String title=chat.optString("title"),url=chat.optString("url");a.sheet(title,new String[]{"new","close"},new String[]{"重命名","删除此对话"},new Runnable[]{()->{EditText text=new EditText(a);text.setText(title);new AlertDialog.Builder(a).setTitle("重命名对话").setView(text).setPositiveButton("保存",(d,w)->{String name=text.getText().toString().trim();if(name.isEmpty()||!begin(a))return;a.loading.task("正在保存对话名称…");a.status("正在同步对话名称…");a.session.asyncDriver("history-rename",J.obj("url",url,"title",name),60000,r->{if(r.optBoolean("ok"))a.conversations.rename(url,name);end(a,r.optBoolean("ok")?"名称已同步到 ChatGPT":r.optString("reason","重命名未完成"));refresh.run();});}).setNegativeButton("取消",null).show();},()->new AlertDialog.Builder(a).setTitle("删除此对话？").setMessage("这会同时删除 ChatGPT 中的这个对话，无法撤销。\n\n"+title).setPositiveButton("删除",(d,w)->{if(!begin(a))return;a.loading.task("正在删除对话…");a.status("正在删除对话…");a.session.asyncDriver("history-delete",J.obj("url",url,"confirmed",true),60000,r->{if(r.optBoolean("ok")){a.conversations.remove(url);if(url.equals(a.conversation)){a.remote.loadUrl(MainActivity.ORIGIN);a.showPage(false);}}end(a,r.optBoolean("ok")?"对话已删除":r.optString("reason","删除未得到确认"));refresh.run();});}).setNegativeButton("取消",null).show()});}
}

