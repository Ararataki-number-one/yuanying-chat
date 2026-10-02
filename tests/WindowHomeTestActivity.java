package local.pocketchat;

import android.content.*;import android.database.sqlite.*;import android.os.*;import android.widget.*;import org.json.*;import java.io.*;

/** Actual native launcher, including migration of the previous shared catalog. */
public class WindowHomeTestActivity extends WindowHomeActivity {
  final JSONArray checks=new JSONArray();Intent openedIntent;int launches;
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  @Override public void onCreate(Bundle b){Context root=Profiles.global(this);if(ProfileCatalog.instance!=null){ProfileCatalog.instance.close();ProfileCatalog.instance=null;}root.deleteDatabase("environment-catalog.db");SQLiteDatabase db=root.openOrCreateDatabase("environment-catalog.db",0,null);db.execSQL("CREATE TABLE environments (slot INTEGER PRIMARY KEY,name TEXT NOT NULL,created INTEGER NOT NULL DEFAULT 0,draft TEXT NOT NULL DEFAULT '',pid INTEGER NOT NULL DEFAULT 0,seen INTEGER NOT NULL DEFAULT 0,connected INTEGER NOT NULL DEFAULT 0,waiting INTEGER NOT NULL DEFAULT 0,mode TEXT NOT NULL DEFAULT '',privacy INTEGER NOT NULL DEFAULT 1)");for(int i=0;i<8;i++)db.execSQL("INSERT INTO environments(slot,name,created,draft) VALUES(?,?,?,?)",new Object[]{i,i==0?"个人主号":i==1?"工作号":i==2?"备用号":"窗口 "+(i+1),i<3?1:0,i==0?"{\"name\":\"原有编辑草稿\"}":""});db.setVersion(1);db.close();super.onCreate(b);handler.postDelayed(()->test(),300);}
  @Override public void startActivity(Intent intent){openedIntent=intent;launches++;}
  void test(){ProfileCatalog catalog=ProfileCatalog.get(this);Intent launcher=getPackageManager().getLaunchIntentForPackage(getPackageName());check("App icon resolves to the window launcher",launcher!=null&&launcher.getComponent().getClassName().endsWith("BrandLaunchActivity"));check("Native launcher does not create a chat session",ChatSession.peek()==null);check("Existing three windows survive catalog upgrade",catalog.item(0).optBoolean("created")&&catalog.item(1).optBoolean("created")&&catalog.item(2).optBoolean("created"));check("Existing names and editor drafts survive upgrade",catalog.name(0).equals("个人主号")&&catalog.item(0).optString("draft").contains("原有编辑草稿"));check("Launcher displays real window cards",cards.getChildCount()==3&&count.getText().toString().contains("3 / 8"));search.setText("工作");check("Name search filters actual cards",cards.getChildCount()==1);search.setText("");catalog.favorite(1,true);filter=1;refresh();check("Favorites persist and filter windows",catalog.item(1).optBoolean("favorite")&&cards.getChildCount()==1);filter=0;refresh();check("v1 migration creates empty group metadata",catalog.item(1).has("group")&&catalog.item(1).optString("group").isEmpty());catalog.details(1,"工作","资料研究");selectedGroup="工作";refresh();check("Group filter shows its actual environment",cards.getChildCount()==1&&catalog.item(1).optString("notes").equals("资料研究"));selectedGroup=null;search.setText("资料研究");check("Search includes profile notes",cards.getChildCount()==1);search.setText("02");check("Search includes stable environment number",cards.getChildCount()==1);search.setText("");sort=2;refresh();check("Name sorting retains every environment",cards.getChildCount()==3);sort=0;refresh();cards.getChildAt(1).performClick();check("Tapping a window routes to its owning profile",openedIntent!=null&&openedIntent.getComponent().getClassName().endsWith("ProfileActivity1")&&"chat".equals(openedIntent.getStringExtra("openWindowAction")));check("Opening records a separate last-opened timestamp",catalog.item(1).optLong("opened")>0&&lastWindow()==1);check("Window cards never submit chat content",ChatSession.peek()==null);openWindow(2,"network");check("Window network menu targets the selected profile",openedIntent.getComponent().getClassName().endsWith("ProfileActivity2")&&"network".equals(openedIntent.getStringExtra("openWindowAction")));try{android.content.pm.ActivityInfo settings=getPackageManager().getActivityInfo(new ComponentName(this,AppSettingsActivity.class),0);check("Global settings is a private native destination",!settings.exported);}catch(Exception e){check("Global settings is a private native destination",false);}try{android.content.pm.ActivityInfo info=getPackageManager().getActivityInfo(new ComponentName(this,DownloadCenterActivity.class),0);check("Download center is private and available without chat",!info.exported);}catch(Exception e){check("Download center is private and available without chat",false);}batchChecks(catalog);try{J.write(new File(getFilesDir(),"window-home-results.json"),J.obj("checks",checks,"scope","Actual native launcher; v1 catalog migration; no account or external traffic").toString(2));}catch(Exception ignored){}search.setText("");filter=0;refresh();}
  static String text(android.view.View view){
    StringBuilder out=new StringBuilder();
    if(view instanceof TextView)out.append(((TextView)view).getText());
    if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++)out.append(text(group.getChildAt(i)));}
    return out.toString();
  }
  static <T extends android.view.View> T find(android.view.View view,Class<T> type){
    if(type.isInstance(view))return type.cast(view);
    if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){T result=find(group.getChildAt(i),type);if(result!=null)return result;}}
    return null;
  }
  void batchChecks(ProfileCatalog catalog){
    try{
      JSONObject draft=J.obj("name","保留编辑草稿","group","工作","privacyLevel",1);
      catalog.details(0,"个人","个人备注");catalog.details(1,"工作","工作备注");catalog.draft(1,draft);
      Context profile=Profiles.context(this,1);
      profile.getSharedPreferences("chat",0).edit().putString("proxy","http://fixture.invalid:8080").putString("conversation","https://chatgpt.com/c/kept").commit();
      int initialLaunches=launches;refresh();
      check("Environment cards emphasize open and move editing to more",text(cards.getChildAt(0)).contains("打开环境")&&text(cards.getChildAt(0)).contains("更多")&&!text(cards.getChildAt(0)).contains("编辑环境"));
      check("Cards show group, network record, and recent use",text(cards.getChildAt(0)).contains("个人")&&text(cards.getChildAt(0)).contains("网络状态")&&text(cards.getChildAt(0)).contains("最近使用"));
      cards.getChildAt(0).performLongClick();cards.getChildAt(1).performClick();
      check("Long press and selection clicks never open profiles",selecting&&selectedIds.contains(0)&&selectedIds.contains(1)&&launches==initialLaunches);
      selectedGroup="工作";refresh();
      check("Filtering preserves hidden selections and reports their scope",visibleIds.size()==1&&selectedIds.size()==2&&selectionCount.getText().toString().contains("筛选外 1"));
      visibleSelectionButton.performClick();
      check("Deselect current results leaves hidden selections intact",selectedIds.size()==1&&selectedIds.contains(0));
      visibleSelectionButton.performClick();
      check("Select current results only adds matching environments",selectedIds.size()==2&&selectedIds.contains(1)&&!selectedIds.contains(2));
      selectedGroup=null;refresh();visibleSelectionButton.performClick();
      check("Select current results selects all shown profiles",selectedIds.size()==3);
      CheckBox check=find(cards.getChildAt(2),CheckBox.class);if(check!=null)check.performClick();
      check("Checkbox deselects its own stable profile ID",!selectedIds.contains(2)&&selectedIds.contains(0)&&selectedIds.contains(1));
      favoriteSelectedButton.performClick();
      check("Bulk favorite only updates selected created profiles",catalog.item(0).optBoolean("favorite")&&catalog.item(1).optBoolean("favorite")&&!catalog.item(2).optBoolean("favorite"));
      android.app.AlertDialog dialog=batchGroup();EditText group=find(dialog.getWindow().getDecorView(),EditText.class);
      group.setText("项目组");dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick();
      check("Bulk group form saves every selected profile",catalog.item(0).optString("group").equals("项目组")&&catalog.item(1).optString("group").equals("项目组")&&catalog.item(2).optString("group").isEmpty());
      check("Bulk group preserves notes and editor drafts",catalog.item(0).optString("notes").equals("个人备注")&&catalog.item(1).optString("notes").equals("工作备注")&&catalog.item(1).optString("draft").equals(draft.toString()));
      check("Bulk management preserves profile network and conversation settings",profile.getSharedPreferences("chat",0).getString("proxy","").equals("http://fixture.invalid:8080")&&profile.getSharedPreferences("chat",0).getString("conversation","").endsWith("/c/kept"));
      unfavoriteSelectedButton.performClick();
      check("Bulk unfavorite preserves selection for further edits",!catalog.item(0).optBoolean("favorite")&&!catalog.item(1).optBoolean("favorite")&&selectedIds.size()==2);
      int count=catalog.group(java.util.Arrays.asList(0,0,2,7,-1,8,null),"共享");
      check("Bulk storage ignores duplicates, invalid IDs, and uncreated slots",count==2&&catalog.item(2).optString("group").equals("共享")&&!catalog.item(7).optBoolean("created")&&catalog.item(7).optString("group").isEmpty());
      String before=catalog.item(0).optString("group");boolean rejected=false;
      try{catalog.group(java.util.Arrays.asList(0,1),"1234567890123");}catch(IllegalArgumentException expected){rejected=true;}
      check("Invalid group rejects the whole operation without changing metadata",rejected&&catalog.item(0).optString("group").equals(before)&&catalog.item(1).optString("group").equals("项目组"));
      catalog.group(java.util.Arrays.asList(0,1),"");
      check("Empty batch group explicitly returns selected profiles to ungrouped",catalog.item(0).optString("group").isEmpty()&&catalog.item(1).optString("group").isEmpty());
      Bundle state=new Bundle();onSaveInstanceState(state);
      check("Configuration state retains selection IDs rather than list positions",state.getBoolean("selecting")&&state.getIntArray("selectedIds").length==2);
      search.setText("不存在的环境");
      check("Empty filtered view keeps selected scope and disables select-all",selectedIds.size()==2&&!visibleSelectionButton.isEnabled()&&batchGroupButton.isEnabled());
      onBackPressed();
      check("Back exits selection without leaving the manager or changing favorites",!selecting&&selectedIds.isEmpty()&&!catalog.item(0).optBoolean("favorite"));
      search.setText("");selectedGroup=null;sort=1;
      catalog.getWritableDatabase().execSQL("UPDATE environments SET opened=CASE slot WHEN 0 THEN 1000 WHEN 1 THEN 3000 WHEN 2 THEN 2000 ELSE 0 END");refresh();
      check("Recent sort orders by actual opened timestamps",visibleIds.equals(java.util.Arrays.asList(1,2,0)));
      check("Recent-use wording handles never opened and future clocks",recentUse(0,1000).equals("尚未打开")&&recentUse(2000,1000).equals("刚刚")&&recentUse(1000,121000).equals("2 分钟前"));
      JSONObject recorded=J.obj("mode","手机网络","connected",true);
      check("Stopped or stale profiles never claim a current connected state",!networkStatus(recorded,false,true).contains("已连接")&&!networkStatus(recorded,true,false).contains("已连接"));
      check("Bulk work never creates a browser or starts a profile",ChatSession.peek()==null&&launches==initialLaunches);
      try(SQLiteDatabase legacy=SQLiteDatabase.create(null)){
        legacy.execSQL("CREATE TABLE environments(slot INTEGER PRIMARY KEY,name TEXT,created INTEGER,draft TEXT,pid INTEGER,seen INTEGER,connected INTEGER,waiting INTEGER,mode TEXT,privacy INTEGER,opened INTEGER,favorite INTEGER,problem TEXT,page TEXT)");
        legacy.execSQL("CREATE TABLE app_settings(name TEXT PRIMARY KEY,value TEXT NOT NULL)");
        legacy.execSQL("INSERT INTO environments VALUES(0,'迁移保留',1,'{\"name\":\"旧草稿\"}',0,0,0,0,'手机网络',1,123,1,'','原网页')");
        catalog.onUpgrade(legacy,3,4);
        try(android.database.Cursor row=legacy.rawQuery("SELECT name,draft,opened,favorite,group_name,notes FROM environments",null)){
          row.moveToFirst();check("v3 upgrade preserves names, drafts, opened times, and favorites",row.getString(0).equals("迁移保留")&&row.getString(1).contains("旧草稿")&&row.getLong(2)==123&&row.getInt(3)==1&&row.getString(4).isEmpty()&&row.getString(5).isEmpty());
        }
      }
      sort=0;
    }catch(Exception error){check("Bulk regression completed without exception: "+error.getClass().getSimpleName(),false);}
  }

}
