package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;

/** Executes the production permission model with manual callbacks and a virtual clock.
 * This is a JVM policy/state-machine check, never Android or Gecko execution. */
public final class SitePermissionsHost {
  static int checks;
  static void check(String name,boolean ok){if(!ok)throw new AssertionError(name);checks++;}
  static List<SitePermissions.Entry> rows(SitePermissions.Entry... values){return Arrays.asList(values);}
  static final class ScopeSpec {
    String id="00000000-0000-0000-0000-000000000032",document="document-1",origin="https://chatgpt.com",context;
    int generation=4,slot=2;boolean privateMode;
    Object browser=new Object(),runtime=new Object(),session=new Object(),port=new Object();
    long lifetime=7,load=11,navigation=13;
    ScopeSpec(){}
    ScopeSpec(SitePermissions.Scope s){id=s.environmentId;generation=s.generation;slot=s.slot;browser=s.browser;runtime=s.runtime;session=s.session;port=s.port;lifetime=s.lifetime;load=s.load;navigation=s.navigation;document=s.document;origin=s.origin;context=s.contextId;privateMode=s.privateMode;}
    SitePermissions.Scope build(){return new SitePermissions.Scope(id,generation,slot,browser,runtime,session,port,lifetime,load,navigation,document,origin,context,privateMode);}
  }
  static SitePermissions.Entry entry(Object nativeObject,int type,int value){return new SitePermissions.Entry(nativeObject,"https://chatgpt.com/c/controlled",null,null,false,type,value);}
  static final class Request {
    final Consumer<List<SitePermissions.Entry>> success;final Consumer<String> failure;
    Request(Consumer<List<SitePermissions.Entry>> success,Consumer<String> failure){this.success=success;this.failure=failure;}
  }
  static final class Task {
    final Runnable action;final long due,order;boolean cancelled;
    Task(Runnable action,long due,long order){this.action=action;this.due=due;this.order=order;}
  }
  static final class Backend implements SitePermissions.Backend {
    SitePermissions.Scope scope=new ScopeSpec().build();
    final ArrayDeque<Request> pending=new ArrayDeque<>();final List<Task> tasks=new ArrayList<>();
    final List<SitePermissions.Entry> written=new ArrayList<>();final List<Integer> values=new ArrayList<>();
    int reads;long now,order;boolean throwRead,throwWrite;
    public SitePermissions.Scope current(){return scope;}
    public void read(SitePermissions.Scope captured,Consumer<List<SitePermissions.Entry>> success,Consumer<String> failure){reads++;if(throwRead)throw new IllegalStateException("controlled read failure");pending.add(new Request(success,failure));}
    public void write(SitePermissions.Scope captured,SitePermissions.Entry permission,int value){if(throwWrite)throw new IllegalStateException("controlled write failure");written.add(permission);values.add(value);}
    public void later(Runnable action,long delay){tasks.add(new Task(action,now+delay,order++));}
    public void cancel(Runnable action){for(Task task:tasks)if(task.action==action)task.cancelled=true;}
    Request take(){if(pending.isEmpty())throw new AssertionError("expected actual queued model read");return pending.remove();}
    void ok(List<SitePermissions.Entry> entries){take().success.accept(entries);}
    void fail(String reason){take().failure.accept(reason);}
    void advance(long amount){
      long target=now+amount;
      for(;;){Task next=null;for(Task task:tasks)if(!task.cancelled&&task.due<=target&&(next==null||task.due<next.due||task.due==next.due&&task.order<next.order))next=task;
        if(next==null)break;tasks.remove(next);now=next.due;next.action.run();}
      now=target;
    }
  }
  static final class Rig {
    final Backend backend=new Backend();final SitePermissions.Manager manager=new SitePermissions.Manager(backend,backend.scope);
    final List<SitePermissions.Result> completed=new ArrayList<>();
    void refresh(){manager.refresh(completed::add);}
    void show(SitePermissions.Entry... entries){refresh();backend.ok(rows(entries));check("initial real model refresh ready",last().status.equals("ready"));}
    void change(SitePermissions.Entry row,int value){manager.change(row,value,completed::add);}
    SitePermissions.Result last(){if(completed.isEmpty())throw new AssertionError("no completed model result");return completed.get(completed.size()-1);}
    void writtenOnce(SitePermissions.Entry fresh,int value){check("exactly one native write",backend.written.size()==1);check("write uses newly queried native object",backend.written.get(0)==fresh);check("write carries requested safe value",backend.values.get(0)==value);}
  }
  static void origins(){
    check("origin lowercases scheme and host and removes page data",SitePermissions.origin("HTTPS://CHATGPT.COM:443/c/private?x=1#part").equals("https://chatgpt.com"));
    check("non-default HTTPS port remains part of identity",SitePermissions.origin("https://chatgpt.com:8443/c/a").equals("https://chatgpt.com:8443"));
    check("highest valid port remains valid",SitePermissions.origin("https://example.test:65535/a").equals("https://example.test:65535"));
    check("IPv6 origin has one bracket pair",SitePermissions.origin("https://[2001:DB8::1]:8443/x").equals("https://[2001:db8::1]:8443"));
    check("IPv6 default port collapses",SitePermissions.origin("https://[2001:db8::1]:443/x").equals("https://[2001:db8::1]"));
    for(String invalid:new String[]{null,"","http://chatgpt.com","javascript:alert(1)","data:text/plain,x","blob:https://chatgpt.com/id","https://user:pass@chatgpt.com/x","https://chatgpt.com@other.test/x","https://example.test:0","https://example.test:65536","https://example.test:-1","https:///missing-host","https://bad host/","https://\u4f8b\u5b50.\u6d4b\u8bd5/"})check("invalid origin is refused: "+String.valueOf(invalid),SitePermissions.origin(invalid).isEmpty());
    char[] huge=new char[2049];Arrays.fill(huge,'a');check("oversized source cannot become an origin",SitePermissions.origin(new String(huge)).isEmpty());
  }
  static void scopes(){
    SitePermissions.Scope base=new ScopeSpec().build();check("complete native scope is valid",base.valid());check("equal independent snapshots retain ownership",base.matches(new ScopeSpec(base).build()));check("absent current scope is stale",!base.matches(null));
    String[] fields={"id","generation","slot","browser","runtime","session","port","lifetime","load","navigation","document","origin","context","private"};
    for(String field:fields){ScopeSpec changed=new ScopeSpec(base);switch(field){case "id":changed.id="00000000-0000-0000-0000-000000000033";break;case "generation":changed.generation++;break;case "slot":changed.slot++;break;case "browser":changed.browser=new Object();break;case "runtime":changed.runtime=new Object();break;case "session":changed.session=new Object();break;case "port":changed.port=new Object();break;case "lifetime":changed.lifetime++;break;case "load":changed.load++;break;case "navigation":changed.navigation++;break;case "document":changed.document="document-2";break;case "origin":changed.origin="https://other.test";break;case "context":changed.context="";break;case "private":changed.privateMode=true;break;default:throw new AssertionError(field);}check("ownership includes "+field,!base.matches(changed.build()));}
    ScopeSpec invalid=new ScopeSpec(base);invalid.id="slot-is-not-an-environment-id";check("invalid environment identity rejected",!invalid.build().valid());invalid=new ScopeSpec(base);invalid.generation=-1;check("negative generation rejected",!invalid.build().valid());invalid=new ScopeSpec(base);invalid.slot=-1;check("negative slot rejected",!invalid.build().valid());invalid=new ScopeSpec(base);invalid.document=null;check("absent document identity rejected",!invalid.build().valid());invalid=new ScopeSpec(base);invalid.origin="HTTPS://CHATGPT.COM";check("scope origin must already be canonical",!invalid.build().valid());invalid=new ScopeSpec(base);invalid.origin=null;check("null scope origin rejected without exception",!invalid.build().valid());
    ScopeSpec empty=new ScopeSpec(base);empty.context="";check("default context null differs from empty context",!base.matches(empty.build()));
  }
  static void entries(){
    SitePermissions.Scope scope=new ScopeSpec().build();SitePermissions.Entry normal=entry(new Object(),0,SitePermissions.ALLOW);check("native object and exact scope form an editable entry",normal.belongs(scope));
    check("missing native object is refused",!entry(null,0,1).belongs(scope));check("HTTP permission record is refused",!new SitePermissions.Entry(new Object(),"http://chatgpt.com",null,null,false,0,1).belongs(scope));check("userinfo permission record is refused",!new SitePermissions.Entry(new Object(),"https://user@chatgpt.com",null,null,false,0,1).belongs(scope));
    check("other site permission is not borrowed",!new SitePermissions.Entry(new Object(),"https://other.test",null,null,false,0,1).belongs(scope));check("context null does not borrow empty-context record",!new SitePermissions.Entry(new Object(),scope.origin,null,"",false,0,1).belongs(scope));check("normal mode does not borrow private permission",!new SitePermissions.Entry(new Object(),scope.origin,null,null,true,0,1).belongs(scope));check("invalid native permission value refused",!entry(new Object(),0,4).belongs(scope));check("negative permission type refused",!entry(new Object(),-1,1).belongs(scope));
    SitePermissions.Entry third=new SitePermissions.Entry(new Object(),scope.origin,"https://frame.test/page",null,false,8,1);check("third-party record keeps normalized separate origin",third.belongs(scope)&&third.thirdPartyOrigin.equals("https://frame.test"));check("first-party and third-party keys are distinct",!third.sameKey(entry(new Object(),8,1)));check("different third-party keys remain distinct",!third.sameKey(new SitePermissions.Entry(new Object(),scope.origin,"https://other-frame.test",null,false,8,1)));check("malformed third-party source rejected",!new SitePermissions.Entry(new Object(),scope.origin,"http://frame.test",null,false,8,1).belongs(scope));check("empty third-party source is not null",!new SitePermissions.Entry(new Object(),scope.origin,"",null,false,8,1).belongs(scope));check("native principal object is not part of logical key",normal.sameKey(entry(new Object(),0,2)));
    for(int type=0;type<=11;type++){SitePermissions.Entry row=entry(new Object(),type,1);boolean editable=type==0||type==1||type==3||type==8||type==9||type==10;check("type "+type+" never adds allow",!row.permits(SitePermissions.ALLOW));check("type "+type+" deny follows explicit matrix",row.permits(SitePermissions.DENY)==(editable||type==7));check("type "+type+" default follows explicit matrix",row.permits(SitePermissions.DEFAULT)==editable);}
  }
  static void refresh(){
    Rig r=new Rig();SitePermissions.Entry notify=entry(new Object(),1,2),location=entry(new Object(),0,1);r.show(notify,location);check("native results sorted without rewriting input",r.last().entries.get(0)==location&&r.last().entries.get(1)==notify);check("reading is not a write",r.backend.written.isEmpty());check("a snapshot is never a mutation confirmation",!r.last().confirmed);boolean immutable=false;try{r.last().entries.clear();}catch(UnsupportedOperationException expected){immutable=true;}check("result list cannot be edited by UI",immutable);
    Rig empty=new Rig();empty.show();check("empty native result is ready rather than failed",empty.last().status.equals("ready")&&empty.last().entries.isEmpty());
    Rig duplicate=new Rig();duplicate.refresh();duplicate.backend.ok(rows(location,entry(new Object(),0,1)));check("duplicate native keys reject complete snapshot",duplicate.last().status.equals("failed")&&duplicate.last().entries.isEmpty());
    Rig third=new Rig();third.show(entry(new Object(),8,1),new SitePermissions.Entry(new Object(),"https://chatgpt.com","https://frame.test",null,false,8,2));check("distinct first and third-party rows are retained",third.last().entries.size()==2);
    Rig foreign=new Rig();foreign.refresh();foreign.backend.ok(rows(new SitePermissions.Entry(new Object(),"https://other.test",null,null,false,0,1)));check("foreign row rejects snapshot",foreign.last().status.equals("failed"));
    Rig missing=new Rig();missing.refresh();missing.backend.ok(null);check("null native result is failure, not no permissions",missing.last().status.equals("failed"));
    Rig count=new Rig();count.refresh();List<SitePermissions.Entry> tooMany=new ArrayList<>();for(int i=0;i<=SitePermissions.MAX_ROWS;i++)tooMany.add(entry(new Object(),i,1));count.backend.ok(tooMany);check("oversized native snapshots reject before display",count.last().status.equals("failed"));
  }
  static void freshWrite(){
    Rig r=new Rig();SitePermissions.Entry selected=entry(new Object(),0,1),fresh=entry(new Object(),0,1);r.show(selected);r.change(selected,2);check("selected UI object cannot write before reread",r.backend.written.isEmpty());r.backend.ok(rows(fresh));r.writtenOnce(fresh,2);check("stale native object is never reused",r.backend.written.get(0).nativePermission!=selected.nativePermission);r.backend.ok(rows(entry(new Object(),0,2)));check("deny confirmed only by separate native readback",r.last().status.equals("confirmed")&&r.last().confirmed);r.backend.advance(10000);check("successful mutation never writes again",r.backend.written.size()==1);
    Rig forged=new Rig();SitePermissions.Entry offered=entry(new Object(),0,1);forged.show(offered);int reads=forged.backend.reads;forged.change(entry(new Object(),0,1),2);check("lookalike unoffered row cannot mutate",forged.last().status.equals("failed")&&forged.backend.reads==reads&&forged.backend.written.isEmpty());
    Rig changed=new Rig();SitePermissions.Entry old=entry(new Object(),0,1);changed.show(old);changed.change(old,2);changed.backend.ok(rows(entry(new Object(),0,3)));check("concurrent change to a third value requires new intent",changed.last().status.equals("changed")&&changed.backend.written.isEmpty());
    Rig reached=new Rig();SitePermissions.Entry before=entry(new Object(),0,1);reached.show(before);reached.change(before,2);reached.backend.ok(rows(entry(new Object(),0,2)));check("already reached target is confirmed without repeat write",reached.last().confirmed&&reached.backend.written.isEmpty());
    Rig absent=new Rig();SitePermissions.Entry previous=entry(new Object(),0,1);absent.show(previous);absent.change(previous,3);absent.backend.ok(rows());check("missing prewrite record never authorizes a write",absent.last().status.equals("changed")&&absent.backend.written.isEmpty());
    Rig allow=new Rig();SitePermissions.Entry allowRow=entry(new Object(),0,2);allow.show(allowRow);allow.change(allowRow,1);check("model blocks a requested new allow",allow.last().status.equals("failed")&&allow.backend.written.isEmpty());
    Rig readonly=new Rig();SitePermissions.Entry persistent=entry(new Object(),2,1);readonly.show(persistent);int beforeReads=readonly.backend.reads;readonly.change(persistent,2);check("persistent-storage readonly intent never queries or writes",readonly.last().status.equals("failed")&&readonly.backend.reads==beforeReads&&readonly.backend.written.isEmpty());
    Rig tracking=new Rig();SitePermissions.Entry exception=entry(new Object(),7,1);tracking.show(exception);tracking.change(exception,3);check("tracking cannot dispatch unsupported restore-default",tracking.last().status.equals("failed")&&tracking.backend.written.isEmpty());
  }
  static void readback(){
    Rig r=new Rig();SitePermissions.Entry selected=entry(new Object(),0,1),fresh=entry(new Object(),0,1);r.show(selected);r.change(selected,2);r.backend.ok(rows(fresh));r.backend.ok(rows(entry(new Object(),0,1)));check("first stale readback does not confirm",r.completed.size()==1);r.backend.advance(149);check("first backoff does not run early",r.backend.pending.isEmpty());r.backend.advance(1);check("first read-only retry starts at 150ms",r.backend.pending.size()==1);r.backend.ok(rows(entry(new Object(),0,1)));r.backend.advance(349);check("second backoff does not run early",r.backend.pending.isEmpty());r.backend.advance(1);check("second read-only retry starts after 350ms",r.backend.pending.size()==1);r.backend.ok(rows(entry(new Object(),0,1)));check("three unmatching readbacks end unconfirmed",r.last().status.equals("unconfirmed")&&!r.last().confirmed);check("exactly pre-read plus three readbacks after refresh",r.backend.reads==5);r.writtenOnce(fresh,2);r.backend.advance(10000);check("no fourth readback or repeated write",r.backend.reads==5&&r.backend.written.size()==1);
    Rig defaults=new Rig();SitePermissions.Entry d=entry(new Object(),1,1),df=entry(new Object(),1,1);defaults.show(d);defaults.change(d,3);defaults.backend.ok(rows(df));defaults.backend.ok(rows());check("missing record confirms requested default only after write",defaults.last().confirmed&&defaults.last().entries.isEmpty());defaults.writtenOnce(df,3);
    Rig missingDeny=new Rig();SitePermissions.Entry md=entry(new Object(),1,1);missingDeny.show(md);missingDeny.change(md,2);missingDeny.backend.ok(rows(entry(new Object(),1,1)));missingDeny.backend.ok(rows());missingDeny.backend.advance(150);missingDeny.backend.ok(rows());missingDeny.backend.advance(350);missingDeny.backend.ok(rows());check("missing record cannot confirm requested deny",missingDeny.last().status.equals("unconfirmed")&&!missingDeny.last().confirmed);
    Rig failure=new Rig();SitePermissions.Entry f=entry(new Object(),0,1);failure.show(f);failure.change(f,2);failure.backend.ok(rows(entry(new Object(),0,1)));failure.backend.fail("unavailable");check("readback failure retains unconfirmed state",failure.last().status.equals("unconfirmed")&&failure.backend.written.size()==1);
  }
  static void revisions(){
    Rig r=new Rig();r.refresh();Request old=r.backend.take();r.refresh();Request current=r.backend.take();old.success.accept(rows(entry(new Object(),0,1)));check("superseded read callback is ignored",r.completed.isEmpty());current.success.accept(rows(entry(new Object(),1,2)));check("latest revision supplies result",r.completed.size()==1&&r.last().entries.get(0).type==1);current.failure.accept("late error");current.success.accept(rows());check("duplicate callbacks cannot replace settled result",r.completed.size()==1&&r.last().entries.size()==1);
    Rig closed=new Rig();closed.refresh();Request pending=closed.backend.take();closed.manager.close();pending.success.accept(rows(entry(new Object(),0,1)));closed.backend.advance(10000);check("closed panel drops callback and timeout",closed.completed.isEmpty()&&closed.backend.written.isEmpty());check("closed manager no longer owns native scope",!closed.manager.current());
    Rig afterWrite=new Rig();SitePermissions.Entry a=entry(new Object(),0,1);afterWrite.show(a);afterWrite.change(a,2);afterWrite.backend.ok(rows(entry(new Object(),0,1)));Request reply=afterWrite.backend.take();afterWrite.manager.close();reply.success.accept(rows(entry(new Object(),0,2)));check("close after one write does not publish a late confirmation",afterWrite.completed.size()==1&&afterWrite.backend.written.size()==1);
    Rig refreshDuringRetry=new Rig();SitePermissions.Entry selected=entry(new Object(),0,1);refreshDuringRetry.show(selected);refreshDuringRetry.change(selected,2);refreshDuringRetry.backend.ok(rows(entry(new Object(),0,1)));refreshDuringRetry.backend.ok(rows(entry(new Object(),0,1)));refreshDuringRetry.refresh();refreshDuringRetry.backend.ok(rows(entry(new Object(),0,2)));int reads=refreshDuringRetry.backend.reads;refreshDuringRetry.backend.advance(1000);check("new refresh cancels scheduled confirmation retry",refreshDuringRetry.backend.reads==reads&&refreshDuringRetry.backend.written.size()==1);
  }
  static void timeouts(){
    Rig r=new Rig();r.refresh();Request late=r.backend.take();r.backend.advance(2999);check("native read timeout keeps full 3000ms",r.completed.isEmpty());r.backend.advance(1);check("native read timeout produces failure",r.last().status.equals("failed")&&!r.last().confirmed);late.success.accept(rows(entry(new Object(),0,1)));check("late result cannot replace timeout",r.completed.size()==1);
    Rig beforeWrite=new Rig();SitePermissions.Entry selected=entry(new Object(),0,1);beforeWrite.show(selected);beforeWrite.change(selected,2);Request before=beforeWrite.backend.take();beforeWrite.backend.advance(3000);check("prewrite timeout cannot dispatch a mutation",beforeWrite.last().status.equals("failed")&&beforeWrite.backend.written.isEmpty());before.success.accept(rows(entry(new Object(),0,1)));check("late prewrite callback still cannot write",beforeWrite.backend.written.isEmpty());
    Rig afterWrite=new Rig();SitePermissions.Entry a=entry(new Object(),0,1);afterWrite.show(a);afterWrite.change(a,2);afterWrite.backend.ok(rows(entry(new Object(),0,1)));Request confirmation=afterWrite.backend.take();afterWrite.backend.advance(3000);check("postwrite timeout reports unconfirmed rather than rollback",afterWrite.last().status.equals("unconfirmed")&&afterWrite.backend.written.size()==1);confirmation.success.accept(rows(entry(new Object(),0,2)));check("late postwrite confirmation ignored",afterWrite.completed.size()==2);
    Rig readThrow=new Rig();readThrow.backend.throwRead=true;readThrow.refresh();check("synchronous native read exception is contained",readThrow.last().status.equals("failed"));
    Rig writeThrow=new Rig();SitePermissions.Entry w=entry(new Object(),0,1);writeThrow.show(w);writeThrow.change(w,2);writeThrow.backend.throwWrite=true;writeThrow.backend.ok(rows(entry(new Object(),0,1)));check("native write exception cannot claim confirmation",writeThrow.last().status.equals("failed")&&!writeThrow.last().confirmed);
  }
  static void stale(){
    Rig r=new Rig();r.refresh();ScopeSpec other=new ScopeSpec(r.backend.scope);other.document="later-document";r.backend.scope=other.build();r.backend.ok(rows(entry(new Object(),0,1)));check("late result for another document is stale",r.last().status.equals("stale")&&r.last().entries.isEmpty());
    Rig reopen=new Rig();SitePermissions.Entry selected=entry(new Object(),0,1);reopen.show(selected);reopen.change(selected,2);ScopeSpec same=new ScopeSpec(reopen.backend.scope);same.lifetime++;Object session=same.session;reopen.backend.scope=same.build();reopen.backend.ok(rows(entry(new Object(),0,1)));check("same-session reopen is invalidated by lifetime",reopen.backend.scope.session==session&&reopen.last().status.equals("stale")&&reopen.backend.written.isEmpty());
    Rig moved=new Rig();SitePermissions.Entry m=entry(new Object(),0,1);moved.show(m);moved.change(m,2);moved.backend.ok(rows(entry(new Object(),0,1)));ScopeSpec changed=new ScopeSpec(moved.backend.scope);changed.generation++;moved.backend.scope=changed.build();moved.backend.ok(rows(entry(new Object(),0,2)));check("readback after environment reset is not confirmed",moved.last().status.equals("stale")&&!moved.last().confirmed&&moved.backend.written.size()==1);
    Rig popup=new Rig();popup.refresh();ScopeSpec pop=new ScopeSpec(popup.backend.scope);pop.session=new Object();popup.backend.scope=pop.build();popup.backend.ok(rows());check("popup activation cannot inherit primary result",popup.last().status.equals("stale"));
    Rig unavailable=new Rig();unavailable.backend.scope=null;unavailable.refresh();check("missing live scope refuses read before SDK",unavailable.last().status.equals("stale")&&unavailable.backend.reads==0);
    Rig portChanged=new Rig();portChanged.refresh();ScopeSpec newPort=new ScopeSpec(portChanged.backend.scope);newPort.origin="https://chatgpt.com:8443";portChanged.backend.scope=newPort.build();portChanged.backend.ok(rows());check("same hostname on another port cannot receive the old result",portChanged.last().status.equals("stale")&&portChanged.backend.written.isEmpty());
  }
  public static void main(String[] args){
    String suite=args.length==0?"all":args[0];
    switch(suite){case "origins":origins();break;case "scopes":scopes();break;case "entries":entries();break;case "refresh":refresh();break;case "fresh-write":freshWrite();break;case "readback":readback();break;case "revisions":revisions();break;case "timeouts":timeouts();break;case "stale":stale();break;case "all":origins();scopes();entries();refresh();freshWrite();readback();revisions();timeouts();stale();break;default:throw new AssertionError("Unknown controlled suite");}
    System.out.println("SITE_PERMISSIONS_HOST suite="+suite+" checks="+checks+" android=false gecko=false");
  }
}
