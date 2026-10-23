package local.pocketchat;

/** Test-only host pair for the three exact reload documents; never admits a page itself. */
final class ReloadDocumentReadyAdapter {
  static final String ACTUAL="http://127.0.0.1:8765/",VIRTUAL="https://chatgpt.com/";
  static boolean maps(String kind,String incoming,String actual,String sender,String visible,String registeredRun,String currentRun,boolean current,boolean topLevel,boolean contentScript){
    if(!"documentReady".equals(kind)||registeredRun==null||!registeredRun.matches("reload-reloadStart-[0-9]+")||!registeredRun.equals(currentRun)||!current||!topLevel||!contentScript)return false;
    for(String path:new String[]{"c/reload-A","c/reload-B","c/reload-C"})
      if((ACTUAL+path).equals(incoming)&&(ACTUAL+path).equals(actual)&&(ACTUAL+path).equals(sender)&&(VIRTUAL+path).equals(visible))return true;
    return false;
  }
}
