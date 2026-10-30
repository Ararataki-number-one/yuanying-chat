package local.pocketchat;
import java.io.*;import java.util.*;import org.json.*;

public final class EnvironmentConfigTransferHost {
  static final JSONArray checks=new JSONArray();interface Action{void run()throws Exception;}
  static void check(String name,boolean pass)throws Exception{checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static void rejected(String name,Action action)throws Exception{boolean failed=false;try{action.run();}catch(Exception expected){failed=true;}check(name,failed);}
  static void reset()throws Exception{for(int i=0;i<8;i++){Profiles.contexts[i]=new TestContext(i);ProfileCatalog.INSTANCE.created[i]=i==0;ProfileCatalog.INSTANCE.ids[i]="identity-"+i;ProfileCatalog.INSTANCE.names[i]="环境"+i;ProfileCatalog.INSTANCE.desktop[i]=false;}ProfileCatalog.INSTANCE.replaceOnItem=false;ProfileCatalog.INSTANCE.failAfterAction=false;ProfileCatalog.INSTANCE.failAfterCommit=false;ProfileCatalog.INSTANCE.replaceAfterActionField=null;ProfileCatalog.INSTANCE.afterAction=null;EnvironmentSpecRepository.failInitialize=false;EnvironmentSpecRepository.wrongLoadedIdentity=false;EnvironmentResetActivity.rootsValid=true;Profiles.contexts[0].prefs.values.put("proxy","secret-proxy");Profiles.contexts[0].vault.put("cookie",new byte[]{1,2,3});}
  static String oldFingerprint(){TestContext old=Profiles.contexts[0];return ProfileCatalog.INSTANCE.names[0]+ProfileCatalog.INSTANCE.ids[0]+ProfileCatalog.INSTANCE.created[0]+old.prefs.values+Arrays.toString(old.vault.get("cookie"));}
  static EnvironmentConfigBackup.Config config()throws Exception{JSONObject preferences=new JSONObject();for(String k:EnvironmentConfigBackup.PREFERENCES)preferences.put(k,true);return new EnvironmentConfigBackup.Config("恢复的环境",BrowserIdentitySpec.preset(BrowserIdentitySpec.RFP).json(),preferences);}
  public static void main(String[] args)throws Exception{
    reset();TestContext root=Profiles.contexts[0];String old=oldFingerprint();EnvironmentConfigBackup.Config config=config();EnvironmentSpec.Identity saved=EnvironmentConfigTransfer.restore(root,1,config,()->true);
    check("fresh identity not imported from source",saved.slot==1&&!saved.environmentId.equals(ProfileCatalog.INSTANCE.ids[0]));check("fresh environment becomes created",ProfileCatalog.INSTANCE.created[1]);
    TestContext dest=Profiles.contexts[1];check("network requires new configuration",Boolean.FALSE.equals(dest.prefs.values.get("networkConfigured")));check("external VPN required",Boolean.TRUE.equals(dest.prefs.values.get("requireExternalVpn")));check("no imported proxy",!dest.prefs.values.containsKey("proxy"));check("no internal route restored",dest.prefs.values.get("networkMode").equals("external"));
    check("browser protection restored as requested",Integer.valueOf(2).equals(dest.prefs.values.get("privacyLevel")));check("only browser spec in destination vault",dest.vault.size()==1&&dest.vault.containsKey("environment-spec"));check("name restored",ProfileCatalog.INSTANCE.names[1].equals("恢复的环境"));check("old environment unchanged after success",old.equals(oldFingerprint()));
    final TestContext initial=root;rejected("occupied environment rejected",()->EnvironmentConfigTransfer.restore(initial,0,config,()->true));check("occupied environment bytes unchanged",old.equals(oldFingerprint()));
    for(String stage:new String[]{"preferences","vault","stale-before","stale-enter","stale-after","browser-data","roots"}){
      reset();root=Profiles.contexts[0];final TestContext source=root;String before=oldFingerprint();TestContext target=Profiles.contexts[1];
      if(stage.equals("preferences"))target.prefs.failAt=1;if(stage.equals("vault"))EnvironmentSpecRepository.failInitialize=true;if(stage.equals("browser-data"))target.browserData=true;if(stage.equals("roots"))EnvironmentResetActivity.rootsValid=false;
      final int[] calls={0};final int expire=stage.equals("stale-before")?1:stage.equals("stale-enter")?2:stage.equals("stale-after")?3:100;
      rejected(stage+" fails closed",()->EnvironmentConfigTransfer.restore(source,1,config,()->++calls[0]<expire));
      check(stage+" does not publish half environment",!ProfileCatalog.INSTANCE.created[1]);check(stage+" retains old bytes",before.equals(oldFingerprint()));
      if(!stage.equals("browser-data")&&!stage.equals("roots")&&!stage.equals("stale-before")&&!stage.equals("stale-enter")){check(stage+" cleans staged settings",target.prefs.values.isEmpty()&&target.vault.isEmpty());}
    }
    reset();root=Profiles.contexts[0];EnvironmentSpec.Identity expected=ProfileCatalog.INSTANCE.identity(0);EnvironmentConfigBackup.Config exported=EnvironmentConfigTransfer.capture(root,expected);check("capture excludes source identity",!new String(exported.bytes(),"UTF-8").contains(expected.environmentId));
    final TestContext source=root;rejected("stale source ownership rejected",()->EnvironmentConfigTransfer.capture(source,new EnvironmentSpec.Identity(0,"another")));
    EnvironmentSpecRepository.wrongLoadedIdentity=true;rejected("loaded spec ownership mismatch rejected",()->EnvironmentConfigTransfer.capture(source,expected));
    EnvironmentSpecRepository.wrongLoadedIdentity=false;ProfileCatalog.INSTANCE.replaceOnItem=true;rejected("delete recreate during final capture rejected",()->EnvironmentConfigTransfer.capture(source,expected));
    reset();final TestContext postAction=Profiles.contexts[0];String postActionBefore=oldFingerprint();ProfileCatalog.INSTANCE.failAfterAction=true;
    rejected("failure after action before catalog commit is handled",()->EnvironmentConfigTransfer.restore(postAction,1,config,()->true));
    check("post action failure cleans owned marker and staged files",Profiles.contexts[1].prefs.values.isEmpty()&&Profiles.contexts[1].vault.isEmpty());check("cleanup reservation never creates empty environment",!ProfileCatalog.INSTANCE.created[1]);check("post action failure retains old environment",postActionBefore.equals(oldFingerprint()));
    for(String field:new String[]{"configRestoreBatch","configRestoreIdentity","configRestoreGeneration"}){
      reset();final TestContext raced=Profiles.contexts[0];ProfileCatalog.INSTANCE.replaceAfterActionField=field;
      rejected("foreign staged "+field+" rejected",()->EnvironmentConfigTransfer.restore(raced,1,config,()->true));
      check("foreign staged "+field+" not erased",Profiles.contexts[1].vault.containsKey("foreign-pending")&&!Profiles.contexts[1].prefs.values.isEmpty());check("foreign staged cleanup does not publish",!ProfileCatalog.INSTANCE.created[1]);
    }
    reset();final TestContext committed=Profiles.contexts[0];String committedBefore=oldFingerprint();ProfileCatalog.INSTANCE.failAfterCommit=true;
    rejected("commit acknowledgement failure reports unconfirmed result",()->EnvironmentConfigTransfer.restore(committed,1,config,()->true));
    check("possibly committed new environment never force cleaned",ProfileCatalog.INSTANCE.created[1]&&Profiles.contexts[1].vault.containsKey("environment-spec")&&!Profiles.contexts[1].prefs.values.isEmpty());check("commit acknowledgement failure retains old environment",committedBefore.equals(oldFingerprint()));
    reset();java.util.concurrent.atomic.AtomicBoolean visible=new java.util.concurrent.atomic.AtomicBoolean(true);ProfileCatalog.INSTANCE.afterAction=()->visible.set(false);EnvironmentConfigTransfer.restore(Profiles.contexts[0],1,config,visible::get);
    check("documented late close may finish already submitted creation",ProfileCatalog.INSTANCE.created[1]);
    System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualSQLiteExecution",false,"actualAndroidExecution",false));
  }
}
