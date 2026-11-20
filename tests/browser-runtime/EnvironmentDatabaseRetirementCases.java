package local.pocketchat;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.Paths;

public final class EnvironmentDatabaseRetirementCases {
  static final String[] NAMES={"conversations.db","deliveries.db","draft-archive.db",ReplyNoticeLedger.DATABASE};
  static final String[] SUFFIXES={"","-wal","-shm","-journal"};
  private static int checks;

  private static void check(boolean passed,String label){if(!passed)throw new AssertionError(label);checks++;}
  private static void write(Path path)throws IOException{Files.write(path,new byte[]{7});}
  private static void retire(Context profile)throws IOException{EnvironmentResetActivity.removeLoginDatabases(profile);}
  private static boolean refused(Context profile)throws IOException{
    try{retire(profile);return false;}catch(IOException pending){return true;}
  }

  private static void verifyRetry(Path directory,String blockedSuffix,boolean reportSuccess)throws Exception{
    Files.createDirectories(directory);
    Context profile=new Context(directory,"");
    for(String name:NAMES)for(String suffix:SUFFIXES)write(directory.resolve(name+suffix));
    Path preserved=directory.resolve("saved-download-library.db"),foreign=directory.resolve("env2_conversations.db");
    write(preserved);write(foreign);

    Path blocked=directory.resolve(NAMES[0]+blockedSuffix);
    profile.blocked=blocked;profile.reportSuccess=reportSuccess;
    check(refused(profile)&&Files.isRegularFile(blocked),"An unremoved file must keep maintenance pending: "+blockedSuffix);
    profile.blocked=null;
    retire(profile);
    for(String name:NAMES)for(String suffix:SUFFIXES)
      if(!Files.notExists(directory.resolve(name+suffix),LinkOption.NOFOLLOW_LINKS))throw new AssertionError("Retry left "+name+suffix);
    check(Files.size(preserved)==1&&Files.size(foreign)==1,"Retry must preserve the shared index and another slot");
    int calls=profile.calls;
    retire(profile);
    check(profile.calls==calls+NAMES.length,"Already absent databases permit repeat with false Android returns");
  }

  private static void verifyLinks(Path directory)throws Exception{
    Files.createDirectories(directory);
    Path foreign=directory.resolve("target");Files.createDirectory(foreign);
    Path file=foreign.resolve(NAMES[0]);write(file);
    Path linkedRoot=directory.resolve("linked-databases");Files.createSymbolicLink(linkedRoot,foreign);
    Context linked=new Context(linkedRoot,"");
    check(refused(linked)&&linked.calls==0&&Files.size(file)==1,"Linked database directory must be rejected before Android deletion");

    Context normal=new Context(directory,"env2_");
    Path dangling=directory.resolve("env2_"+NAMES[0]+"-wal");
    Files.createSymbolicLink(dangling,foreign.resolve("absent"));
    normal.blocked=dangling;normal.reportSuccess=true;
    check(refused(normal)&&Files.isSymbolicLink(dangling),"A dangling sidecar still occupies the target path");
    normal.blocked=null;
    retire(normal);
    check(Files.notExists(dangling,LinkOption.NOFOLLOW_LINKS)&&Files.size(file)==1,"Retry unlinks the sidecar without following it");
  }

  public static void main(String[] args)throws Exception{
    Path root=Paths.get(args[0]);
    verifyRetry(root.resolve("main"),"",false);
    for(String suffix:new String[]{"-wal","-shm","-journal"})verifyRetry(root.resolve(suffix),suffix,true);
    verifyLinks(root.resolve("links"));
    Context empty=new Context(root.resolve("missing"),"");
    retire(empty);
    check(Files.notExists(empty.dir),"Absent database directory is allowed");
    check(Files.isDirectory(root),"The storage root is preserved");
    check(empty.calls==NAMES.length,"All supported database names were checked");
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false}");
  }
}

/** Controlled Android delete result with actual temporary filesystem entries. */
final class Context {
  final Path dir;
  final String prefix;
  Path blocked;
  boolean reportSuccess;
  int calls;

  Context(Path dir,String prefix){this.dir=dir;this.prefix=prefix;}
  File getDatabasePath(String name){return dir.resolve(prefix+name).toFile();}
  boolean deleteDatabase(String name){
    calls++;
    boolean removed=false;
    for(String suffix:EnvironmentDatabaseRetirementCases.SUFFIXES){
      Path file=dir.resolve(prefix+name+suffix);
      if(file.equals(blocked))continue;
      try{removed|=Files.deleteIfExists(file);}catch(IOException problem){throw new IllegalStateException(problem);}
    }
    return blocked==null?removed:reportSuccess;
  }
}
