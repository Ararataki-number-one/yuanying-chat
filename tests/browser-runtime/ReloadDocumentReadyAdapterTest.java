package local.pocketchat;

/** Exercise the exact test adapter; no synthetic document is admitted to production here. */
public final class ReloadDocumentReadyAdapterTest {
  static int passed;static final String RUN="reload-reloadStart-123456";
  static void check(boolean value){if(!value)throw new AssertionError("reload adapter control "+(passed+1));passed++;}
  static boolean maps(String kind,String incoming,String actual,String sender,String visible,String registered,String currentRun,boolean current,boolean top,boolean content){return ReloadDocumentReadyAdapter.maps(kind,incoming,actual,sender,visible,registered,currentRun,current,top,content);}
  public static void main(String[] args){
    for(String path:new String[]{"c/reload-A","c/reload-B","c/reload-C"}){
      String a=ReloadDocumentReadyAdapter.ACTUAL+path,v=ReloadDocumentReadyAdapter.VIRTUAL+path;
      check(maps("documentReady",a,a,a,v,RUN,RUN,true,true,true));
      check(!maps("ready",a,a,a,v,RUN,RUN,true,true,true));
      check(!maps("result",a,a,a,v,RUN,RUN,true,true,true));
      check(!maps("documentReady",a+"?foreign",a,a,v,RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a+"#foreign",a,v,RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a,a+"?foreign",v,RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a,a,v+"?foreign",RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a,a,v,RUN,"reload-reloadStart-999",true,true,true));
      check(!maps("documentReady",a,a,a,v,"reload-requestReload-123456","reload-requestReload-123456",true,true,true));
      check(!maps("documentReady",a,a,a,v,RUN,RUN,false,true,true));
      check(!maps("documentReady",a,a,a,v,RUN,RUN,true,false,true));
      check(!maps("documentReady",a,a,a,v,RUN,RUN,true,true,false));
      check(!maps("documentReady",a,null,a,v,RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a,null,v,RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a,a,null,RUN,RUN,true,true,true));
      check(!maps("documentReady",a,a,a,v,null,RUN,true,true,true));
      check(!maps("documentReady",a,a,a,v,RUN,null,true,true,true));
    }
    for(String path:new String[]{"c/reload-collapse","c/other","c/reload-A/","c/reload-A?x=1"}){
      String a=ReloadDocumentReadyAdapter.ACTUAL+path,v=ReloadDocumentReadyAdapter.VIRTUAL+path;
      check(!maps("documentReady",a,a,a,v,RUN,RUN,true,true,true));
    }
    String a=ReloadDocumentReadyAdapter.ACTUAL+"c/reload-A",b=ReloadDocumentReadyAdapter.ACTUAL+"c/reload-B",v=ReloadDocumentReadyAdapter.VIRTUAL+"c/reload-B";
    check(!maps("documentReady",a,b,b,v,RUN,RUN,true,true,true));
    check(!maps("documentReady",b,b,a,v,RUN,RUN,true,true,true));
    check(!maps(null,b,b,b,v,RUN,RUN,true,true,true));
    check(!maps("documentReady",null,b,b,v,RUN,RUN,true,true,true));
    System.out.println("{\"status\":\"passed\",\"passed\":"+passed+",\"total\":"+passed+",\"actualAndroidExecution\":false}");
  }
}
