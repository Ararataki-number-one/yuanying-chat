package local.pocketchat;

import org.json.JSONObject;

/** Actual catalogue methods; storage and lifecycle setup use the existing
 * transactional host adapter, not Android SQLite or a real account. */
public final class DeleteIdentityCases {
  static void check(String name,boolean pass){DefaultEnvironmentHost.check(name,pass);}
  static void rejectConfirm(ProfileCatalog catalog,EnvironmentSpec.Identity expected,String label)throws Exception{
    String before=catalog.db.rows.toString(),settings=catalog.db.settings.toString();boolean rejected=false;
    try{catalog.beginDelete(expected);}catch(java.io.IOException changed){rejected=true;}
    check(label,rejected&&before.equals(catalog.db.rows.toString())&&settings.equals(catalog.db.settings.toString())&&catalog.db.begins==catalog.db.ends);
  }
  static void run()throws Exception{
    ProfileCatalog c=DefaultEnvironmentHost.setup(0,0,1);EnvironmentSpec.Identity shown=c.identity(1),kept=c.identity(0);
    EnvironmentSpec.Identity first=c.beginDelete(shown);
    check("A confirmed deletion returns the same UUID and exactly the next generation",first.slot==shown.slot&&first.generation==shown.generation+1&&first.environmentId.equals(shown.environmentId)&&c.deletionIdentity(1).equals(first));
    check("The other environment keeps its exact identity",c.identity(0).equals(kept));
    rejectConfirm(c,shown,"A second old confirmation does not advance an already pending deletion");
    c.completeDelete(first);c.created(1);EnvironmentSpec.Identity replacement=c.identity(1);
    check("Recreation produces a new UUID while retaining the advanced generation",!replacement.environmentId.equals(shown.environmentId)&&replacement.generation==first.generation);
    rejectConfirm(c,shown,"A confirmation opened before deletion cannot delete the replacement");
    rejectConfirm(c,new EnvironmentSpec.Identity(1,replacement.generation,shown.environmentId),"Equal generation with the old UUID is rejected");
    rejectConfirm(c,new EnvironmentSpec.Identity(1,replacement.generation+1,replacement.environmentId),"Equal UUID with a different generation is rejected");
    rejectConfirm(c,null,"A missing confirmation identity has no catalogue side effects");
    boolean expired=false;try{EnvironmentDeleteActivity.requireCurrent(c,first);}catch(EnvironmentDeleteActivity.Expired expected){expired=true;}
    check("An old worker cannot enter cleanup after the replacement has been created",expired&&c.identity(1).equals(replacement));
    EnvironmentSpec.Identity second=c.beginDelete(replacement);String pending=c.db.rows.toString();expired=false;
    try{EnvironmentDeleteActivity.requireCurrent(c,first);}catch(EnvironmentDeleteActivity.Expired expected){expired=true;}
    boolean completed=false;try{c.completeDelete(first);}catch(java.io.IOException expected){completed=true;}
    check("An old worker also cannot complete another deletion occupying its slot",expired&&completed&&pending.equals(c.db.rows.toString())&&c.deletionIdentity(1).equals(second));
    EnvironmentDeleteActivity.requireCurrent(c,second);c.completeDelete(second);
    check("The currently confirmed deletion can finish",!c.item(1).optBoolean("deleting")&&!c.item(1).optBoolean("created")&&c.item(1).optString("environmentId").isEmpty());
    c=DefaultEnvironmentHost.setup(1,0,1);shown=c.identity(1);String before=c.db.rows.toString();c.db.failDefaultWrite=true;boolean failed=false;
    try{c.beginDelete(shown);}catch(java.io.IOException expected){failed=true;}
    check("Default persistence failure still rolls back the complete confirmed deletion",failed&&before.equals(c.db.rows.toString())&&c.identity(1).equals(shown)&&c.db.begins==c.db.ends);
    // This is the exact operation made by the old UI. It remains available for
    // legacy internal fixtures, so the production UI must use the typed API.
    c=DefaultEnvironmentHost.setup(0,0,1);shown=c.identity(1);first=c.beginDelete(shown);c.completeDelete(first);c.created(1);replacement=c.identity(1);c.beginDelete(shown.slot);
    check("The former slot-only UI operation reproduces deletion of a replacement",c.deletionIdentity(1).environmentId.equals(replacement.environmentId)&&!replacement.environmentId.equals(shown.environmentId));
  }
  public static void main(String[] args)throws Exception{
    DefaultEnvironmentHost.current();DefaultEnvironmentHost.concurrency();DefaultEnvironmentHost.routing();run();
    int passed=0;for(int i=0;i<DefaultEnvironmentHost.checks.length();i++)if(DefaultEnvironmentHost.checks.optJSONObject(i).optBoolean("pass"))passed++;
    System.out.println(J.obj("status",passed==DefaultEnvironmentHost.checks.length()?"passed":"failed","passed",passed,"total",DefaultEnvironmentHost.checks.length(),"actualAndroidExecution",false,"checks",DefaultEnvironmentHost.checks));
    if(passed!=DefaultEnvironmentHost.checks.length())System.exit(1);
  }
}
