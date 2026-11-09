package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import java.util.HashSet;
import java.util.Set;

/** Test-only current workspace layout and read-only observation after real input. */
final class DownloadWorkspaceVisuals {
  final Activity activity;final View root;final String invocationNonce;
  final Set<String> nonces=new HashSet<>();final Handler handler=new Handler(Looper.getMainLooper());
  DownloadLocationLayoutEvidence observation;boolean closed;
  static boolean requested(Intent request){return request!=null&&request.getIntExtra("visualDownloadContract",1)==2;}
  static LinearLayout body(Activity activity,LinearLayout root){
    // The production embedded and standalone workspaces use this same header.
    root.addView(DesignDownloads.header(activity),new LinearLayout.LayoutParams(-1,-2));
    LinearLayout box=DesignUi.column(activity);box.setPadding(DesignUi.dp(activity,20),DesignUi.dp(activity,4),DesignUi.dp(activity,20),DesignUi.dp(activity,20));
    ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(true);scroll.setClipToPadding(false);
    scroll.addView(box,new ScrollView.LayoutParams(-1,-2));root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
    return box;
  }
  DownloadWorkspaceVisuals(Activity activity,View root,String nonce){
    this.activity=activity;this.root=root;this.invocationNonce=nonce;
    if(!"local.pocketchat.test".equals(activity.getPackageName())||nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IllegalArgumentException("Owned download capture required");
    nonces.add(nonce);
  }
  void observe(Intent request){
    String nonce=null;
    try{
      nonce=request==null?null:request.getStringExtra("visualObserveNonce");
      if(closed||!"local.pocketchat.test".equals(activity.getPackageName())||!requested(activity.getIntent())||!"downloads".equals(activity.getIntent().getStringExtra("visualAction")))throw new IllegalArgumentException("scene");
      if(request==null||!"download-workspace-location".equals(request.getStringExtra("visualObserveAction")))throw new IllegalArgumentException("action");
      if(nonce==null||!nonce.matches("[0-9a-f]{32}")||nonces.contains(nonce)||!invocationNonce.equals(request.getStringExtra("visualParentNonce")))throw new IllegalArgumentException("nonce");
      if(!DownloadLocationLayoutEvidence.cleanSource(activity).equals(request.getStringExtra("visualSourceCommit")))throw new IllegalArgumentException("source");
      nonces.add(nonce);if(observation!=null)observation.close();
      DownloadLocationLayoutEvidence fresh=new DownloadLocationLayoutEvidence(activity,root,nonce,invocationNonce);observation=fresh;
      // No clicks, scrolling, visibility changes or layout requests. The host
      // has already expanded the real tools and brought the label into view.
      handler.post(()->{if(!closed&&observation==fresh&&!fresh.closed)fresh.onPreDraw();});
    }catch(Exception invalid){
      Log.w("PocketDownloadLabel",J.obj("schema",1,"scene","downloads","status","rejected","nonce",nonce!=null&&nonce.matches("[0-9a-f]{32}")?nonce:"","reason",invalid.getClass().getSimpleName()).toString());
    }
  }
  void close(){closed=true;handler.removeCallbacksAndMessages(null);if(observation!=null)observation.close();}
}
