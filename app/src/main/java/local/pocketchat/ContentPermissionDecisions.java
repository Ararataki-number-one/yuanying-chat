package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;

/** One bounded lookup of native stored denial; never an allow decision or permission cache. */
final class ContentPermissionDecisions {
  static final int MAX_READS_PER_DOCUMENT=32;
  interface Backend {
    SitePermissions.Scope current(Object session);
    void read(SitePermissions.Scope scope,Consumer<List<SitePermissions.Entry>> success,Consumer<String> failure);
    void later(Runnable action,long delay);
    void cancel(Runnable action);
  }
  static final class Request {
    final Object session,nativePermission;final String origin,contextId,thirdPartyOrigin;
    final boolean privateMode;final int type,value;
    Request(Object session,Object permission,String uri,String thirdParty,String context,boolean privateMode,int type,int value){
      this.session=session;nativePermission=permission;origin=SitePermissions.origin(uri);thirdPartyOrigin=thirdParty;
      contextId=context;this.privateMode=privateMode;this.type=type;this.value=value;
    }
    boolean matches(SitePermissions.Scope scope){return scope!=null&&scope.valid()&&nativePermission!=null&&session==scope.session
      &&!origin.isEmpty()&&origin.equals(scope.origin)&&Objects.equals(contextId,scope.contextId)&&privateMode==scope.privateMode
      &&value>=0&&value<=3&&(contextId==null||contextId.length()<=1024)&&(thirdPartyOrigin==null||thirdPartyOrigin.length()<=2048);}
  }
  private final Backend backend;private Pending pending;private SitePermissions.Scope budget;private int reads;private boolean closed;
  ContentPermissionDecisions(Backend backend){this.backend=backend;}
  static boolean managed(int type){return type==0||type==1||type==3||type==9||type==10;}
  static boolean unchanged(int type){return type==2||type==4||type==5||type==6||type==7||type==8;}
  void close(){closed=true;if(pending!=null)pending.finish(SitePermissions.DENY);budget=null;}
  private SitePermissions.Scope current(Object session){try{return backend.current(session);}catch(RuntimeException invalid){return null;}}
  void request(Request request,Consumer<Integer> complete){
    if(closed||request==null){complete.accept(SitePermissions.DENY);return;}
    // Do not change persistent storage, playback, DRM, tracking exceptions or special storage access.
    if(unchanged(request.type)){complete.accept(SitePermissions.DEFAULT);return;}
    SitePermissions.Scope scope=current(request.session);
    if(!managed(request.type)||!request.matches(scope)||pending!=null){complete.accept(SitePermissions.DENY);return;}
    if(!scope.matches(budget)){budget=scope;reads=0;}
    if(reads>=MAX_READS_PER_DOCUMENT){complete.accept(SitePermissions.DENY);return;}reads++;
    Pending call=new Pending(scope,request,complete);pending=call;
    try{backend.later(call.timeout,SitePermissions.READ_TIMEOUT_MS);backend.read(scope,rows->{
      if(call.settled)return;
      if(!scope.matches(current(request.session))){call.finish(SitePermissions.DENY);return;}
      call.finish(storedDecision(scope,request,rows));
    },reason->call.finish(SitePermissions.DENY));}
    catch(RuntimeException unavailable){call.finish(SitePermissions.DENY);}
  }
  static int storedDecision(SitePermissions.Scope scope,Request request,List<SitePermissions.Entry> rows){
    if(rows==null||rows.size()>SitePermissions.MAX_ROWS)return SitePermissions.DENY;
    SitePermissions.Entry selected=null;
    for(SitePermissions.Entry row:rows){
      if(row==null||row.nativePermission==null||row.origin.isEmpty()||row.type<0||row.type>10||row.value<1||row.value>3||(row.thirdPartyOrigin!=null&&row.thirdPartyOrigin.isEmpty()))return SitePermissions.DENY;
      // Inherited, different namespace and special third-party records cannot supply this decision.
      if(!row.origin.equals(scope.origin)||!Objects.equals(row.contextId,scope.contextId)||row.privateMode!=scope.privateMode
          ||row.type!=request.type)continue;
      if(row.thirdPartyOrigin!=null)return SitePermissions.DENY;
      if(selected!=null)return SitePermissions.DENY;selected=row;
    }
    return selected!=null&&selected.value==SitePermissions.DENY?SitePermissions.DENY:SitePermissions.DEFAULT;
  }
  private final class Pending {
    final SitePermissions.Scope scope;final Request request;final Consumer<Integer> complete;boolean settled;
    final Runnable timeout=()->finish(SitePermissions.DENY);
    Pending(SitePermissions.Scope scope,Request request,Consumer<Integer> complete){this.scope=scope;this.request=request;this.complete=complete;}
    void finish(int value){if(settled)return;settled=true;if(pending==this)pending=null;try{backend.cancel(timeout);}catch(RuntimeException ignored){}
      complete.accept(value==SitePermissions.DEFAULT?SitePermissions.DEFAULT:SitePermissions.DENY);}
  }
}
