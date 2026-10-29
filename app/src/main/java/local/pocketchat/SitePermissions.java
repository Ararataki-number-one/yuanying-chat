package local.pocketchat;

import java.net.URI;
import java.util.*;
import java.util.function.Consumer;

/** A short-lived view of native permissions, never a second permission database. */
final class SitePermissions {
  static final int ALLOW=1,DENY=2,DEFAULT=3,MAX_ROWS=128;
  static final long READ_TIMEOUT_MS=3000;
  private SitePermissions() {}

  static String origin(String value) {
    try {
      if(value==null||value.length()>2048)return "";
      URI uri=new URI(value);String host=uri.getHost();int port=uri.getPort();
      if(!"https".equalsIgnoreCase(uri.getScheme())||host==null||uri.getRawUserInfo()!=null||port==0||port>65535)return "";
      host=host.toLowerCase(Locale.ROOT);
      if(host.indexOf(':')>=0&&!host.startsWith("["))host="["+host+"]";
      return "https://"+host+(port<0||port==443?"":":"+port);
    } catch(Exception invalid) {return "";}
  }

  static final class Scope {
    final String environmentId,origin,document,contextId;
    final int generation,slot;final boolean privateMode;
    final Object browser,runtime,session,port;
    final long lifetime,load,navigation;
    Scope(String id,int generation,int slot,Object browser,Object runtime,Object session,Object port,
        long lifetime,long load,long navigation,String document,String origin,String contextId,boolean privateMode) {
      this.environmentId=id;this.generation=generation;this.slot=slot;this.browser=browser;this.runtime=runtime;
      this.session=session;this.port=port;this.lifetime=lifetime;this.load=load;this.navigation=navigation;
      this.document=document;this.origin=origin;this.contextId=contextId;this.privateMode=privateMode;
    }
    boolean valid() {
      return environmentId!=null&&environmentId.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
          &&generation>=0&&slot>=0&&browser!=null&&runtime!=null&&session!=null
          &&document!=null&&origin!=null&&!origin.isEmpty()&&origin.equals(SitePermissions.origin(origin));
    }
    boolean matches(Scope other) {
      return other!=null&&valid()&&other.valid()&&environmentId.equals(other.environmentId)
          &&generation==other.generation&&slot==other.slot&&browser==other.browser&&runtime==other.runtime
          &&session==other.session&&port==other.port&&lifetime==other.lifetime&&load==other.load
          &&navigation==other.navigation&&document.equals(other.document)&&origin.equals(other.origin)
          &&Objects.equals(contextId,other.contextId)&&privateMode==other.privateMode;
    }
  }

  static final class Entry {
    final Object nativePermission;final String origin,thirdPartyOrigin,contextId;
    final boolean privateMode;final int type,value;
    Entry(Object nativePermission,String uri,String thirdPartyOrigin,String contextId,boolean privateMode,int type,int value) {
      this.nativePermission=nativePermission;this.origin=SitePermissions.origin(uri);
      this.thirdPartyOrigin=thirdPartyOrigin==null?null:SitePermissions.origin(thirdPartyOrigin);
      this.contextId=contextId;this.privateMode=privateMode;this.type=type;this.value=value;
    }
    boolean belongs(Scope scope) {
      return nativePermission!=null&&scope!=null&&origin.equals(scope.origin)&&!origin.isEmpty()
          &&(thirdPartyOrigin==null||!thirdPartyOrigin.isEmpty())&&Objects.equals(contextId,scope.contextId)
          &&privateMode==scope.privateMode&&value>=ALLOW&&value<=DEFAULT&&type>=0;
    }
    boolean sameKey(Entry other) {
      return other!=null&&type==other.type&&origin.equals(other.origin)
          &&Objects.equals(thirdPartyOrigin,other.thirdPartyOrigin)&&Objects.equals(contextId,other.contextId)
          &&privateMode==other.privateMode;
    }
    boolean permits(int next) {
      if(next!=DENY&&next!=DEFAULT)return false;
      // Keep playback, DRM and irreversible persistent-storage policies unchanged.
      if(type==0||type==1||type==3||type==8||type==9||type==10)return true;
      return type==7&&next==DENY;
    }
    String title() {
      switch(type) {
        case 0:return "位置";case 1:return "网站通知";case 2:return "持久存储";case 3:return "扩展现实（XR）";
        case 4:return "静音自动播放";case 5:return "有声自动播放";case 6:return "受保护媒体（DRM）";
        case 7:return "跟踪保护例外";case 8:return "第三方存储访问";
        case 9:return "本机设备访问";case 10:return "本地网络访问";default:return "其他原生权限";
      }
    }
    String valueLabel() {
      if(type==7)return value==ALLOW?"已有跟踪保护例外":value==DENY?"无跟踪保护例外":"内核默认";
      return value==ALLOW?"已允许":value==DENY?"已拒绝":"内核默认";
    }
  }

  interface Backend {
    Scope current();
    void read(Scope scope,Consumer<List<Entry>> success,Consumer<String> failure);
    void write(Scope scope,Entry permission,int value);
    void later(Runnable action,long delay);
    void cancel(Runnable action);
  }
  static final class Result {
    final String status,message;final List<Entry> entries;final boolean confirmed;
    Result(String status,String message,List<Entry> entries,boolean confirmed) {
      this.status=status;this.message=message;this.entries=Collections.unmodifiableList(new ArrayList<>(entries));this.confirmed=confirmed;
    }
  }

