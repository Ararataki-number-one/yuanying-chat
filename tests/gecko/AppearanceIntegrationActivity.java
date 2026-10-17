package local.pocketchat;

import android.os.*;
import android.graphics.drawable.ColorDrawable;
import android.content.res.Configuration;
import android.widget.*;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.io.File;

/** Test-only native windows; real system night-mode events and actual taps drive the controls. */
public final class AppearanceIntegrationActivity extends ThemedActivity {
  final Handler handler=new Handler(Looper.getMainLooper());
  final String instance=java.util.UUID.randomUUID().toString();
  String token;String feedbackUrl="";LinearLayout root,settings;EditText draft;TextView sample;Button primary;
  ReferenceUi.Modal modal;int configurations;JSONObject buildIdentity;
  @Override public void onCreate(Bundle state){super.onCreate(state);token=getIntent().getStringExtra("runToken");
    root=DesignUi.screen(this);settings=DesignUi.body(this,root,"外观测试",null);
    sample=DesignUi.text(this,"正文与辅助信息",16,DesignUi.TEXT);settings.addView(sample);
    draft=DesignUi.input(settings,"保留输入","夜间中文草稿","输入不丢失");draft.setSelection(2,4);
    primary=DesignUi.button(this,"打开外观设置",true,()->{DesignSettingsUi.appearance(this,()->{});});settings.addView(primary);
    DesignUi.action(settings,"检查弹窗",false,()->{modal=new ReferenceUi.Modal(this,"弹窗配色");modal.note("网络与下载仍可继续");modal.buttons("关闭",modal::dismiss,"确定",modal::dismiss);modal.show();});
    DesignUi.action(settings,"打开反馈",false,()->{if(AppSettings.get(this,FeedbackUi.DRAFT,"").isEmpty())AppSettings.put(this,FeedbackUi.DRAFT,J.obj("suggestion",false,"title","Upload picker missing","details","Tap add attachment; picker does not appear.","system",false).toString());FeedbackUi.open(this);});
    setContentView(root);handler.post(write);
  }
  @Override public void startActivity(android.content.Intent intent){
    if(android.content.Intent.ACTION_VIEW.equals(intent.getAction())&&intent.getData()!=null&&"github.com".equals(intent.getData().getHost())){feedbackUrl=intent.getData().toString();return;}
    super.startActivity(intent);
  }
  JSONObject identity()throws Exception{if(buildIdentity==null)buildIdentity=IntegrationBuildIdentity.read(this);return buildIdentity;}
  final Runnable write=new Runnable(){public void run(){try{
    JSONObject value=J.obj("runToken",token,"instance",instance,"buildIdentity",identity(),"actualAndroidExecution",true,
      "feedbackUrl",feedbackUrl,"feedbackDraft",AppSettings.get(AppearanceIntegrationActivity.this,FeedbackUi.DRAFT,""),"mode",AppAppearance.mode(),"dark",AppAppearance.dark(),"systemDark",(getResources().getConfiguration().uiMode&Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES,
      "textColor",sample.getCurrentTextColor(),"cardColor",DesignUi.CARD,"backgroundColor",DesignUi.BG,"primaryText",primary.getCurrentTextColor(),
      "draft",draft.getText().toString(),"selectionStart",draft.getSelectionStart(),"selectionEnd",draft.getSelectionEnd(),"configurations",configurations,
      "systemUi",getWindow().getDecorView().getSystemUiVisibility(),"modalVisible",modal!=null&&modal.isShowing(),"modalColor",modal==null?0:((android.graphics.drawable.GradientDrawable)modal.root.getBackground()).getColor().getDefaultColor());
    android.util.AtomicFile file=new android.util.AtomicFile(new File(getFilesDir(),"appearance-results.json"));java.io.FileOutputStream out=file.startWrite();out.write(value.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(out);
  }catch(Exception e){android.util.Log.e("AppearanceTest","report",e);}handler.postDelayed(this,500);}};
  @Override public void onConfigurationChanged(Configuration c){super.onConfigurationChanged(c);configurations++;}
  @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
