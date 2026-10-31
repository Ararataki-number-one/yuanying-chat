package android.app;
import java.util.*;
public final class ActivityManager {
  public List<RunningAppProcessInfo> processes=new ArrayList<>();public int queries;
  public List<RunningAppProcessInfo> getRunningAppProcesses(){queries++;return processes;}
  public static final class RunningAppProcessInfo {public int uid,pid;public String processName;public RunningAppProcessInfo(String name,int pid,int uid){processName=name;this.pid=pid;this.uid=uid;}}
}
