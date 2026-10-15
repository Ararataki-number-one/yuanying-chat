package local.pocketchat;

/** JVM controls exercise the exact adapter used by the actual SDK fixture. */
public final class ChromeCollapseDocumentReadyAdapterTest {
  static int passed;
  static void check(boolean value){if(!value)throw new AssertionError("adapter control "+(passed+1));passed++;}
  static boolean maps(String kind,String incoming,String actual,String sender,String visible,boolean current,boolean top,boolean content){return ChromeCollapseDocumentReadyAdapter.maps(kind,incoming,actual,sender,visible,current,top,content);}
  public static void main(String[] args){
    String a=ChromeCollapseDocumentReadyAdapter.ACTUAL,v=ChromeCollapseDocumentReadyAdapter.VIRTUAL;
    check(maps("documentReady",a,a,a,v,true,true,true));
    check(!maps("result",a,a,a,v,true,true,true));
    check(!maps("documentReady",a+"?foreign",a,a,v,true,true,true));
    check(!maps("documentReady",a,a+"?foreign",a,v,true,true,true));
    check(!maps("documentReady",a,a,a+"?foreign",v,true,true,true));
    check(!maps("documentReady",a,a,a,v+"?foreign",true,true,true));
    check(!maps("documentReady",a,a,a,v,false,true,true));
    check(!maps("documentReady",a,a,a,v,true,false,true));
    check(!maps("documentReady",a,a,a,v,true,true,false));
    check(!maps(null,a,a,a,v,true,true,true));
    check(!maps("documentReady",null,a,a,v,true,true,true));
    check(!maps("documentReady",a,null,a,v,true,true,true));
    check(!maps("documentReady",a,a,null,v,true,true,true));
    check(!maps("documentReady",a,a,a,null,true,true,true));
    System.out.println("{\"status\":\"passed\",\"passed\":"+passed+",\"total\":"+passed+",\"actualAndroidExecution\":false}");
  }
}
