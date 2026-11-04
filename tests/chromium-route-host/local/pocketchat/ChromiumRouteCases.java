package local.pocketchat;
import java.nio.file.*;
import java.util.*;
public final class ChromiumRouteCases {
  static int checks;static void check(String name,boolean result){checks++;if(!result)throw new AssertionError(name);}
  public static void main(String[] args)throws Exception{
    ChromiumRoutePolicy p=new ChromiumRoutePolicy();
    ChromiumRoutePolicy.Ticket first=p.begin();check("route blocked before proxy callback",!p.current(first));
    check("lost evidence cannot admit",!p.admit(first,false));check("verified callback admits",p.admit(first,true));
    for(int i=0;i<100;i++)check("valid resume/reload retains exact ticket "+i,p.retain(first,true)&&p.current(first));
    check("changed evidence cannot retain",!p.retain(first,false));
    ChromiumRoutePolicy.Ticket second=p.begin();check("refresh invalidates captured download lease",!p.current(first));
    check("late proxy callback cannot reopen old route",!p.admit(first,true));check("replacement waits for own callback",!p.current(second));
    check("replacement admits",p.admit(second,true));p.block();check("blocked callback cannot reopen",!p.admit(second,true));
    ChromiumRoutePolicy.Ticket third=p.begin();p.close();check("closed callback cannot reopen",!p.admit(third,true));check("closed cannot restart",p.begin()==null);
    ChromiumRoutePolicy.ProxyQueue queue=new ChromiumRoutePolicy.ProxyQueue();List<Integer> events=new ArrayList<>();
    queue.submit(()->events.add(1));queue.submit(()->events.add(2));queue.submit(()->events.add(3));
    check("proxy changes never overlap",events.equals(Arrays.asList(1)));queue.complete();check("newest pending replaces obsolete proxy change",events.equals(Arrays.asList(1,3)));queue.complete();
    queue.submit(()->events.add(4));check("completed queue accepts replacement activity",events.equals(Arrays.asList(1,3,4)));queue.complete();
    Random random=new Random(20261104);for(int round=0;round<1000;round++){
      ChromiumRoutePolicy model=new ChromiumRoutePolicy();ChromiumRoutePolicy.Ticket prior=null,current=null;boolean admitted=false;
      for(int step=0;step<40;step++)switch(random.nextInt(5)){
        case 0:prior=current;current=model.begin();admitted=false;break;
        case 1:boolean proof=random.nextBoolean();boolean result=model.admit(current,proof);if(current!=null&&proof)admitted=true;check("model admission",result==(current!=null&&proof));break;
        case 2:check("model retain",model.retain(current,true)==admitted);break;
        case 3:if(prior!=null&&prior!=current)check("model stale callback",!model.admit(prior,true));break;
        default:model.block();current=null;admitted=false;break;
      }
    }
    Path directory=Files.createTempDirectory("chromium-profile-cleanup");try{
      for(int slot=0;slot<8;slot++){Path child=Files.createDirectories(directory.resolve("app_webview_env"+slot));Files.write(child.resolve("Cookies"),new byte[]{1});}
      Files.createDirectories(directory.resolve("app_webview"));EnvironmentBrowserData.clearChromium(directory.toFile(),3);
      check("only selected suffix removed",!Files.exists(directory.resolve("app_webview_env3"))&&Files.exists(directory.resolve("app_webview_env4/Cookies")));
      EnvironmentBrowserData.clearChromium(directory.toFile(),0);check("default suffix and legacy directory cleaned on explicit reset",!Files.exists(directory.resolve("app_webview_env0"))&&!Files.exists(directory.resolve("app_webview")));
      Path outside=Files.createTempDirectory("chromium-outside");try{Files.write(outside.resolve("keep"),new byte[]{2});EnvironmentBrowserData.erase(directory.resolve("app_webview_env1").toFile());Files.createSymbolicLink(directory.resolve("app_webview_env1"),outside);EnvironmentBrowserData.clearChromium(directory.toFile(),1);check("terminal symlink unlinked without erasing target",Files.exists(outside.resolve("keep")));}finally{EnvironmentBrowserData.erase(outside.toFile());}
      boolean refused=false;try{EnvironmentBrowserData.clearChromium(directory.toFile(),8);}catch(java.io.IOException expected){refused=true;}check("invalid slot refused before erasing another environment",refused&&Files.exists(directory.resolve("app_webview_env2/Cookies")));
    }finally{EnvironmentBrowserData.erase(directory.toFile());}
    check("public browser fixture allowed",BrowserAddressPolicy.allowed("http://browser-fixture.example/start"));
    check("public HTTPS allowed",BrowserAddressPolicy.allowed("https://example.com/file"));
    check("private download target blocked",!BrowserAddressPolicy.allowed("http://127.0.0.1/file"));
    check("encoded authority blocked",!BrowserAddressPolicy.allowed("https://example.com%2f@localhost/file"));
    System.out.println("Chromium route policy: "+checks+" checks passed");
  }
}
