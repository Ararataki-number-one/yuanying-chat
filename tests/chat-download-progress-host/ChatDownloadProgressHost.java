package local.pocketchat;
import org.json.*;
public final class ChatDownloadProgressHost {
  static int checks;static void check(boolean value,String name){if(!value)throw new AssertionError(name);checks++;}
  static JSONObject task(String state,long received,long total){return J.obj("id","download","slot",2,"environmentId","owned-environment","environmentGeneration",4,"name","file.zip","state",state,"received",received,"total",total);}
  static ChatDownloadProgress read(JSONObject row){return ChatDownloadProgress.read(row,2,"owned-environment",4);}
  public static void main(String[] args)throws Exception{
    ChatDownloadProgress state=read(task("preparing",0,-1));check(state.busy&&!state.determinate&&state.progress==0,"Preparing is visible without invented total or percentage");
    state=read(task("downloading",250,1000));check(state.determinate&&state.progress==250&&state.received==250,"Real received bytes drive the progress bar");
    check(read(task("downloading",500,1000)).progress>state.progress,"Later byte observations advance progress");
    state=read(task("downloading",900,-1));check(state.busy&&!state.determinate&&state.received==900,"Chunked response shows bytes without a fabricated percentage");
    state=read(task("saving",1000,1000));check(state.busy&&!state.finished&&state.progress==1000,"Received bytes do not claim publication before saving completes");
    check(read(task("paused",400,1000)).progress==400&&!read(task("paused",400,1000)).busy,"Pause retains the real partial progress");
    check(read(task("saved",900,-1)).progress==1000&&read(task("saved",900,-1)).total==900,"A completed unknown-length file shows its final measured size");
    check(read(task("saved",0,-1)).progress==1000,"A saved empty file completes without division by zero");
    check(read(task("failed",300,1000)).finished&&!read(task("failed",300,1000)).busy,"Failure remains a terminal visible state");
    check(read(task("cancelled",300,1000)).finished,"Cancellation is retained independently of byte progress");
    check(read(task("downloading",Long.MAX_VALUE,Long.MAX_VALUE)).progress==1000,"Large counters do not overflow percentage arithmetic");
    check(read(task("downloading",-2,1000)).received==0,"Negative received bytes cannot produce negative progress");
    check(read(task("downloading",1200,1000)).progress==1000,"Displayed progress is bounded when counters exceed a declared total");
    check(read(task("downloading",0,0)).determinate==false,"An unknown or zero total remains indeterminate during transfer");
    check(read(null)==null,"No task produces no chat card");check(read(task("other",1,10))==null,"Unknown states do not invent progress");
    check(read(task("downloading",1,10).put("slot",3))==null,"Another environment slot cannot appear in this chat");
    check(read(task("downloading",1,10).put("environmentId","replaced"))==null,"A replacement environment cannot reuse the previous card");
    check(read(task("downloading",1,10).put("environmentGeneration",5))==null,"A reset generation cannot reuse the previous card");
    System.out.println(J.obj("status","passed","passed",checks,"actualAndroidExecution",false,"scope","Actual chat progress projection using real task counters and owner boundaries"));
  }
}
