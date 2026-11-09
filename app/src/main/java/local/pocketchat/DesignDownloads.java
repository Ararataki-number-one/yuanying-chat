package local.pocketchat;

import android.app.*;
import android.content.*;
import android.database.ContentObserver;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.text.DateFormat;
import java.util.*;

/** Shared download presentation keeps live rows in place while progress changes. */
final class DesignDownloads {
  /** The embedded workspace and the cross-window Activity share one page header. */
  static LinearLayout header(Activity a){
    LinearLayout heading=DesignUi.row(a);heading.setPadding(DesignUi.dp(a,22),DesignUi.dp(a,14),DesignUi.dp(a,18),DesignUi.dp(a,14));heading.setClipChildren(false);heading.setClipToPadding(false);
    LinearLayout copy=DesignUi.column(a);
    TextView title=DownloadWorkspaceStyle.text(a,"下载",ReferenceUi.PAGE_TITLE_SIZE,DesignUi.TEXT,true);title.setContentDescription("下载中心");
    if(Build.VERSION.SDK_INT>=28)title.setAccessibilityHeading(true);copy.addView(title);
    TextView subtitle=DownloadWorkspaceStyle.text(a,"文件与下载任务",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);subtitle.setPadding(0,DesignUi.dp(a,3),DesignUi.dp(a,6),0);copy.addView(subtitle);
    heading.addView(copy,new LinearLayout.LayoutParams(0,-2,1));
    Button folder=ReferenceUi.iconButton(a,"tray","保存位置",()->folder(a));folder.setBackground(DesignUi.glass(a,25));GlassMotion.press(folder,true);
    heading.addView(folder,new LinearLayout.LayoutParams(DesignUi.dp(a,50),DesignUi.dp(a,50)));
    return heading;
  }
  static JSONArray rows(Context c){return DownloadDisplaySnapshot.read(c);}
  static JSONArray ordered(JSONArray files,JSONArray tasks){
    return DownloadListPolicy.ordered(files,tasks);
  }
  static String key(JSONObject row){return DownloadListPolicy.key(row);}
  static boolean busy(String state){return DownloadListPolicy.busy(state);}
  static boolean matches(JSONObject row,int filter){return DownloadListPolicy.matches(row,filter);}
  static String timeLabel(JSONObject row){long time=row.optLong("time");if(time<=0)return "时间未记录";return ("saved".equals(row.optString("state"))?"保存于 ":"开始于 ")+DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT,Locale.getDefault()).format(new Date(time));}
  static String updateKey(Context context){Bundle b=AppUpdates.call(context,"status",null);return b.getString("state","")+":"+b.getLong("packageStoredBytes")+":"+b.getBoolean("packageDeleteRetry");}
  static void updatePackage(Activity a,LinearLayout box){updatePackage(a,box,AppUpdates.call(a,"status",null));}
  static void updatePackage(Activity a,LinearLayout box,Bundle update){
    long bytes=update.getLong("packageStoredBytes");
    if(bytes<=0&&!update.getBoolean("packageDeleteRetry"))return;
    LinearLayout row=DesignUi.row(a);TextView label=DownloadWorkspaceStyle.text(a,"更新安装包 · "+DownloadTasks.amount(bytes),ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);
    row.addView(label,new LinearLayout.LayoutParams(0,-2,1));Button manage=DesignUi.button(a,"管理",false,()->AppUpdates.open(a));manage.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(manage);manage.setContentDescription("管理更新安装包");
    row.addView(manage,new LinearLayout.LayoutParams(DesignUi.dp(a,64),DesignUi.dp(a,44)));box.addView(row,new LinearLayout.LayoutParams(-1,-2));
  }
  static void open(Activity a,JSONObject r,SavedFileActions actions){if("saved".equals(r.optString("state"))){actions.show(r);return;}int slot=r.optInt("slot");if(a instanceof MainActivity&&slot==Profiles.slot(a)){MainActivity main=(MainActivity)a;for(int i=0;i<main.downloads.tasks.rows.length();i++){JSONObject actual=main.downloads.tasks.rows.optJSONObject(i);if(actual.optString("id").equals(r.optString("id"))){main.downloads.taskActions(actual);return;}}}a.startActivity(new Intent(a,Profiles.activity(slot)).putExtra("openDownload",r.optString("id")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
  static void render(Activity a,LinearLayout box,int filter,java.util.function.IntConsumer choose,SavedFileActions actions){new Controller(a,box,filter,choose,actions);}

  /** One controller per visible workspace; byte changes never replace its scroll view. */
  static final class Controller {
    final Activity a;final LinearLayout box,packages,list,empty;final java.util.function.IntConsumer choose;final SavedFileActions actions;
    final Map<String,Row> views=new LinkedHashMap<>();int filter=-1;String packageKey="";LinearLayout tabs;
    DownloadQuery query;final android.content.SharedPreferences preferences;final EditText search;
    final Button scopeButton,kindButton,sortButton,collectButton,basketButton;final DownloadCollection collection;final DownloadCollectionSession.State collectionSession;
    final Button toolsButton;final LinearLayout toolsPanel;final TextView toolSummary,sectionLabel;boolean toolsExpanded;
    final Map<String,String> scopes=new LinkedHashMap<>();boolean collecting;String collectionNotice="",emptyDiscoveryKey="";
    final Handler discoveryHandler=new Handler(Looper.getMainLooper());final Runnable discovery=()->refresh(this.requestedFilter);
    final DownloadRefreshUi refreshUi;Map<Integer,String> preparedNames;Map<String,String> preparedTimes,preparedOwners;int requestedFilter;
    final LinearLayout paging;final TextView pageLabel;final Button previous,next,latest;
    final Map<Integer,String> anchors=new HashMap<>();final Map<String,Integer> scrollStates=new HashMap<>();
    DownloadDisplayCache.Page prepared;SavedDownloadMetadata.Watch metadata;boolean attached=true,visible=true;long epoch;
    final DownloadReadGate reads=new DownloadReadGate();final DownloadDisplayCache.Scope requestScope=new DownloadDisplayCache.Scope();
    String anchor="",viewed="";boolean navigating;final ContentObserver changes;
    final android.view.ViewTreeObserver.OnScrollChangedListener scrolled=this::rememberViewed;
    void rememberViewed(){ScrollView scroll=scroll();if(scroll==null)return;int y=scroll.getScrollY();for(int i=0;i<list.getChildCount();i++){View card=list.getChildAt(i);if(list.getTop()+card.getTop()+card.getHeight()>y){Object key=card.getTag();if(key instanceof String)viewed=(String)key;break;}}}
    ScrollView scroll(){return box.getParent() instanceof ScrollView?(ScrollView)box.getParent():null;}
    String stateKey(){return requestedFilter+":"+query.key()+":"+anchor;}
    void saveScroll(){ScrollView scroll=scroll();if(scroll!=null)scrollStates.put(stateKey(),scroll.getScrollY());}
    void page(String selected){saveScroll();anchor=selected;viewed="";anchors.put(requestedFilter,anchor);navigating=true;epoch++;requestScope.invalidate();refresh(requestedFilter);}
    void setVisible(boolean value){visible=value;if(!value){saveScroll();epoch++;requestScope.invalidate();if(metadata!=null){metadata.close();metadata=null;}}else if(attached){if(metadata==null)metadata=SavedDownloadMetadata.watch(a);refresh(requestedFilter);}}
    void close(){if(!attached)return;discoveryHandler.removeCallbacksAndMessages(null);attached=false;setVisible(false);box.getViewTreeObserver().removeOnScrollChangedListener(scrolled);try{a.getContentResolver().unregisterContentObserver(changes);}catch(RuntimeException ignored){}}

    Controller(Activity a,LinearLayout box,int filter,java.util.function.IntConsumer choose,SavedFileActions actions){
      this.a=a;this.box=box;this.choose=choose;this.actions=actions;
      collectionSession=DownloadCollectionSession.get(a);collection=collectionSession.files;collecting=collectionSession.collecting;
      preferences=Profiles.global(a).getSharedPreferences("download-discovery",0);
      query=new DownloadQuery(preferences.getString("query",""),preferences.getString("owner",""),preferences.getInt("kind",0),preferences.getInt("sort",0));
      tabs=DownloadWorkspaceStyle.tabs(a,filter,choose);box.addView(tabs);
      LinearLayout searchRow=DesignUi.row(a),searchBox=DesignUi.column(a);searchRow.setPadding(0,DesignUi.dp(a,8),0,0);
      search=DesignUi.searchInput(searchBox,"搜索文件或环境");search.setContentDescription("搜索全部下载记录");search.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(200)});search.setText(query.text);DownloadWorkspaceStyle.search(search);
      searchRow.addView(searchBox,new LinearLayout.LayoutParams(0,-2,1));
      toolsButton=ReferenceUi.iconButton(a,"filter","展开下载工具",()->setToolsExpanded(!toolsExpanded));toolsButton.setBackground(DesignUi.glass(a,24));GlassMotion.press(toolsButton,true);
      LinearLayout.LayoutParams toolButtonParams=new LinearLayout.LayoutParams(DesignUi.dp(a,48),DesignUi.dp(a,48));toolButtonParams.leftMargin=DesignUi.dp(a,8);searchRow.addView(toolsButton,toolButtonParams);box.addView(searchRow);
      toolSummary=DownloadWorkspaceStyle.text(a,"",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);toolSummary.setMaxLines(2);toolSummary.setEllipsize(android.text.TextUtils.TruncateAt.END);toolSummary.setPadding(DesignUi.dp(a,4),DesignUi.dp(a,3),DesignUi.dp(a,4),DesignUi.dp(a,5));toolSummary.setVisibility(View.GONE);box.addView(toolSummary);
      toolsPanel=DesignUi.column(a);toolsPanel.setPadding(DesignUi.dp(a,12),DesignUi.dp(a,8),DesignUi.dp(a,12),DesignUi.dp(a,8));toolsPanel.setBackground(DownloadWorkspaceStyle.card(a));
      LinearLayout discoveryTools=DesignUi.row(a);if(a.getResources().getConfiguration().fontScale>=1.4f||a.getResources().getConfiguration().screenWidthDp<360)discoveryTools.setOrientation(LinearLayout.VERTICAL);
      scopeButton=DesignUi.button(a,"全部环境",false,this::chooseScope);kindButton=DesignUi.button(a,DownloadQuery.KINDS[query.kind],false,this::chooseKind);sortButton=DesignUi.button(a,DownloadQuery.SORTS[query.sort],false,this::chooseSort);
      int controlIndex=0;for(Button button:new Button[]{scopeButton,kindButton,sortButton}){button.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(button);LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(discoveryTools.getOrientation()==LinearLayout.VERTICAL?-1:0,-2,discoveryTools.getOrientation()==LinearLayout.VERTICAL?0:1);params.topMargin=DesignUi.dp(a,4);if(controlIndex++>0&&discoveryTools.getOrientation()!=LinearLayout.VERTICAL)params.leftMargin=DesignUi.dp(a,5);discoveryTools.addView(button,params);}toolsPanel.addView(discoveryTools);
      Button folder=ReferenceUi.link(a,"保存位置",()->folder(a));folder.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(folder);LinearLayout.LayoutParams folderParams=new LinearLayout.LayoutParams(-2,-2);folderParams.gravity=Gravity.END;toolsPanel.addView(folder,folderParams);
      toolsExpanded=!query.owner.isEmpty()||query.kind!=0||query.sort!=0;toolsPanel.setVisibility(toolsExpanded?View.VISIBLE:View.GONE);LinearLayout.LayoutParams toolsParams=new LinearLayout.LayoutParams(-1,-2);toolsParams.topMargin=DesignUi.dp(a,6);box.addView(toolsPanel,toolsParams);
      LinearLayout link=DesignUi.row(a);link.setPadding(DesignUi.dp(a,2),DesignUi.dp(a,4),0,0);boolean stackCollection=discoveryTools.getOrientation()==LinearLayout.VERTICAL;
      sectionLabel=DownloadWorkspaceStyle.text(a,"全部文件",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);sectionLabel.setMaxLines(1);sectionLabel.setEllipsize(android.text.TextUtils.TruncateAt.END);link.addView(sectionLabel,new LinearLayout.LayoutParams(0,-2,1));
      LinearLayout collectionTools=DesignUi.row(a);if(stackCollection)collectionTools.setOrientation(LinearLayout.VERTICAL);
      collectButton=ReferenceUi.link(a,"收集文件",()->{collecting=!collecting;syncCollection();});collectButton.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(collectButton);collectionTools.addView(collectButton);
      basketButton=ReferenceUi.link(a,"收集篮 · 0",this::showCollection);basketButton.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(basketButton);LinearLayout.LayoutParams basketParams=new LinearLayout.LayoutParams(-2,-2);basketParams.leftMargin=DesignUi.dp(a,10);collectionTools.addView(basketButton,basketParams);link.addView(collectionTools);box.addView(link);
      packages=DesignUi.column(a);box.addView(packages);list=DesignUi.column(a);box.addView(list);empty=DesignUi.column(a);box.addView(empty);
      paging=DesignUi.row(a);previous=DesignUi.button(a,"上一页",false,()->{if(prepared!=null&&!prepared.window.previous.isEmpty())page(prepared.window.previous);});next=DesignUi.button(a,"下一页",false,()->{if(prepared!=null&&!prepared.window.next.isEmpty())page(prepared.window.next);});pageLabel=DownloadWorkspaceStyle.text(a,"正在读取下载记录…",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);latest=DesignUi.button(a,"返回最新",false,()->page(""));paging.addView(previous);paging.addView(pageLabel,new LinearLayout.LayoutParams(0,-2,1));paging.addView(next);box.addView(paging);box.addView(latest);
      for(Button button:new Button[]{previous,next,latest}){button.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(button);}paging.setVisibility(View.GONE);latest.setVisibility(View.GONE);
      refreshUi=new DownloadRefreshUi(a,box,()->refresh(requestedFilter));
      changes=new ContentObserver(new Handler(Looper.getMainLooper())){@Override public void onChange(boolean self){DownloadLibraryChanges.revision.incrementAndGet();if(attached&&visible)refresh(requestedFilter);}};
      a.getContentResolver().registerContentObserver(DownloadLibraryChanges.uri(a),false,changes);
      // Another process may have changed the library while no workspace was attached.
      DownloadLibraryChanges.revision.incrementAndGet();
      box.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){public void onViewAttachedToWindow(View v){}public void onViewDetachedFromWindow(View v){close();}});
      box.getViewTreeObserver().addOnScrollChangedListener(scrolled);
      metadata=SavedDownloadMetadata.watch(a);this.filter=filter;requestedFilter=filter;
      search.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence text,int start,int count,int after){}public void afterTextChanged(android.text.Editable value){}public void onTextChanged(CharSequence text,int start,int before,int count){changeQuery(query.text(text.toString()),true);}});
      setToolsExpanded(toolsExpanded);syncCollection();refresh(filter);
    }
    void changeQuery(DownloadQuery next,boolean debounce){
      if(next.key().equals(query.key()))return;saveScroll();query=next;anchor="";viewed="";anchors.clear();navigating=true;epoch++;requestScope.invalidate();emptyDiscoveryKey="";empty.removeAllViews();
      preferences.edit().putString("query",query.text).putString("owner",query.owner).putInt("kind",query.kind).putInt("sort",query.sort).apply();discoveryLabels();
      discoveryHandler.removeCallbacks(discovery);if(debounce)discoveryHandler.postDelayed(discovery,220);else refresh(requestedFilter);
    }
    void setToolsExpanded(boolean expanded){toolsExpanded=expanded;Row.visible(toolsPanel,expanded);toolsButton.setContentDescription(expanded?"收起下载工具":"展开下载工具");toolsButton.setTooltipText(expanded?"收起下载工具":"展开下载工具");discoveryLabels();}
    void discoveryLabels(){
      Row.text(scopeButton,scopes.getOrDefault(query.owner,query.owner.isEmpty()?"全部环境":"原环境文件"));Row.text(kindButton,DownloadQuery.KINDS[query.kind]);Row.text(sortButton,DownloadQuery.SORTS[query.sort]);if(latest!=null)Row.text(latest,query.sort<2?"返回最新":"回到开头");
      List<String> selected=new ArrayList<>();if(!query.owner.isEmpty())selected.add(scopeButton.getText().toString());if(query.kind!=0)selected.add(DownloadQuery.KINDS[query.kind]);if(query.sort!=0)selected.add(DownloadQuery.SORTS[query.sort]);
      Row.text(toolSummary,String.join(" · ",selected));Row.visible(toolSummary,!toolsExpanded&&!selected.isEmpty());toolsButton.setSelected(toolsExpanded||!selected.isEmpty());
    }
    void chooseScope(){
      List<String> keys=new ArrayList<>(scopes.keySet());if(keys.isEmpty())keys.add("");String[] names=new String[keys.size()];for(int i=0;i<keys.size();i++)names[i]=scopes.getOrDefault(keys.get(i),"全部环境");
      AppAppearance.dialog(a).setTitle("文件所属环境").setSingleChoiceItems(names,keys.indexOf(query.owner),(dialog,which)->{dialog.dismiss();changeQuery(query.owner(keys.get(which)),false);}).setNegativeButton("取消",null).show();
    }
    void chooseKind(){AppAppearance.dialog(a).setTitle("文件类型").setSingleChoiceItems(DownloadQuery.KINDS,query.kind,(dialog,which)->{dialog.dismiss();changeQuery(query.kind(which),false);}).setNegativeButton("取消",null).show();}
    void chooseSort(){AppAppearance.dialog(a).setTitle("文件排序").setSingleChoiceItems(DownloadQuery.SORTS,query.sort,(dialog,which)->{dialog.dismiss();changeQuery(query.sort(which),false);}).setNegativeButton("取消",null).show();}
    void toggleCollection(JSONObject row){if(actions.busy){syncCollection();return;}collectionNotice="";if(!collection.toggle(row))SavedFileActions.problem(a,"最多收集 "+DownloadCollection.LIMIT+" 个已完成文件；同一文件不能重复加入");syncCollection();}
    void syncCollection(){collectionSession.collecting=collecting;Row.text(collectButton,collecting?"完成选择":"收集文件");Row.text(basketButton,"收集篮 · "+collection.size());Row.visible(basketButton,collecting||collection.size()>0);if(collectButton.isEnabled()==actions.busy)collectButton.setEnabled(!actions.busy);if(basketButton.isEnabled()==actions.busy)basketButton.setEnabled(!actions.busy);for(Row row:views.values())row.selection(collecting,collection.size()>0&&collection.containsKey(row.collectionKey()),!actions.busy,this);}
    void decorateDiscoveryPage(JSONArray rows){syncCollection();if(rows.length()==0&&query.restricted()){String key=requestedFilter+":"+query.key();if(!key.equals(emptyDiscoveryKey)){emptyDiscoveryKey=key;empty.removeAllViews();DownloadWorkspaceStyle.empty(empty,"没有匹配的文件","试试其他关键词，或清除环境与类型筛选。","清除搜索与筛选",()->{changeQuery(DownloadQuery.all(),false);search.setText("");choose.accept(0);});}}else emptyDiscoveryKey="";}
    void showCollection(){
      LinearLayout content=DesignUi.column(a);int pad=DesignUi.dp(a,18);content.setPadding(pad,pad,pad,pad);JSONArray selected=collection.snapshot();
      DesignUi.note(content,selected.length()==0?"点击“收集文件”，可跨页、跨筛选选择已保存文件，一次分享。":"已收集 "+selected.length()+" / "+DownloadCollection.LIMIT+" 个文件。搜索或翻页会保留选择；分享前会核对文件是否仍可读取。");
      if(!collectionNotice.isEmpty())DesignUi.note(content,collectionNotice);final AlertDialog[] holder={null};
      for(int i=0;i<selected.length();i++){JSONObject value=selected.optJSONObject(i);LinearLayout row=DesignUi.row(a);TextView label=DownloadWorkspaceStyle.text(a,DownloadMetadataValues.name(value),ReferenceUi.BODY_SIZE,DesignUi.TEXT,false);label.setMaxLines(2);row.addView(label,new LinearLayout.LayoutParams(0,-2,1));Button remove=DesignUi.button(a,"移除",false,()->{collection.toggle(value);syncCollection();holder[0].dismiss();showCollection();});remove.setTextSize(ReferenceUi.ACTION_SIZE);DownloadWorkspaceStyle.readable(remove);row.addView(remove);content.addView(row);}
      Button pageFiles=DesignUi.button(a,"加入本页已完成文件",false,()->{int added=0,skipped=0;for(Row row:views.values())if(DownloadCollection.eligible(row.value)&&!collection.contains(row.value)){if(collection.toggle(row.value))added++;else skipped++;}collectionNotice="本次加入 "+added+" 个文件"+(skipped>0?"；"+skipped+" 个未加入（最多 "+DownloadCollection.LIMIT+" 个，同一文件不重复加入）":"");collecting=true;syncCollection();holder[0].dismiss();showCollection();});content.addView(pageFiles);
      ScrollView overflow=new ScrollView(a);overflow.addView(content);AlertDialog dialog=AppAppearance.dialog(a).setTitle("文件收集篮").setView(overflow).setNegativeButton("继续选择",(d,w)->{collecting=true;syncCollection();}).setNeutralButton("清空收集篮",(d,w)->{collection.clear();syncCollection();}).setPositiveButton("分享 "+selected.length()+" 个文件",null).create();holder[0]=dialog;dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(selected.length()>0&&!actions.busy);
      dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{dialog.dismiss();DownloadCollectionShare.share(a,actions,selected,this::syncCollection);syncCollection();});
    }
    void saveState(Bundle state){state.putString("downloadCollection",collection.snapshot().toString());state.putBoolean("downloadCollecting",collecting);state.putBoolean("downloadToolsExpanded",toolsExpanded);}
    void restoreState(Bundle state){if(state==null)return;try{collection.restore(new JSONArray(state.getString("downloadCollection","[]")));}catch(JSONException invalid){collection.clear();}collecting=state.getBoolean("downloadCollecting");setToolsExpanded(state.getBoolean("downloadToolsExpanded",toolsExpanded));syncCollection();}
    void refresh(int selected){
      if(!attached||!visible)return;
      if(selected!=requestedFilter){saveScroll();anchors.put(requestedFilter,anchor);requestedFilter=selected;anchor=anchors.getOrDefault(selected,"");viewed="";navigating=true;epoch++;requestScope.invalidate();}
      if(!reads.begin(epoch,DownloadLibraryChanges.revision.get()))return;final long request=epoch;final int chosen=requestedFilter;final String selectedAnchor=anchor;
      DownloadDisplayCache.request(a,chosen,selectedAnchor,viewed,query,requestScope,page->{
        reads.complete();if(!attached||!visible)return;
        if(request==epoch&&chosen==requestedFilter&&page.currentFormat()){
          prepared=page;if(!scopes.equals(page.scopes)){scopes.clear();scopes.putAll(page.scopes);}discoveryLabels();preparedNames=page.names;preparedTimes=page.times;preparedOwners=page.environmentLabels;
          try{apply(page.window.rows,chosen,System.currentTimeMillis());decorateDiscoveryPage(page.window.rows);}finally{preparedNames=null;preparedTimes=null;preparedOwners=null;}
          if(page.window.rows.length()>0){anchor=key(page.window.rows.optJSONObject(0));anchors.put(chosen,anchor);if(viewed.isEmpty())viewed=anchor;}
          String key=page.update.getString("state","")+":"+page.update.getLong("packageStoredBytes")+":"+page.update.getBoolean("packageDeleteRetry");
          if(!key.equals(packageKey)){packages.removeAllViews();updatePackage(a,packages,page.update);packageKey=key;}
          if(previous.isEnabled()==page.window.previous.isEmpty())previous.setEnabled(!page.window.previous.isEmpty());if(next.isEnabled()==page.window.next.isEmpty())next.setEnabled(!page.window.next.isEmpty());Row.text(pageLabel,page.window.total==0?"0 条记录":(page.window.start+1)+"–"+(page.window.start+page.window.rows.length())+" / "+page.window.total);Row.visible(latest,page.window.newer);refreshUi.clear();
          Row.visible(paging,!page.window.previous.isEmpty()||!page.window.next.isEmpty());Row.text(sectionLabel,new String[]{"全部文件","进行中的任务","已完成的文件","失败的任务"}[chosen]+" · "+page.window.total);Row.visible(collectButton,page.window.total>0||collecting||collection.size()>0);
          if(navigating){ScrollView scroll=scroll();int restore=scrollStates.getOrDefault(stateKey(),0);if(scroll!=null)scroll.post(()->scroll.scrollTo(0,restore));navigating=false;}
        }
        if(reads.replay(epoch))refresh(requestedFilter);
      },error->{reads.complete();if(!attached||!visible)return;if(request==epoch&&!(error instanceof java.util.concurrent.CancellationException))refreshUi.failed();if(reads.replay(epoch))refresh(requestedFilter);});
    }
    void apply(JSONArray data,int selected,long now){
      boolean changedFilter=selected!=filter;if(changedFilter){filter=selected;box.removeView(tabs);tabs=DownloadWorkspaceStyle.tabs(a,filter,choose);box.addView(tabs,0);}
      ScrollView scroll=box.getParent() instanceof ScrollView?(ScrollView)box.getParent():null;int oldY=scroll==null?0:scroll.getScrollY();
      View anchor=null;int anchorTop=0;if(oldY>0&&!changedFilter){for(int i=0;i<list.getChildCount();i++){View card=list.getChildAt(i);int top=list.getTop()+card.getTop();if(top+card.getHeight()>oldY){anchor=card;anchorTop=top-oldY;break;}}}
      Set<String> visible=new HashSet<>();int index=0;boolean structure=changedFilter,rebound=false;Map<String,String> environmentLabels=preparedOwners;DownloadRowBinding.Frame frame=new DownloadRowBinding.Frame(DesignUi.RED,DesignUi.CYAN,DesignUi.GREEN);
      for(int i=0;i<data.length()&&i<DownloadPageWindow.LIMIT;i++){
        JSONObject value=data.optJSONObject(i);if(value==null||!matches(value,filter))continue;String key=key(value);if(!visible.add(key))continue;
        Row row=views.get(key);if(row==null){row=new Row(a,actions);row.card.setTag(key);views.put(key,row);}String environment=environmentLabels==null?DownloadOwnerLabels.UNKNOWN:environmentLabels.getOrDefault(key,DownloadOwnerLabels.UNKNOWN);
        row.value=value;if(preparedTimes!=null)row.binding.preparedTime(value,preparedTimes.get(key));DownloadRowBinding.Stamp next=row.binding.next(value,now,environment,frame);if(next!=null){row.bind(value,now,environment);row.binding.applied(next);rebound=true;}
        if(index>=list.getChildCount()||list.getChildAt(index)!=row.card){structure=true;if(row.card.getParent()==list)list.removeView(row.card);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=DesignUi.dp(a,10);list.addView(row.card,index,p);}index++;
      }
      for(Iterator<Map.Entry<String,Row>> it=views.entrySet().iterator();it.hasNext();){Map.Entry<String,Row> entry=it.next();if(!visible.contains(entry.getKey())){list.removeView(entry.getValue().card);it.remove();structure=true;}}
      if(index==0){if(empty.getChildCount()==0||changedFilter){empty.removeAllViews();String[] titles={"还没有下载文件","没有进行中的下载","还没有已完成的下载","没有失败的下载"};String[] details={"在会话中保存文件后，可在这里打开、分享或整理。","开始下载后，这里会显示实际进度。","文件保存完成后会自动出现在这里。","下载失败时，这里会显示原因和可用操作。"};DownloadWorkspaceStyle.empty(empty,titles[filter],details[filter],"查看全部下载",filter==0?null:()->choose.accept(0));}}else if(empty.getChildCount()>0)empty.removeAllViews();
      if(scroll!=null&&(structure||rebound)){View kept=anchor;int offset=anchorTop;scroll.post(()->{if(changedFilter)scroll.scrollTo(0,0);else if(kept!=null&&kept.getParent()==list)scroll.scrollTo(0,list.getTop()+kept.getTop()-offset);else scroll.scrollTo(0,oldY);});}
    }
  }
  static final class Row {
    final Activity a;final LinearLayout card;final ImageView icon;final TextView name,status,stateLabel,time,progressText,reason,stale,location,arrow;final Button menu;final ProgressBar progress;final CheckBox collected;boolean syncingSelection,selectionKnown,selectionVisible,selectionChecked,selectionEnabled;Controller selectionOwner;JSONObject value,selectionKeyRow;String appearance="",selectionLabel="",selectedKey="";
    final DownloadRowBinding binding=new DownloadRowBinding();
    Row(Activity a,SavedFileActions actions){
      this.a=a;card=DesignUi.card(a);card.setPadding(DesignUi.dp(a,16),DesignUi.dp(a,12),DesignUi.dp(a,12),DesignUi.dp(a,12));card.setBackground(DownloadWorkspaceStyle.card(a));
      LinearLayout top=DesignUi.row(a);collected=new CheckBox(a);collected.setVisibility(View.GONE);top.addView(collected,new LinearLayout.LayoutParams(DesignUi.dp(a,48),DesignUi.dp(a,48)));
      icon=DesignUi.icon(a,"download",DesignUi.GREEN,40);icon.setPadding(DesignUi.dp(a,9),DesignUi.dp(a,9),DesignUi.dp(a,9),DesignUi.dp(a,9));icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);top.addView(icon);
      LinearLayout labels=DesignUi.column(a);labels.setPadding(DesignUi.dp(a,12),0,DesignUi.dp(a,4),0);
      name=DownloadWorkspaceStyle.text(a,"",ReferenceUi.CARD_TITLE_SIZE,DesignUi.TEXT,true);name.setMaxLines(2);name.setEllipsize(android.text.TextUtils.TruncateAt.END);labels.addView(name);
      status=DownloadWorkspaceStyle.text(a,"",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);status.setMaxLines(2);status.setEllipsize(android.text.TextUtils.TruncateAt.END);status.setPadding(0,DesignUi.dp(a,4),0,0);labels.addView(status);top.addView(labels,new LinearLayout.LayoutParams(0,-2,1));
      menu=ReferenceUi.more(a,()->actions.show(value));top.addView(menu,new LinearLayout.LayoutParams(DesignUi.dp(a,48),DesignUi.dp(a,48)));
      arrow=DownloadWorkspaceStyle.text(a,"",22,DesignUi.MUTED,false);Ui.Icon disclosure=new Ui.Icon("chevron-right",DesignUi.MUTED);disclosure.setBounds(0,0,DesignUi.dp(a,18),DesignUi.dp(a,18));arrow.setCompoundDrawables(disclosure,null,null,null);arrow.setGravity(Gravity.CENTER);arrow.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);top.addView(arrow,new LinearLayout.LayoutParams(DesignUi.dp(a,48),DesignUi.dp(a,48)));card.addView(top);
      LinearLayout date=DesignUi.row(a);date.setPadding(0,DesignUi.dp(a,6),DesignUi.dp(a,4),0);
      time=DownloadWorkspaceStyle.text(a,"",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);time.setMaxLines(2);date.addView(time,new LinearLayout.LayoutParams(0,-2,1));
      stateLabel=DownloadWorkspaceStyle.text(a,"",ReferenceUi.STATUS_SIZE,DesignUi.MUTED,false);stateLabel.setMaxLines(1);stateLabel.setPadding(DesignUi.dp(a,8),DesignUi.dp(a,3),DesignUi.dp(a,8),DesignUi.dp(a,3));LinearLayout.LayoutParams stateParams=new LinearLayout.LayoutParams(-2,-2);stateParams.leftMargin=DesignUi.dp(a,8);date.addView(stateLabel,stateParams);card.addView(date);
      progress=new ProgressBar(a,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);progress.setProgressTintList(android.content.res.ColorStateList.valueOf(DesignUi.BLUE));progress.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(DesignUi.LINE));LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,DesignUi.dp(a,4));pp.topMargin=DesignUi.dp(a,10);card.addView(progress,pp);
      progressText=DownloadWorkspaceStyle.text(a,"",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);progressText.setPadding(0,DesignUi.dp(a,6),0,0);card.addView(progressText);
      reason=DownloadWorkspaceStyle.text(a,"",ReferenceUi.SECONDARY_SIZE,DesignUi.RED,false);reason.setPadding(0,DesignUi.dp(a,5),0,0);reason.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);card.addView(reason);
      stale=DownloadWorkspaceStyle.text(a,"记录待刷新，点按核对任务",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);stale.setPadding(0,DesignUi.dp(a,5),0,0);card.addView(stale);
      location=DownloadWorkspaceStyle.text(a,"",ReferenceUi.SECONDARY_SIZE,DesignUi.MUTED,false);location.setMaxLines(3);location.setPadding(0,DesignUi.dp(a,8),0,0);
      card.setClickable(true);card.setFocusable(true);card.setOnClickListener(v->{if(selectionOwner!=null&&selectionOwner.collecting&&DownloadCollection.eligible(value))selectionOwner.toggleCollection(value);else open(a,value,actions);});collected.setOnCheckedChangeListener((button,isChecked)->{if(!syncingSelection&&selectionOwner!=null)selectionOwner.toggleCollection(value);});
    }
    String collectionKey(){if(value!=selectionKeyRow){selectionKeyRow=value;selectedKey=value==null?"":DownloadCollection.key(value);}return selectedKey;}
    void selection(boolean mode,boolean checked,boolean enabled,Controller owner){
      selectionOwner=owner;boolean shown=mode&&DownloadCollection.eligible(value);syncingSelection=true;
      if(!selectionKnown||selectionVisible!=shown){selectionVisible=shown;collected.setVisibility(shown?View.VISIBLE:View.GONE);icon.setVisibility(shown?View.GONE:View.VISIBLE);}
      if(!selectionKnown||collected.isChecked()!=checked){selectionChecked=checked;collected.setChecked(checked);}
      if(!selectionKnown||selectionEnabled!=enabled){selectionEnabled=enabled;collected.setEnabled(enabled);}
      String label=value==null?"":DownloadMetadataValues.name(value);if(!selectionKnown||!selectionLabel.equals(label)){selectionLabel=label;collected.setContentDescription("收集文件 "+label);}
      selectionKnown=true;syncingSelection=false;
    }
    void bind(JSONObject row,long now,String environmentName){
      value=row;String state=row.optString("state");boolean saved="saved".equals(state);int color="failed".equals(state)?DesignUi.RED:saved?DownloadWorkspaceStyle.savedColor(DownloadMetadataValues.name(row)):"paused".equals(state)?DesignUi.MUTED:DesignUi.GREEN;
      String glyph=saved?DownloadWorkspaceStyle.savedGlyph(DownloadMetadataValues.name(row)):"paused".equals(state)?"pause":"failed".equals(state)?"info":"download";
      int stateColor=saved?DesignUi.GREEN:color;String next=glyph+":"+color+":"+stateColor;if(!next.equals(appearance)){appearance=next;icon.setImageDrawable(new Ui.Icon(glyph,color));icon.setBackground(DesignUi.surface(a,(color&0xffffff)|0x0c000000,12,android.graphics.Color.TRANSPARENT));arrow.setTextColor(color);stateLabel.setTextColor(stateColor);stateLabel.setBackground(DesignUi.surface(a,(stateColor&0xffffff)|0x0c000000,10,android.graphics.Color.TRANSPARENT));}
      text(name,DownloadMetadataValues.name(row));text(status,environmentName+(saved?" · "+DownloadTasks.amount(DownloadMetadataValues.bytes(row)):""));text(stateLabel,DownloadTasks.label(state));text(time,binding.time(row,()->timeLabel(row)));String description="管理 "+DownloadMetadataValues.name(row);if(!android.text.TextUtils.equals(menu.getContentDescription(),description))menu.setContentDescription(description);visible(menu,saved);visible(arrow,!saved);
      boolean failed="failed".equals(state),hasReceived=row.optLong("received")>0;
      visible(progress,!saved&&(!failed||(hasReceived&&row.optLong("total",-1)>0)));visible(progressText,!saved&&(!failed||hasReceived));visible(reason,!saved&&!row.optString("reason").isEmpty());visible(stale,!saved&&busy(state)&&row.optLong("updated")>0&&now-row.optLong("updated")>15000);visible(location,false);
      long total=row.optLong("total",-1),received=row.optLong("received");boolean indefinite=total<=0&&busy(state);if(progress.isIndeterminate()!=indefinite)progress.setIndeterminate(indefinite);int percent=total>0?(int)Math.min(100,received*100/total):0;if(progress.getProgress()!=percent)progress.setProgress(percent);text(progressText,DownloadTasks.progress(row));text(reason,row.optString("reason"));
    }
    static void text(TextView view,String value){if(!android.text.TextUtils.equals(view.getText(),value))view.setText(value);}
    static void visible(View view,boolean value){int visibility=value?View.VISIBLE:View.GONE;if(view.getVisibility()!=visibility)view.setVisibility(visibility);}
  }
  static AlertDialog folder(Activity a){return DesignUi.message(a,"保存位置","默认位置："+(Build.VERSION.SDK_INT>=29?"Download/元婴期院士/窗口_编号/":"各窗口的应用内文件目录")+"\n\n点文件右侧菜单可打开、分享、另存为或删除。每个文件菜单的“详细信息”显示实际保存位置，并可复制位置。");}
}
