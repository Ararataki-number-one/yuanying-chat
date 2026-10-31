package local.pocketchat;

import android.app.*;
import android.content.*;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;
import android.os.Handler;
import org.json.*;
import java.lang.reflect.Field;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

public final class BackgroundReplyRuntimeHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  static void field(String name,Object value)throws Exception{Field field=BackgroundReplyPolicy.class.getDeclaredField(name);field.setAccessible(true);field.set(null,value);}
  static Application setup(int owner,boolean enabled,long revision,int pending)throws Exception {
    field("current",BackgroundReplyPolicy.Snapshot.unknown());field("latestRevision",0L);field("installed",false);Handler.reset();
    AppSettings.reset();ChatService.reset();ChatSession.reset();QuietNotifications.clears=0;ProfileCatalog.db=new SQLiteDatabase();Build.VERSION.SDK_INT=35;
    Application root=new Application();root.profiles=new Context[8];root.profiles[0]=root;for(int slot=1;slot<8;slot++)root.profiles[slot]=new Context(root,slot);
    for(int slot=0;slot<8;slot++){root.profiles[slot].preferences.values.put("backgroundWait",true);root.profiles[slot].preferences.values.put("draft","keep-draft-"+slot);}
    Application.processName=processName(root,owner);root.manager=new ActivityManager();root.manager.processes.add(process(root,owner,android.os.Process.myUid()));
    AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,enabled,revision,pending);return root;
  }
  static String processName(Context root,int slot){return root.getPackageName()+(slot==0?"":":profile"+slot);}
  static ActivityManager.RunningAppProcessInfo process(Context root,int slot,int uid){return new ActivityManager.RunningAppProcessInfo(processName(root,slot),slot==Profiles.processSlot()?android.os.Process.myPid():800+slot,uid);}
  static boolean matches(boolean enabled,long revision,int pending){BackgroundReplyPolicy.Snapshot value=BackgroundReplyPolicy.snapshot();return value.known&&value.enabled==enabled&&value.revision==revision&&value.legacyPendingMask==pending;}
  static boolean noCreation(Context root){return ChatSession.gets==0&&ChatSession.browserCreations==0&&root.providerAcquisitions==0&&root.serviceStarts==0;}

  static void receiver()throws Exception {
    Application root=setup(3,false,4,0);BackgroundReplyPolicy.install(root);BackgroundReplyPolicy.install(root);
    check("A UI process installs one dynamic package action receiver",root.registrations.size()==1&&root.registrations.get(0).filter.action.equals(root.getPackageName()+".BACKGROUND_REPLY_POLICY_CHANGED"));
    check("Modern dynamic policy receiver is not exported",root.registrations.get(0).flags==Context.RECEIVER_NOT_EXPORTED);
    check("Receiver installation reconciles locally without provider or browser acquisition",noCreation(root)&&!ChatService.calls.isEmpty()&&ChatService.calls.stream().allMatch(call->call.slot==3)&&ChatSession.instance==null);
    int before=AppSettings.reads;Context.Registration receiver=root.registrations.get(0);
    receiver.receiver.onReceive(root,null);receiver.receiver.onReceive(root,new Intent("unrelated.action"));
    check("Unrelated and null broadcasts do not trigger authority reads",AppSettings.reads==before);
    AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,true,5,0);
    receiver.receiver.onReceive(root,new Intent(BackgroundReplyPolicy.action(root)).putExtra("revision",Long.MAX_VALUE));
    check("A broadcast revision is only a hint and the authority grants enable",matches(true,5,0)&&noCreation(root));
    AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,false,6,0);
    receiver.receiver.onReceive(root,new Intent(BackgroundReplyPolicy.action(root)).putExtra("revision",0));
    check("A lower broadcast hint still reloads the newer disabled authority",matches(false,6,0));
    root=setup(0,false,1,0);Build.VERSION.SDK_INT=32;BackgroundReplyPolicy.install(root);
    check("Legacy supported Android uses the two argument dynamic registration",root.registrations.size()==1&&root.registrations.get(0).flags==0&&noCreation(root));
    root=setup(0,false,1,255);Application.processName=root.getPackageName()+":network";BackgroundReplyPolicy.bootstrap(root);BackgroundReplyPolicy.install(root);
    check("The independent proxy process does not install or bootstrap UI policy owners",root.registrations.isEmpty()&&AppSettings.reads==0&&AppSettings.initializations==0&&AppSettings.acknowledged.isEmpty()&&noCreation(root));
  }

  static void disable()throws Exception {
    Application root=setup(4,true,10,0);ChatSession session=new ChatSession();ChatSession.instance=session;
    BackgroundReplyPolicy.Snapshot value=BackgroundReplyPolicy.setEnabled(root,false);
    Set<Class<?>> targets=new HashSet<>();for(Intent intent:root.stopped)targets.add(intent.target);
    check("Global disable targets each of the eight ChatServices exactly once",root.stopped.size()==8&&targets.size()==8&&targets.equals(new HashSet<>(Arrays.asList(Profiles.SERVICES))));
    check("Global disable never targets the independent proxy transport service",root.stopped.stream().noneMatch(intent->intent.target==NetworkTransportService.class));
    check("Local disable reaches the ChatService release hook for the actual owner",ChatService.calls.size()==1&&ChatService.calls.get(0).slot==4&&!ChatService.calls.get(0).value.enabled&&!ChatService.wakeHeld&&!ChatService.running&&ChatService.releases==1);
    check("An existing same process session receives the disabled snapshot",session.changes.size()==1&&session.changes.get(0).known&&!session.changes.get(0).enabled&&session.changes.get(0).revision==11);
    check("Global disable clears reply cards and creates no browser or provider",QuietNotifications.clears>=1&&noCreation(root));
    Intent hint=root.broadcasts.size()==1?root.broadcasts.get(0):null;
    check("Policy invalidation is explicitly limited to the application package",hint!=null&&root.getPackageName().equals(hint.packageName)&&BackgroundReplyPolicy.action(root).equals(hint.action)&&hint.getLongExtra("revision",0)==value.revision&&value.revision==11);
    root=setup(0,true,1,0);BackgroundReplyPolicy.setEnabled(root,false);
    check("Disabling a profile without a session uses peek without constructing one",ChatSession.peeks==1&&ChatSession.instance==null&&noCreation(root));
    root=setup(0,true,1,0);session=new ChatSession();session.deleted=true;ChatSession.instance=session;BackgroundReplyPolicy.setEnabled(root,false);
    check("A retired session is not reactivated by policy reconciliation",session.changes.isEmpty()&&noCreation(root));
    root=setup(2,false,3,0);BackgroundReplyPolicy.setEnabled(root,true);
    check("Explicit enable does not stop reply or proxy services",root.stopped.isEmpty()&&matches(true,4,0)&&noCreation(root));
  }

  static void unknownAndRevisions()throws Exception {
    Application root=setup(1,true,20,0);BackgroundReplyPolicy.refresh(root);check("A current authoritative enable is cached",matches(true,20,0));
    AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,false,21,0);BackgroundReplyPolicy.refresh(root);
    check("A newer authoritative disable advances the cached revision",matches(false,21,0));
    AppSettings.failReads=AppSettings.failInitialization=true;ChatSession session=new ChatSession();ChatSession.instance=session;BackgroundReplyPolicy.policyChanged(root,Long.MAX_VALUE);
    check("Unavailable authority closes cached admission despite an enabling hint",!BackgroundReplyPolicy.snapshot().known&&!BackgroundReplyPolicy.enabledCached());
    check("Unknown authority reaches local service and existing session as disabled",!ChatService.calls.isEmpty()&&!ChatService.calls.get(ChatService.calls.size()-1).value.enabled&&!ChatService.wakeHeld&&!session.changes.isEmpty()&&!session.changes.get(session.changes.size()-1).enabled&&QuietNotifications.clears>0&&noCreation(root));
    AppSettings.failReads=AppSettings.failInitialization=false;AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,true,20,0);BackgroundReplyPolicy.refresh(root);
    check("A stale enable cannot return after authority failure erased the current snapshot",!BackgroundReplyPolicy.snapshot().known&&!BackgroundReplyPolicy.enabledCached());
    AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,false,22,0);BackgroundReplyPolicy.refresh(root);
    check("A fresh disabled revision restores known admission after an authority failure",matches(false,22,0));
    AppSettings.authority=new BackgroundReplyPolicy.Snapshot(true,true,23,0);BackgroundReplyPolicy.refresh(root);
    check("Only a current newer authority can reenable after failure",matches(true,23,0));
    root=setup(0,true,1,0);AppSettings.authority=BackgroundReplyPolicy.Snapshot.unknown();BackgroundReplyPolicy.policyChanged(root,999);
    check("Unknown initialization cannot be interpreted as an enable",!BackgroundReplyPolicy.enabledCached()&&!BackgroundReplyPolicy.snapshot().known&&AppSettings.initializations>0&&noCreation(root));
    root=setup(0,true,1,0);AppSettings.failSet=AppSettings.failReads=AppSettings.failInitialization=true;boolean failed=false;try{BackgroundReplyPolicy.setEnabled(root,true);}catch(IllegalStateException expected){failed=true;}
    check("A failed save with unavailable authority propagates failure while local capture stays off",failed&&!BackgroundReplyPolicy.enabledCached()&&!ChatService.wakeHeld&&root.broadcasts.isEmpty()&&noCreation(root));
  }

  static void migration()throws Exception {
    Application root=setup(0,false,1,255);
    root.manager.processes.add(process(root,2,android.os.Process.myUid()));root.manager.processes.add(process(root,5,android.os.Process.myUid()));root.manager.processes.add(process(root,3,android.os.Process.myUid()+1));
    BackgroundReplyPolicy.migrateLegacyPreferences(root);
    check("Compatibility migration skips other running owners but commits own and cold slots",AppSettings.acknowledged.equals(Arrays.asList(0,1,3,4,6,7))&&AppSettings.authority.legacyPendingMask==36&&matches(false,1,36));
    check("Running owners retain untouched preference maps for their own process",root.profiles[2].preferences.edits==0&&root.profiles[5].preferences.edits==0&&Boolean.TRUE.equals(root.profiles[2].preferences.values.get("backgroundWait"))&&Boolean.TRUE.equals(root.profiles[5].preferences.values.get("backgroundWait")));
    boolean preserved=true;for(int slot=0;slot<8;slot++)preserved&=("keep-draft-"+slot).equals(root.profiles[slot].preferences.values.get("draft"));
    check("Compatibility edits preserve unrelated synthetic draft values",preserved&&ProfileCatalog.db.balanced()&&noCreation(root));
    Application.processName=processName(root,2);BackgroundReplyPolicy.migrateLegacyPreferences(root);
    check("A running owner commits its own pending compatibility bit on natural execution",!Boolean.TRUE.equals(root.profiles[2].preferences.values.get("backgroundWait"))&&AppSettings.authority.legacyPendingMask==32&&root.profiles[5].preferences.edits==0);
    root=setup(3,false,1,255);root.manager.processes=null;BackgroundReplyPolicy.migrateLegacyPreferences(root);
    check("Unknown process liveness permits only the current owner preference commit",AppSettings.acknowledged.equals(Collections.singletonList(3))&&AppSettings.authority.legacyPendingMask==247&&root.profiles[3].preferences.commits==1);
    boolean othersUntouched=true;for(int slot=0;slot<8;slot++)if(slot!=3)othersUntouched&=root.profiles[slot].preferences.edits==0;
    check("Unknown liveness leaves every other compatibility bit pending",othersUntouched&&ProfileCatalog.db.balanced());
    root=setup(3,false,1,255);root.manager.processes=null;root.profiles[3].preferences.commitSucceeds=false;BackgroundReplyPolicy.migrateLegacyPreferences(root);
    check("An owner preference commit failure retains its durable retry bit",AppSettings.acknowledged.isEmpty()&&AppSettings.authority.legacyPendingMask==255&&Boolean.TRUE.equals(root.profiles[3].preferences.values.get("backgroundWait"))&&ProfileCatalog.db.balanced());
    root.profiles[3].preferences.commitSucceeds=true;BackgroundReplyPolicy.migrateLegacyPreferences(root);
    check("A later successful owner commit clears only its compatibility bit",AppSettings.acknowledged.equals(Collections.singletonList(3))&&AppSettings.authority.legacyPendingMask==247&&noCreation(root));
    root=setup(0,true,9,0);BackgroundReplyPolicy.migrateLegacyPreferences(root);
    check("A completed compatibility mask causes no preference writes or policy reset",AppSettings.acknowledged.isEmpty()&&matches(true,9,0)&&root.profiles[0].preferences.edits==0);
    root=setup(0,false,1,255);Build.VERSION.SDK_INT=27;Application.processName="unavailable-on-old-api";root.manager.processes.clear();root.manager.processes.add(new ActivityManager.RunningAppProcessInfo(root.getPackageName(),android.os.Process.myPid(),android.os.Process.myUid()));BackgroundReplyPolicy.bootstrap(root);
    check("Legacy Android bootstrap resolves its owner from the matching process PID",AppSettings.initializations==1&&AppSettings.authority.legacyPendingMask==0&&ProfileCatalog.db.balanced());
  }

  static void queuedHook()throws Exception {
    Application root=setup(6,false,8,0);ChatSession session=new ChatSession();ChatSession.instance=session;AtomicReference<Throwable> error=new AtomicReference<>();
    Thread worker=new Thread(()->{try{BackgroundReplyPolicy.policyChanged(root,8);}catch(Throwable failure){error.set(failure);}},"policy-invalidation-worker");worker.start();worker.join(5000);
    check("Worker invalidation queues local hooks instead of executing browser hooks on the worker",!worker.isAlive()&&error.get()==null&&Handler.pending()==1&&ChatService.calls.isEmpty()&&session.changes.isEmpty());
    Handler.drain();
    check("Queued local policy work delivers the existing session hook on host main drain",Handler.pending()==0&&ChatService.calls.size()==1&&ChatService.calls.get(0).slot==6&&session.changes.size()==1&&!session.changes.get(0).enabled&&noCreation(root));
  }

  static void failedStartupGate()throws Exception {
    Application root=setup(0,true,7,255);AppSettings.failInitializationLocked=true;boolean refused=false;
    try{BackgroundReplyPolicy.bootstrap(root);}catch(android.database.sqlite.SQLiteDatabaseLockedException expected){refused=true;}
    check("A locked authority initialization cannot allow startup past the preference gate",refused&&!BackgroundReplyPolicy.enabledCached()&&!BackgroundReplyPolicy.snapshot().known);
    check("A locked initial authority makes no compatibility preference writes",AppSettings.acknowledged.isEmpty()&&Arrays.stream(root.profiles).allMatch(profile->profile.preferences.edits==0));
    root=setup(0,true,7,255);ProfileCatalog.db.failBeginLocked=true;refused=false;
    try{BackgroundReplyPolicy.bootstrap(root);}catch(android.database.sqlite.SQLiteDatabaseLockedException expected){refused=true;}
    check("A locked compatibility writer gate cannot fall through to profile providers",refused&&!BackgroundReplyPolicy.enabledCached()&&!BackgroundReplyPolicy.snapshot().known);
    check("A failed compatibility gate preserves every profile preference map",AppSettings.acknowledged.isEmpty()&&Arrays.stream(root.profiles).allMatch(profile->profile.preferences.edits==0));
  }

  public static void main(String[] args)throws Exception {
    receiver();disable();unknownAndRevisions();migration();queuedHook();failedStartupGate();
    int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;
    System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks));if(passed!=checks.length())System.exit(1);
  }
}
