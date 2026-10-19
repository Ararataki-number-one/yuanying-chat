package local.pocketchat;

import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.*;

/** First-run introduction shares the same readable native surfaces as the workspaces. */
public class BrandLaunchActivity extends ThemedActivity {
  void route(){AppUpdates.schedule(this);AppSettings.put(this,"brandSeen","true");if(AppSettings.bool(this,"startupDirect",true)){int id=AppSettings.defaultSlot(this);ProfileCatalog.get(this).opened(id);startActivity(new Intent(this,Profiles.activity(id)).putExtra("openWindowAction","chat").putExtra("forceWebMode",true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}else startActivity(new Intent(this,WindowHomeActivity.class));finish();}
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    if(AppSettings.bool(this,"brandSeen",false)&&!getIntent().getBooleanExtra("previewBrand",false)){route();return;}
    LinearLayout root=DesignUi.screen(this),content=DesignUi.column(this);
    ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);
    content.setPadding(DesignUi.dp(this,24),DesignUi.dp(this,36),DesignUi.dp(this,24),DesignUi.dp(this,24));
    ImageView logo=DesignUi.icon(this,"brand",DesignUi.BLUE,64);content.addView(logo);
    TextView name=DesignUi.text(this,"元婴期院士",28,DesignUi.TEXT);name.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));name.setPadding(0,DesignUi.dp(this,20),0,DesignUi.dp(this,8));content.addView(name);
    DesignUi.note(content,"专注你的 ChatGPT 原网页。\n独立环境，清楚掌握每一条连接。");
    DesignUi.section(content,"为日常使用而设计","");
    LinearLayout features=DesignUi.group(this);content.addView(features);
    DesignUi.groupedRow(features,DesignUi.setting(this,"chat","熟悉的原网页","沿用官方输入、模型选择和会话操作。","",null));
    DesignUi.groupedRow(features,DesignUi.setting(this,"window","彼此独立的环境","分别保存登录、草稿和网络配置。","",null));
    DesignUi.groupedRow(features,DesignUi.setting(this,"lock","固定出口","入口和出口独立管理，线路状态清楚可见。","",null));
    DesignUi.action(content,"立即进入",true,this::route);
    TextView version=DesignUi.text(this,"版本 "+AppVersion.name(this),12,DesignUi.MUTED);version.setGravity(Gravity.CENTER);version.setPadding(0,DesignUi.dp(this,18),0,0);content.addView(version);
    scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
  }
}
