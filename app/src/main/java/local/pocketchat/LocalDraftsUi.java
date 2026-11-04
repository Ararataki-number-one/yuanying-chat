package local.pocketchat;

import android.widget.*;
import org.json.*;
import java.util.concurrent.*;

/** Searchable recovery workbench. Saving and copying never write the website editor. */
final class LocalDraftsUi {
  static void show(MainActivity a){if(a.session!=null)new Workspace(a).show();}
  static final class Workspace {
    final MainActivity a;final ChatSession owner;final ReferenceUi.Modal dialog;
    final EditText search;final TextView feedback;final LinearLayout list;final Button save;
    final ExecutorService reader=LocalContinuityUi.reader("LocalDraftSearch");Future<?> reading;
    int request,limit=40;boolean closed,capturing;final Runnable refresh=this::read;
    Workspace(MainActivity a){
      this.a=a;owner=a.session;dialog=new ReferenceUi.Modal(a,"草稿救援");
      dialog.note("仅此环境的本机副本。搜索、预览或复制后手动粘贴，当前网页输入保持不变。");
      search=DesignUi.searchInput(dialog.body,"搜索草稿内容或来源");search.setContentDescription("搜索暂存草稿");
      save=DesignUi.button(a,"暂存当前网页输入",true,this::capture);dialog.body.addView(save,new LinearLayout.LayoutParams(-1,-2));
      feedback=LocalContinuityUi.status(a,dialog.body);list=DesignUi.column(a);dialog.body.addView(list);
      dialog.buttons("关闭",dialog::dismiss,"刷新副本",this::read);
      dialog.setOnDismissListener(d->close());dialog.root.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){public void onViewAttachedToWindow(android.view.View view){}public void onViewDetachedFromWindow(android.view.View view){close();}});
      LocalContinuityUi.watch(search,()->{limit=40;request++;a.handler.removeCallbacks(refresh);a.handler.postDelayed(refresh,180);});
    }
    boolean current(){return !closed&&dialog.isShowing()&&LocalContinuityUi.current(a,owner);}
    void close(){if(closed)return;closed=true;request++;a.handler.removeCallbacks(refresh);reader.shutdownNow();}
    void show(){dialog.show();read();}
    void read(){
      if(!current())return;final int token=++request,maximum=limit;final String query=search.getText().toString();
      boolean enabled=LocalDraftPolicy.enabled(owner.context);save.setEnabled(enabled&&!capturing);
      feedback.setText(enabled?"正在读取本机副本…":"本机草稿保存已关闭；已有副本仍可查看和复制。");
      if(reading!=null)reading.cancel(true);reading=reader.submit(()->{
        LocalContinuityStore.Drafts result;try{result=LocalContinuityStore.drafts(owner.context,query,maximum);}catch(RuntimeException unavailable){a.handler.post(()->{if(current()&&token==request)feedback.setText("本机副本暂时无法读取，可刷新重试。");});return;}
        a.handler.post(()->{if(!current()||token!=request)return;
          list.removeAllViews();feedback.setText((enabled?"": "本机草稿保存已关闭。")+(result.incomplete?"部分副本暂时无法读取，可刷新重试。":result.rows.size()+" 份匹配副本")+(result.more?" · 可继续加载":""));
          if(result.rows.isEmpty())DesignUi.note(list,query.trim().isEmpty()?"还没有暂存副本。可以先暂存当前网页输入；重新加载或恢复连接时留下的副本也会出现在这里。":"没有匹配的草稿，试试其他关键词。");
          for(LocalContinuityPolicy.Draft row:result.rows)LocalContinuityUi.row(a,list,LocalContinuityPolicy.preview(row.body,140),row.origin+" · "+LocalContinuityUi.time(row.created),()->detail(row));
          if(result.more)DesignUi.action(list,"加载更多副本",false,()->{limit+=40;read();});dialog.resize();
        });
      });
    }
    void detail(LocalContinuityPolicy.Draft row){
      if(!current())return;ReferenceUi.Modal detail=new ReferenceUi.Modal(a,"草稿副本");
      detail.note(row.origin+"\n"+LocalContinuityUi.time(row.created));detail.body.addView(LocalContinuityUi.text(a,row.body,14));
      TextView result=LocalContinuityUi.status(a,detail.body);result.setText("复制后手动粘贴。不会替换网页输入或发送消息。");
      detail.buttons("关闭",detail::dismiss,"复制全文",()->LocalContinuityUi.copy(a,owner,"暂存草稿",row.body,result));detail.show();
    }
    void capture(){
      if(!current()||capturing)return;
      if(!LocalDraftPolicy.enabled(owner.context)){feedback.setText("本机草稿保存已关闭，请先在环境偏好中开启。");return;}
      final String url=owner.web.getUrl();final long epoch=owner.navigationEpoch,revision=LocalDraftPolicy.revision(owner.context);
      if(!MainActivity.chatUrl(url)||!owner.web.hasVisibleDocument()){feedback.setText("当前网页尚不可读取，请等输入框出现后再暂存。");return;}
      capturing=true;save.setEnabled(false);feedback.setText("正在读取当前输入…");
      owner.asyncDriver("page-state",J.obj("expectedUrl",url),2500,page->{
        if(!current())return;
        if(epoch!=owner.navigationEpoch||!WebReplyObserver.same(url,owner.web.getUrl())||!WebReplyObserver.same(url,page.optString("url"))||!PageMemory.completeDraft(page)){
          capturing=false;save.setEnabled(LocalDraftPolicy.enabled(owner.context));feedback.setText("网页已变化或无法完整读取输入，未保存副本，请重试。");return;
        }
        String body=page.optString("draft");if(body.trim().isEmpty()){capturing=false;save.setEnabled(LocalDraftPolicy.enabled(owner.context));feedback.setText("当前输入为空，无需暂存。");return;}
        owner.webStore.worker.execute(()->{
          boolean complete;try{EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity(Profiles.slot(owner.context),owner.environmentGeneration,owner.environmentId);complete=ProfileCatalog.get(owner.context).withIdentity(identity,()->DraftArchive.get(owner.context).save(url,body,"手动暂存的网页输入",revision));}catch(Exception stale){complete=false;}final boolean saved=complete;
          a.handler.post(()->{if(!current())return;capturing=false;save.setEnabled(LocalDraftPolicy.enabled(owner.context));if(saved){read();feedback.setText("已暂存这次输入的副本，网页内容保持不变。");}else feedback.setText("暂存未完成或保存设置已变化，请保留网页中的输入后重试。");});
        });
      });
    }
  }
}
