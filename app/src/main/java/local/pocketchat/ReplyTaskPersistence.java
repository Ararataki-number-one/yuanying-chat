package local.pocketchat;

import org.json.JSONObject;

/** Persists a local observation outcome before releasing its pending cursor. */
final class ReplyTaskPersistence {
  private ReplyTaskPersistence() {}

  static void complete(ChatSession session,JSONObject job,JSONObject poll) {
    finish(session,job,"completed","回复已完成",poll.optString("userKey"),
      poll.optString("url",session.conversation),"回复完成");
  }

  static void stopped(ChatSession session,JSONObject job) {
    if(job==null)return;
    finish(session,job,"stopped","已观察到网页停止操作，已停止完成提醒",
      job.optString("userKey"),"","已停止等待这条网页回复");
  }

  static void abandon(ChatSession session,JSONObject job) {
    finish(session,job,"uncertain","已解除等待，发送结果仍需在网页核对",
      "","","已解除等待，请自行核对是否需要发送");
  }

  private static boolean owns(ChatSession session,JSONObject job) {
    return job!=null&&!session.deleted&&session.pending==job;
  }

  private static boolean stillIdle(ChatSession session,long generation) {
    return !session.deleted&&session.pending==null&&session.webWorkGeneration==generation;
  }

  private static void finish(ChatSession session,JSONObject job,String state,String detail,
      String key,String url,String message) {
    if(!owns(session,job))return;
    String id=job.optString("id");
    boolean saved;
    // Ordinary progress deduplication is not a durable terminal receipt.
    try {saved=session.deliveries.update(id,state,detail,true,key,url);}
    catch(Exception error){saved=false;}
    if(!owns(session,job))return;
    if(!saved){session.setStatus("等待记录保存失败，请保留原网页核对");return;}

    boolean cleared=clearPending(session,id,state,url);
    // commit may publish memory and invoke listeners even when disk writing fails.
    if(!owns(session,job))return;
    // Unlike completed/stopped, uncertain does not suppress pending on recovery.
    if(!cleared&&"uncertain".equals(state)){
      session.setStatus("等待记录清理失败，请重试解除等待");return;
    }
    retire(session);
    long generation=session.webWorkGeneration;
    session.status=cleared?message:message+" · 本地等待记录清理未完成";
    if("completed".equals(state))ChatService.completed(session.context,id,url);
    if(!stillIdle(session,generation))return;
    ChatService.end(session.context);
    if(!stillIdle(session,generation))return;
    if("completed".equals(state))session.wakeDeferredBrowserSettings();
    else session.setStatus(session.status);
  }

  private static boolean clearPending(ChatSession session,String id,String state,String url) {
    try {
      if("completed".equals(state))return session.prefs.edit().remove("pending")
        .putString("lastCompletedId",id).putString("url",url).commit();
      return session.prefs.edit().remove("pending").commit();
    } catch(Exception error){return false;}
  }

  private static void retire(ChatSession session) {
    session.pending=null;session.activeDeliveryId="";
    session.replyStalled=false;session.replyHealthStatus="";
  }

  /** SQLite already records the terminal outcome; a stale preference must not revive it. */
  static void restoreTerminal(ChatSession session,JSONObject job,JSONObject receipt) {
    if(!owns(session,job))return;
    String id=job.optString("id"),state=receipt.optString("state");
    if(!"completed".equals(state)&&!"stopped".equals(state))return;
    String url=receipt.optString("url");
    if(url.isEmpty())url=job.optString("confirmedUrl",job.optString("expectedUrl"));
    boolean cleared=clearPending(session,id,state,url);
    if(!owns(session,job))return;
    retire(session);
    if(!cleared)session.status="已恢复等待结果 · 本地等待记录清理未完成";
    // Construction is not finished yet. The existing notice ledger owns deduplication;
    // this is deliberately not a transaction across SQLite, preferences and notifications.
    if("completed".equals(state)){
      final String completedUrl=url;
      session.handler.post(()->{if(!session.deleted)ChatService.completed(session.context,id,completedUrl);});
    }
  }
}
