package local.pocketchat;

/** Immutable, document-bound work observation. Unknown never authorizes a switch. */
final class TaskGuardSnapshot {
  final boolean known,replyBusy,fileBusy,submitting,operation,downloading;
  final int slot,generation;final String environmentId,resourceBinding,documentId;
  final long navigationEpoch,resourceSequence,workGeneration;
  TaskGuardSnapshot(boolean known,boolean replyBusy,boolean fileBusy,boolean submitting,boolean operation,boolean downloading,int slot,int generation,String environmentId,long navigationEpoch,String binding,String document,long sequence,long workGeneration){
    this.known=known;this.replyBusy=replyBusy;this.fileBusy=fileBusy;this.submitting=submitting;this.operation=operation;this.downloading=downloading;this.slot=slot;this.generation=generation;this.environmentId=environmentId;this.navigationEpoch=navigationEpoch;resourceBinding=binding;documentId=document;resourceSequence=sequence;this.workGeneration=workGeneration;
  }
  boolean busyOrUnknown(){return !known||replyBusy||fileBusy||submitting||operation||downloading;}
  boolean sameWork(TaskGuardSnapshot other){return other!=null&&slot==other.slot&&generation==other.generation&&environmentId.equals(other.environmentId)&&navigationEpoch==other.navigationEpoch&&resourceBinding.equals(other.resourceBinding)&&documentId.equals(other.documentId)&&resourceSequence==other.resourceSequence&&workGeneration==other.workGeneration&&known==other.known&&replyBusy==other.replyBusy&&fileBusy==other.fileBusy&&submitting==other.submitting&&operation==other.operation&&downloading==other.downloading;}
}
