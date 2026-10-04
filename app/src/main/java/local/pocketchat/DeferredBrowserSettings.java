package local.pocketchat;

import org.json.*;

/** Desired settings stay separate from the policy currently used by a live reply. */
final class DeferredBrowserSettings {
  static boolean pending(ChatSession s){return s.prefs.contains("nextPrivacyLevel");}
  static JSONObject desired(ChatSession s){return J.obj("privacyLevel",s.prefs.getInt("nextPrivacyLevel",s.privacy.level()),"desktopSite",s.prefs.getBoolean("nextDesktopSite",s.privacy.wantsDesktop()));}
  static boolean save(ChatSession s,int level,boolean desktop){return s.prefs.edit().putInt("nextPrivacyLevel",level).putBoolean("nextDesktopSite",desktop).commit();}
  static void cancel(ChatSession s){s.prefs.edit().remove("nextPrivacyLevel").remove("nextDesktopSite").commit();}
  static boolean idle(ChatSession s){return !s.deleted&&!ProfileUi.working(s)&&!s.connecting&&!s.navigating&&!s.recoveryScheduled&&!s.web.failed;}
  static void apply(ChatSession s){JSONObject value=desired(s);boolean protection=value.optInt("privacyLevel")!=s.privacy.level();ProfileCatalog.get(s.context).browserDisplay(Profiles.slot(s.context),value.optBoolean("desktopSite"));s.prefs.edit().putInt("privacyLevel",value.optInt("privacyLevel")).remove("nextPrivacyLevel").remove("nextDesktopSite").commit();s.applyBrowserSettings(protection);s.setStatus("已应用保存的网页显示和保护设置");}
  static void release(ChatSession s){s.configurationCapture=false;s.operation=false;}
  static void drain(ChatSession s){
    if(!pending(s)||!idle(s)||android.os.SystemClock.elapsedRealtime()-s.lastDeferredBrowserAttempt<10000)return;
    s.lastDeferredBrowserAttempt=android.os.SystemClock.elapsedRealtime();String url=s.web.getUrl();long epoch=s.navigationEpoch;String scope=s.pageMemory.scope();
    if(!MainActivity.chatUrl(url)){apply(s);return;}
    s.operation=true;s.configurationCapture=true;
    s.asyncDriver("inspect",J.obj("expectedUrl",url),2500,inspected->{
      if(epoch!=s.navigationEpoch||!WebReplyObserver.same(url,inspected.optString("url"))||inspected.optBoolean("busy")||inspected.optString("draftRaw").length()>300000){release(s);return;}
      s.asyncDriver("page-state",J.obj("expectedUrl",url),2500,state->{
        if(!state.optBoolean("ok")||epoch!=s.navigationEpoch||!scope.equals(s.pageMemory.scope())||!state.optString("draft").equals(inspected.optString("draft"))){release(s);return;}
        s.pageMemory.remember(scope,url,state);s.web.checkpointState();
        s.webStore.worker.execute(()->{boolean saved=DraftArchive.get(s.context).save(url,state.optString("draft"),"应用环境设置前的草稿");s.handler.post(()->{
          if(!saved||epoch!=s.navigationEpoch||!scope.equals(s.pageMemory.scope())||!pending(s)){release(s);return;}
          s.asyncDriver("inspect",J.obj("expectedUrl",url),2500,fresh->{release(s);if(epoch==s.navigationEpoch&&WebReplyObserver.same(url,fresh.optString("url"))&&!fresh.optBoolean("busy")&&fresh.optString("draft").equals(state.optString("draft"))&&pending(s)&&idle(s))apply(s);});
        });});
      });
    });
  }
}
