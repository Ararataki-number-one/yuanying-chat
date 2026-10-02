package local.pocketchat;

import android.webkit.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

public class ContinuityFixtureActivity extends MainActivity {
  static final AtomicInteger documents=new AtomicInteger(),heads=new AtomicInteger();
  static volatile boolean failHead=false;static volatile String nextDraft="";
  @Override void startNetwork(){session.connect();}
  @Override WebViewClient remoteClient(){WebViewClient original=session.client();return new WebViewClient(){
    @Override public void onPageStarted(WebView v,String u,android.graphics.Bitmap b){original.onPageStarted(v,u,b);}
    @Override public void onPageCommitVisible(WebView v,String u){original.onPageCommitVisible(v,u);}
    @Override public void onPageFinished(WebView v,String u){original.onPageFinished(v,u);}
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest request){try{
      if("HEAD".equals(request.getMethod())){heads.incrementAndGet();return new WebResourceResponse("text/html","UTF-8",failHead?503:200,failHead?"Fixture unavailable":"OK",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
      if(request.isForMainFrame())documents.incrementAndGet();String room=request.getUrl().getLastPathSegment();if(room==null||room.isEmpty())room="one";
      String html=asset("fixture-continuity.html").replace("__ROOM__",room.replaceAll("[^a-zA-Z0-9-]",""));
      String draft=nextDraft;nextDraft="";html=html.replace("__DRAFT__",draft.replace("\\","\\\\").replace("'","\\'").replace("\n","\\n"));
      return new WebResourceResponse("text/html","UTF-8",new ByteArrayInputStream(html.getBytes(StandardCharsets.UTF_8)));
    }catch(Exception e){return blocked();}}
  };}
}
