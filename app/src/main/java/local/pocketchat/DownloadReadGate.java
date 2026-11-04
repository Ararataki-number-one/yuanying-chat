package local.pocketchat;

/** One display read at a time; only a newer document/query or library revision needs a replay. */
final class DownloadReadGate {
  private boolean running,pending;private long issuedEpoch,issuedRevision;
  boolean begin(long epoch,long revision){
    if(running){pending|=epoch!=issuedEpoch||revision!=issuedRevision;return false;}
    running=true;pending=false;issuedEpoch=epoch;issuedRevision=revision;return true;
  }
  void complete(){running=false;}
  boolean replay(long epoch){boolean again=pending||epoch!=issuedEpoch;pending=false;return again;}
}
