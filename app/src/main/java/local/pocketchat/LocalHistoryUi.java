package local.pocketchat;

import android.widget.*;
import java.util.*;
import java.util.concurrent.*;

/** Offline, read-only search over messages the current environment already observed. */
final class LocalHistoryUi {
  static void show(MainActivity a){if(a.session!=null)new Workspace(a).show();}
  static final class Workspace {
    final MainActivity a;final ChatSession owner;final ReferenceUi.Modal dialog;
    final EditText search;final TextView feedback;final LinearLayout list;
    final ExecutorService reader=LocalContinuityUi.reader("LocalHistorySearch");Future<?> reading;
    final LocalContinuityStore.HistorySession history;long revision;int request,limit=30;boolean closed;final Runnable refresh=this::read;
    Workspace(MainActivity a){
      this.a=a;owner=a.session;history=new LocalContinuityStore.HistorySession(owner.context);dialog=new ReferenceUi.Modal(a,"本机离线阅读");
      dialog.note("搜索此环境已在网页中显示并保存的文字。可离线阅读和复制；未打开的历史、附件内容和网站后续变化可能不在副本中。");
      search=DesignUi.searchInput(dialog.body,"搜索对话标题或消息全文");search.setContentDescription("搜索本机对话内容");
      feedback=LocalContinuityUi.status(a,dialog.body);list=DesignUi.column(a);dialog.body.addView(list);
      dialog.buttons("关闭",dialog::dismiss,"刷新本机记录",()->{revision++;read();});
      dialog.setOnDismissListener(d->close());dialog.root.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){public void onViewAttachedToWindow(android.view.View view){}public void onViewDetachedFromWindow(android.view.View view){close();}});
      LocalContinuityUi.watch(search,()->{limit=30;request++;a.handler.removeCallbacks(refresh);a.handler.postDelayed(refresh,180);});
    }
    boolean current(){return !closed&&dialog.isShowing()&&LocalContinuityUi.current(a,owner);}
    void close(){if(closed)return;closed=true;request++;a.handler.removeCallbacks(refresh);reader.shutdownNow();}
    void show(){dialog.show();read();}
    void read(){
      if(!current())return;final int token=++request,maximum=limit;final long version=revision;final String query=search.getText().toString();feedback.setText("正在搜索本机内容…");
      if(reading!=null)reading.cancel(true);reading=reader.submit(()->{
        LocalContinuityStore.History result;try{history.revision(version);result=history.search(query,maximum);}catch(RuntimeException unavailable){a.handler.post(()->{if(current()&&token==request)feedback.setText("本机记录暂时无法读取，可刷新重试。");});return;}
        a.handler.post(()->{if(!current()||token!=request)return;list.removeAllViews();
          feedback.setText((result.incomplete?"部分本机记录暂时无法读取，可刷新重试。":result.rows.size()+" 个匹配对话")+(result.more?" · 可继续加载":""));
          if(result.rows.isEmpty())DesignUi.note(list,query.trim().isEmpty()?"还没有保存的网页文字。打开并阅读一段对话后，已显示的文字会按原有保存流程留在本机。":"没有匹配的本机内容，试试其他关键词。");
          for(LocalContinuityStore.Conversation row:result.rows){
            LocalContinuityUi.row(a,list,row.title,row.messages.size()+" 条文字消息 · "+LocalContinuityUi.time(row.touched)+"\n"+row.snippet,()->new Reader(a,owner,row,row.readerQuery).show());
          }
          if(result.more)DesignUi.action(list,"加载更多本机对话",false,()->{limit+=30;read();});dialog.resize();
        });
      });
    }
  }
  static final class Reader {
    static final int PAGE=16;
    final MainActivity a;final ChatSession owner;final LocalContinuityStore.Conversation conversation;final ReferenceUi.Modal dialog;
    final EditText search;final TextView feedback;final LinearLayout messages;final Button previous,next;int start,request;boolean closed;
    final ExecutorService reader=LocalContinuityUi.reader("LocalMessageSearch");Future<?> reading;final Runnable refresh=this::render;
    Reader(MainActivity a,ChatSession owner,LocalContinuityStore.Conversation conversation,String query){
      this.a=a;this.owner=owner;this.conversation=conversation;dialog=new ReferenceUi.Modal(a,"本机对话副本");dialog.note(conversation.title+"\n保存时间："+LocalContinuityUi.time(conversation.touched));
      search=DesignUi.searchInput(dialog.body,"在这段对话中查找");search.setContentDescription("查找对话中的文字");
      feedback=LocalContinuityUi.status(a,dialog.body);messages=DesignUi.column(a);dialog.body.addView(messages);
      LinearLayout pages=DesignUi.row(a);previous=DesignUi.button(a,"上一页",false,()->{start=Math.max(0,start-PAGE);render();});next=DesignUi.button(a,"下一页",false,()->{start+=PAGE;render();});pages.addView(previous,new LinearLayout.LayoutParams(0,-2,1));pages.addView(next,new LinearLayout.LayoutParams(0,-2,1));dialog.body.addView(pages);
      dialog.buttons("关闭",dialog::dismiss,"复制整段对话",this::copyConversation);search.setText(query);
      LocalContinuityUi.watch(search,()->{start=0;request++;a.handler.removeCallbacks(refresh);a.handler.postDelayed(refresh,180);});
      dialog.setOnDismissListener(d->close());dialog.root.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){public void onViewAttachedToWindow(android.view.View view){}public void onViewDetachedFromWindow(android.view.View view){close();}});
    }
    void close(){if(closed)return;closed=true;request++;a.handler.removeCallbacks(refresh);reader.shutdownNow();}
    void show(){dialog.show();render();}
    void render(){
      if(closed||!LocalContinuityUi.current(a,owner)||!dialog.isShowing())return;
      final int token=++request,from=start;String query=search.getText().toString();feedback.setText("正在查找本机文字…");
      if(reading!=null)reading.cancel(true);reading=reader.submit(()->{List<LocalContinuityPolicy.Message> rows=conversation.index.search(query);a.handler.post(()->{if(!closed&&token==request&&LocalContinuityUi.current(a,owner)&&dialog.isShowing())apply(rows,from);});});
    }
    void apply(List<LocalContinuityPolicy.Message> rows,int from){
      start=from;if(start>=rows.size())start=Math.max(0,((rows.size()-1)/PAGE)*PAGE);int end=Math.min(rows.size(),start+PAGE);messages.removeAllViews();
      feedback.setText(rows.isEmpty()?"没有匹配的文字消息":(start+1)+"–"+end+" / "+rows.size()+" 条文字消息");previous.setEnabled(start>0);next.setEnabled(end<rows.size());
      for(int i=start;i<end;i++){LocalContinuityPolicy.Message row=rows.get(i);LocalContinuityUi.row(a,messages,LocalContinuityPolicy.role(row.role)+" · 第 "+row.position+" 条",LocalContinuityPolicy.preview(row.text,500),()->message(row));}
      dialog.resize();dialog.scroll.post(()->dialog.scroll.scrollTo(0,0));
    }
    void copyConversation(){
      if(!LocalContinuityUi.current(a,owner))return;
      if(!LocalContinuityPolicy.copyFits(conversation.title,conversation.messages,180000)){feedback.setText("这段对话较长，请打开单条消息后复制所需文字。");return;}
      LocalContinuityUi.copy(a,owner,"本机对话副本",LocalContinuityPolicy.transcript(conversation.title,conversation.messages),feedback);
    }
    void message(LocalContinuityPolicy.Message row){
      if(!LocalContinuityUi.current(a,owner))return;ReferenceUi.Modal detail=new ReferenceUi.Modal(a,LocalContinuityPolicy.role(row.role)+" · 第 "+row.position+" 条");
      detail.body.addView(LocalContinuityUi.text(a,row.text,15));TextView result=LocalContinuityUi.status(a,detail.body);result.setText("这是本机保存的文字副本。");detail.buttons("关闭",detail::dismiss,"复制这条消息",()->LocalContinuityUi.copy(a,owner,"本机消息副本",row.text,result));detail.show();
    }
  }
}
