package local.pocketchat;

import android.app.Activity;
import android.view.ViewGroup;
import android.webkit.DownloadListener;
import android.webkit.WebChromeClient;
import android.webkit.WebViewClient;

/** One UI host's callbacks and parent; the retained session outlives this binding. */
final class GeckoUiBinding implements AutoCloseable {
  private final GeckoWebView web;
  private final Activity host;
  private final ViewGroup parent;
  private final WebViewClient client,backgroundClient;
  private final WebChromeClient chrome;
  private final DownloadListener download;
  private final GeckoWebView.ResponseDownload responseDownload;
  private boolean closed;

  GeckoUiBinding(GeckoWebView web,Activity host,ViewGroup parent,WebViewClient backgroundClient){
    this.web=web;this.host=host;this.parent=parent;this.backgroundClient=backgroundClient;
    client=web.client;chrome=web.chrome;download=web.download;responseDownload=web.responseDownload;
  }

  boolean current(){return !closed&&web.displayContext.getBaseContext()==host;}

  @Override public void close(){
    if(closed)return;closed=true;
    // Restore the session's page/error handling, without retaining its retired UI.
    // A replacement host can already have installed different callbacks.
    if(web.client==client)web.setWebViewClient(backgroundClient);
    if(web.chrome==chrome)web.setWebChromeClient(null);
    if(web.download==download)web.setDownloadListener(null);
    if(web.responseDownload==responseDownload)web.responseDownload=null;
    if(web.displayContext.getBaseContext()!=host)return;
    if(web.getParent()==parent)parent.removeView(web);
    // Detaching a view can synchronously bind another Activity.
    web.releaseHost(host);
  }
}
