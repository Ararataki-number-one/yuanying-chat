package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.net.Uri;
import android.os.Build;
import android.text.InputFilter;
import android.widget.*;
import org.json.JSONObject;

/** Native draft and preview; GitHub owns authentication and the final submission. */
final class FeedbackUi {
  static final String DRAFT="feedbackDraftV1";
  static void open(Activity a){
    JSONObject saved=J.parse(AppSettings.get(a,DRAFT,"{}"));
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"问题与建议");
    Spinner type=new Spinner(a);type.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,new String[]{"遇到问题","改进建议"}));type.setSelection(saved.optBoolean("suggestion")?1:0);d.body.addView(type);
    EditText title=DesignUi.input(d.body,"一句话说明",saved.optString("title"),"例如：选择图片后没有出现附件");title.setFilters(new InputFilter[]{new InputFilter.LengthFilter(FeedbackReport.TITLE_LIMIT)});
    EditText details=DesignUi.input(d.body,"详细说明",saved.optString("details"),"做了什么、实际发生什么、希望怎样改善？");details.setSingleLine(false);details.setMinLines(3);details.setMaxLines(7);details.setGravity(android.view.Gravity.TOP);details.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);details.setFilters(new InputFilter[]{new InputFilter.LengthFilter(FeedbackReport.DETAIL_LIMIT)});
    CheckBox system=new CheckBox(a);system.setText("附带手机型号和 Android 版本");system.setTextColor(ReferenceUi.TEXT);system.setChecked(saved.optBoolean("system",true));d.body.addView(system);
    d.note("反馈公开在 GitHub，需要 GitHub 账号。版本号会附带；不会自动收集聊天、日志或网络配置。请勿填写密码、订阅链接等私人信息。截图可在提交页添加。");
    TextView error=ReferenceUi.text(a,"",13,ReferenceUi.RED,false);d.body.addView(error);
    Runnable save=()->AppSettings.put(a,DRAFT,J.obj("suggestion",type.getSelectedItemPosition()==1,"title",title.getText().toString(),"details",details.getText().toString(),"system",system.isChecked()).toString());
    d.setOnDismissListener(ignored->save.run());
    DesignUi.action(d.body,"查看反馈与处理进度",false,()->{save.run();openUrl(a,FeedbackReport.ISSUES,error);});
    DesignUi.action(d.body,"清空草稿",false,()->{if(title.length()==0&&details.length()==0)return;ReferenceUi.Modal confirm=new ReferenceUi.Modal(a,"清空反馈草稿？");confirm.note("尚未提交的内容将被删除。");confirm.buttons("保留",confirm::dismiss,"清空",()->{title.setText("");details.setText("");save.run();confirm.dismiss();});confirm.show();});
    d.buttons("保存草稿",()->{save.run();d.dismiss();},"预览反馈",()->{
      save.run();FeedbackReport report=new FeedbackReport(type.getSelectedItemPosition()==1,title.getText().toString(),details.getText().toString(),AppVersion.name(a),system.isChecked()?Build.MANUFACTURER+" "+Build.MODEL+" / Android "+Build.VERSION.RELEASE:"");
      error.setText(report.error());if(!report.error().isEmpty()){d.resize();return;}preview(a,report);
    });d.show();
  }
  static void preview(Activity a,FeedbackReport report){
    ReferenceUi.Modal d=new ReferenceUi.Modal(a,"预览公开反馈");d.note(report.issueTitle()+"\n\n"+report.body());
    TextView status=ReferenceUi.text(a,"",13,ReferenceUi.MUTED,false);d.body.addView(status);
    String url=report.url();if(url==null)d.note("内容较长：先复制反馈，再打开 GitHub 粘贴到正文。草稿仍保存在本机。");else d.note("打开后可检查、添加截图，再点击 GitHub 的提交按钮。打开提交页不代表已经提交。");
    DesignUi.action(d.body,"复制反馈内容",false,()->{copy(a,report.body());status.setText("已复制，可粘贴到 GitHub 正文。不要将私人信息附在截图里。");d.resize();});
    d.buttons("返回修改",d::dismiss,url==null?"复制并打开提交页":"打开 GitHub 提交",()->{if(url==null)copy(a,report.body());if(openUrl(a,url==null?report.baseUrl():url,status)){status.setText("已打开提交页；完成提交后可在反馈列表查看。草稿已保留。");d.resize();}});d.show();
  }
  static void copy(Activity a,String value){ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);clipboard.setPrimaryClip(ClipData.newPlainText("反馈内容",value));}
  static boolean openUrl(Activity a,String url,TextView error){try{a.startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE));return true;}catch(ActivityNotFoundException|SecurityException unavailable){error.setText("未找到可打开 GitHub 的浏览器。可先复制反馈，稍后在项目 Issues 中提交。");return false;}}
}
