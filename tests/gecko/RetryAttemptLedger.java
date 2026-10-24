package local.pocketchat;

import java.util.*;

/** Test-only ownership ledger. A callback invocation is not proof of retirement. */
final class RetryAttemptLedger {
  static final class Case {
    final String name,externalId;String environment="",snapshotHash="";int generation;
    boolean closed;final List<Attempt> attempts=new ArrayList<>();
    Case(String name,String externalId){this.name=name;this.externalId=externalId;}
  }
  static final class Attempt {
    final Case owner;final String id;long started=-1,retired=-1;int jobCount=-1;
    Attempt(Case owner,String id){this.owner=owner;this.id=id;}
  }
  static final class Callback {
    final Attempt attempt;final String id;final long at;final boolean wasActive,isRetired;final int jobCount;
    Callback(Attempt attempt,String id,long at,boolean wasActive,boolean isRetired,int jobCount){this.attempt=attempt;this.id=id;this.at=at;this.wasActive=wasActive;this.isRetired=isRetired;this.jobCount=jobCount;}
  }
  final List<Case> cases=new ArrayList<>();final List<Callback> callbacks=new ArrayList<>();
  final Map<String,Attempt> admitted=new LinkedHashMap<>();Case current;
  Case open(String name,String externalId){
    if(current!=null&&!current.closed)throw new IllegalStateException("Previous retry case is not closed");
    for(Case row:cases)if(row.name.equals(name)||row.externalId.equals(externalId))throw new IllegalStateException("Duplicate retry case");
    current=new Case(name,externalId);cases.add(current);return current;
  }
  void admit(String id,String environment,int generation,String snapshotHash){
    if(current==null||admitted.containsKey(id)||environment.isEmpty()||snapshotHash.isEmpty())throw new IllegalStateException("Invalid retry admission");
    Case owner=null;
    if(current.externalId.equals(id)){
      if(!current.attempts.isEmpty())throw new IllegalStateException("External retry admission is not first");
      owner=current;owner.environment=environment;owner.generation=generation;owner.snapshotHash=snapshotHash;
    }else if(id.startsWith("internal:")){
      for(Case row:cases)if(row.environment.equals(environment)&&row.generation==generation&&row.snapshotHash.equals(snapshotHash)){
        if(owner!=null)throw new IllegalStateException("Ambiguous retry candidate ownership");owner=row;
      }
    }
    if(owner==null||owner!=current||owner.closed)throw new IllegalStateException("Retry admission has no live owning case");
    Attempt attempt=new Attempt(owner,id);admitted.put(id,attempt);owner.attempts.add(attempt);
  }
  Attempt start(String id,long at){
    Attempt attempt=require(id);if(attempt.owner!=current||attempt.owner.closed||attempt.started>=0)throw new IllegalStateException("Invalid retry preparation");
    attempt.started=at;return attempt;
  }
  boolean deferred(String id,long at,boolean wasActive,boolean isRetired,int jobCount){
    Attempt attempt=admitted.get(id);callbacks.add(new Callback(attempt,id,at,wasActive,isRetired,jobCount));
    if(attempt==null)throw new IllegalStateException("Unowned retry callback");
    // Production deliberately ignores a callback after this Transition retired.
    if(!wasActive){if(attempt.retired<0)throw new IllegalStateException("Retry retirement was not observed");return false;}
    if(!isRetired||attempt.owner!=current||attempt.owner.closed||attempt.started<0||attempt.retired>=0||at<attempt.started)throw new IllegalStateException("Invalid retry retirement");
    attempt.retired=at;attempt.jobCount=jobCount;return true;
  }
  Attempt require(String id){Attempt value=admitted.get(id);if(value==null)throw new IllegalStateException("Unowned retry attempt");return value;}
  void close(int expected){
    if(current==null||current.closed||current.attempts.size()!=expected)throw new IllegalStateException("Incomplete retry case admissions");
    for(Attempt attempt:current.attempts)if(attempt.started<0||attempt.retired<attempt.started)throw new IllegalStateException("Retry case still owns unfinished work");
    current.closed=true;
  }
}
