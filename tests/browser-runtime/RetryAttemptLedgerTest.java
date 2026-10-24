package local.pocketchat;

/** Host-only callback replay; no Android timing or product execution claim. */
public final class RetryAttemptLedgerTest {
  static int checks;
  static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);checks++;}
  static void rejects(Runnable action,String name){try{action.run();}catch(IllegalStateException expected){checks++;return;}throw new AssertionError(name);}
  static void admit(RetryAttemptLedger ledger,String id,String snapshot,long at){ledger.admit(id,"environment",1,snapshot);ledger.start(id,at);}
  static void retire(RetryAttemptLedger ledger,String id,long at){check(ledger.deferred(id,at,true,true,1),"actual retirement is counted");}
  public static void main(String[] args){
    RetryAttemptLedger ledger=new RetryAttemptLedger();ledger.open("retry-invalid","external-a");
    admit(ledger,"external-a","candidate-a",100);retire(ledger,"external-a",200);
    for(int i=1;i<=5;i++){admit(ledger,"internal:a"+i,"candidate-a",200+i*100);retire(ledger,"internal:a"+i,250+i*100);}
    ledger.close(6);ledger.open("retry-timeout","external-b");
    admit(ledger,"external-b","candidate-b",386604);
    check(!ledger.deferred("internal:a5",386604,false,true,1),"previous recovery callback is retained but cannot retire current case");
    check(ledger.callbacks.get(ledger.callbacks.size()-1).attempt.owner.name.equals("retry-invalid"),"late callback keeps original owner");
    retire(ledger,"external-b",389162);
    for(int i=1;i<=3;i++){admit(ledger,"internal:b"+i,"candidate-b",389200+i*5000);retire(ledger,"internal:b"+i,391800+i*5000);}
    check(ledger.current.attempts.size()==4,"late callback does not create fifth timeout attempt");
    rejects(()->ledger.close(6),"four real attempts cannot complete five retries and recovery");
    check(!ledger.deferred("internal:b3",410000,false,true,1),"same-case duplicate callback is not another retirement");
    rejects(()->ledger.deferred("internal:b3",410001,true,true,1),"double actual retirement is rejected");
    rejects(()->ledger.admit("internal:wrong-environment","other",1,"candidate-b"),"wrong environment cannot impersonate owner");
    rejects(()->ledger.admit("internal:wrong-generation","environment",2,"candidate-b"),"wrong generation cannot impersonate owner");
    rejects(()->ledger.admit("internal:wrong-candidate","environment",1,"candidate-a"),"old candidate cannot enter new case");
    rejects(()->ledger.admit("internal:b3","environment",1,"candidate-b"),"duplicate admission is rejected");
    admit(ledger,"internal:b4","candidate-b",420000);retire(ledger,"internal:b4",422600);
    admit(ledger,"internal:b5","candidate-b",422800);
    rejects(()->ledger.close(6),"missing recovery retirement cannot be hidden");
    rejects(()->ledger.deferred("internal:b5",423000,false,true,2),"inactive callback cannot fabricate an unobserved retirement");
    retire(ledger,"internal:b5",423100);ledger.close(6);
    check(ledger.current.closed&&ledger.current.attempts.size()==6,"five real retries plus real recovery complete case");
    int before=ledger.callbacks.size();
    rejects(()->ledger.deferred("internal:unowned",424000,false,true,1),"unowned callback fails instead of being filtered");
    check(ledger.callbacks.size()==before+1,"rejected unowned callback remains raw evidence");
    RetryAttemptLedger unfinished=new RetryAttemptLedger();unfinished.open("one","outside");
    admit(unfinished,"outside","candidate",100);
    rejects(()->unfinished.open("two","outside-two"),"new case cannot clear unfinished ownership");
    rejects(()->unfinished.deferred("outside",150,true,false,2),"active but not retired job cannot advance count");
    System.out.println("RetryAttemptLedger host controls: "+checks+" passed; actualAndroidExecution=false");
  }
}