  /** Main-handler confined. Each async result must still own the exact page and native runtime. */
  static final class Manager {
    final Backend backend;final Scope scope;
    private long revision;private boolean closed;private List<Entry> shown=Collections.emptyList();
    private final Set<Runnable> timers=new HashSet<>();
    Manager(Backend backend,Scope scope) {this.backend=backend;this.scope=scope;}
    boolean current() {return !closed&&scope!=null&&scope.matches(backend.current());}
    void close() {closed=true;revision++;for(Runnable timer:new ArrayList<>(timers))backend.cancel(timer);timers.clear();shown=Collections.emptyList();}
    private long begin() {revision++;for(Runnable timer:new ArrayList<>(timers))backend.cancel(timer);timers.clear();return revision;}
    private boolean active(long ticket) {return !closed&&ticket==revision;}
    private Result result(String status,String message,List<Entry> entries,boolean confirmed) {return new Result(status,message,entries,confirmed);}
    private void stale(Consumer<Result> complete) {shown=Collections.emptyList();complete.accept(result("stale","页面或环境已变化，请关闭后重新打开站点权限。",shown,false));}
    private List<Entry> checked(List<Entry> input) {
      if(input==null||input.size()>MAX_ROWS)throw new IllegalArgumentException("permission-count");
      ArrayList<Entry> output=new ArrayList<>();
      for(Entry row:input) {
        if(row==null||!row.belongs(scope))throw new IllegalArgumentException("permission-scope");
        for(Entry prior:output)if(row.sameKey(prior))throw new IllegalArgumentException("permission-duplicate");
        output.add(row);
      }
      output.sort((a,b)->{int type=Integer.compare(a.type,b.type);return type!=0?type:Objects.toString(a.thirdPartyOrigin,"").compareTo(Objects.toString(b.thirdPartyOrigin,""));});
      return output;
    }
    private void read(long ticket,Consumer<List<Entry>> success,Consumer<String> failure) {
      if(!active(ticket))return;
      if(!current()){failure.accept("stale");return;}
      boolean[] settled={false};
      Runnable timeout=()->{if(!active(ticket)||settled[0])return;settled[0]=true;failure.accept("timeout");};
      timers.add(timeout);backend.later(timeout,READ_TIMEOUT_MS);
      Consumer<String> fail=reason->{if(!active(ticket)||settled[0])return;settled[0]=true;timers.remove(timeout);backend.cancel(timeout);failure.accept(reason);};
      try {
        backend.read(scope,rows->{
          if(!active(ticket)||settled[0])return;
          settled[0]=true;timers.remove(timeout);backend.cancel(timeout);
          if(!current()){failure.accept("stale");return;}
          List<Entry> checked;
          try{checked=checked(rows);}catch(RuntimeException invalid){failure.accept("invalid");return;}
          success.accept(checked);
        },fail);
      }catch(RuntimeException unavailable){fail.accept("unavailable");}
    }
    void refresh(Consumer<Result> complete) {
      long ticket=begin();shown=Collections.emptyList();
      if(!current()){stale(complete);return;}
      read(ticket,rows->{shown=rows;complete.accept(result("ready",rows.isEmpty()?"此站点没有已保存的原生权限记录。":"已读取当前环境、此站点的原生记录。",rows,false));},
          reason->{if("stale".equals(reason))stale(complete);else complete.accept(result("failed","原生权限暂未读到，请重试。",Collections.emptyList(),false));});
    }
    void change(Entry selected,int desired,Consumer<Result> complete) {
      boolean offered=shown.contains(selected);long ticket=begin();shown=Collections.emptyList();
      if(!current()){stale(complete);return;}
      if(!offered||selected==null||!selected.belongs(scope)||!selected.permits(desired)) {
        complete.accept(result("failed","此项不支持该操作，请重新读取权限。",shown,false));return;
      }
      // A UI record is only an intent. Re-read and retain Gecko's fresh original object/principal.
      read(ticket,rows->{
        Entry fresh=find(rows,selected);
        if(fresh!=null&&fresh.value==desired){shown=rows;complete.accept(result("confirmed","原生回读已确认当前设置。",rows,true));return;}
        if(fresh==null||fresh.value!=selected.value||!fresh.permits(desired)) {
          shown=rows;complete.accept(result("changed","权限在操作前已变化，请核对后重试。",rows,false));return;
        }
        if(!current()){stale(complete);return;}
        try{backend.write(scope,fresh,desired);}catch(RuntimeException failure){complete.accept(result("failed","原生权限设置未完成，请重新读取。",Collections.emptyList(),false));return;}
        confirm(ticket,selected,desired,0,complete);
      },reason->{if("stale".equals(reason))stale(complete);else complete.accept(result("failed","未取得设置前的原生记录，尚未修改。",Collections.emptyList(),false));});
    }
    private Entry find(List<Entry> rows,Entry target) {for(Entry row:rows)if(row.sameKey(target))return row;return null;}
    private void confirm(long ticket,Entry selected,int desired,int attempt,Consumer<Result> complete) {
      read(ticket,rows->{
        Entry actual=find(rows,selected);
        if(actual!=null&&actual.value==desired||actual==null&&desired==DEFAULT) {
          shown=rows;complete.accept(result("confirmed",desired==DEFAULT?"原生回读已确认恢复内核默认。":"原生回读已确认拒绝。",rows,true));return;
        }
        if(attempt>=2){shown=rows;complete.accept(result("unconfirmed","请求已发送，但原生回读未确认生效。可重新读取，未自动重试写入。",rows,false));return;}
        Runnable retry=()->confirm(ticket,selected,desired,attempt+1,complete);
        timers.add(retry);backend.later(retry,attempt==0?150:350);
      },reason->{if("stale".equals(reason))stale(complete);else complete.accept(result("unconfirmed","请求已发送，但未取得原生回读。请重新读取确认。",Collections.emptyList(),false));});
    }
  }
}
