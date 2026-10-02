package local.pocketchat;

import android.webkit.CookieManager;
import org.json.*;
import java.util.*;

/** Bounded in-process snapshots, scoped to applied network profile and cookies. */
final class PageMemory {
  final ChatSession session;final LinkedHashMap<String,JSONObject> pages=new LinkedHashMap<>(16,0.75f,true);long serial;
  boolean restorePending;JSONObject lastRestore=new JSONObject();
  PageMemory(ChatSession s){session=s;}
  String scope(){try{return session.appliedIdentity+":"+NativeNetwork.hash(String.valueOf(CookieManager.getInstance().getCookie(MainActivity.ORIGIN)));}catch(Exception e){return "";}}
  static String address(String url){try{android.net.Uri u=android.net.Uri.parse(url);return u.getScheme()+"://"+u.getHost()+u.getPath();}catch(Exception e){return "";}}
  String document(String url){JSONObject state=pages.get(scope()+"|"+address(url));return state==null?"":state.optString("documentId");}
  String content(String url){JSONObject state=pages.get(scope()+"|"+address(url));return state==null?"":state.optString("contentKey");}
  void remember(String namespace,String url,JSONObject state){if(state==null||!state.optBoolean("ok")||!namespace.equals(scope())||!WebReplyObserver.same(url,state.optString("url")))return;pages.put(namespace+"|"+address(url),state);while(pages.size()>8)pages.remove(pages.keySet().iterator().next());}
  void capture(Runnable done){String url=session.web.getUrl(),namespace=scope();long request=++serial;
    if(!MainActivity.chatUrl(url)||namespace.isEmpty()){done.run();return;}
    session.runDriver("page-state",J.obj("expectedUrl",url),state->{
      if(request==serial&&state.optBoolean("ok")&&namespace.equals(scope())&&WebReplyObserver.same(url,session.web.getUrl())&&WebReplyObserver.same(url,state.optString("url"))){pages.put(namespace+"|"+address(url),state);while(pages.size()>8)pages.remove(pages.keySet().iterator().next());}
      done.run();
    });
  }
  void restore(String url,long epoch){if(!restorePending)return;restorePending=false;
    JSONObject saved=pages.get(scope()+"|"+address(url));if(saved==null){lastRestore=J.obj("ok",false,"reason","no-snapshot");return;}
    boolean allowDraft=session.pending==null&&!session.submitting&&!session.operation;
    session.asyncDriver("page-restore",J.obj("expectedUrl",url,"state",saved,"allowDraft",allowDraft,"allowScroll",AppPrefs.enabled(session.context,"restoreScroll")),2200,result->{
      if((session.context.getApplicationInfo().flags&android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0)lastRestore=result;
      if(epoch!=session.navigationEpoch||!WebReplyObserver.same(url,session.web.getUrl()))return;
      if(result.optBoolean("conflict")&&!saved.optString("draft").isEmpty()){
        final String text=saved.optString("draft");session.webStore.worker.execute(()->{
          boolean archived=DraftArchive.get(session.context).save(url,text,"重连前网页草稿");
          session.handler.post(()->{if(epoch==session.navigationEpoch&&WebReplyObserver.same(url,session.web.getUrl())&&session.pending==null)session.setStatus(archived?"网页已有新草稿，原草稿已暂存，可在“恢复暂存草稿”查看":"原草稿暂存未完成，网页中的新草稿未改动");});
        });
      }
    });
  }
}
