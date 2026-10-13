package local.pocketchat;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Real filesystem checks for the production environment-root admission policy. */
public final class EnvironmentDeleteRootPolicyTest {
  static int checks;
  static void require(boolean value,String name){if(!value)throw new AssertionError(name);checks++;}
  static boolean rejected(File root,int slot){try{EnvironmentBrowserData.root(root,slot);return false;}catch(IOException expected){return true;}}
  static Path marker(Path directory)throws Exception{Files.createDirectories(directory);Path marker=directory.resolve("private-marker");Files.write(marker,new byte[]{31,32,33});return marker;}
  static boolean unchanged(Path marker)throws Exception{return java.util.Arrays.equals(Files.readAllBytes(marker),new byte[]{31,32,33});}
  public static void main(String[] args)throws Exception{
    Path temporary=Files.createTempDirectory("environment-delete-root-policy-");
    try{
      Path valid=Files.createDirectory(temporary.resolve("valid"));Path shared=marker(valid);
      require(EnvironmentBrowserData.root(valid.toFile(),0).equals(valid.toFile().getCanonicalFile())&&unchanged(shared),"Slot zero retains its trusted shared root");
      File environment=EnvironmentBrowserData.root(valid.toFile(),1);Path own=marker(environment.toPath());
      require(environment.equals(valid.resolve("profiles/env1").toFile())&&unchanged(own)&&unchanged(shared),"Valid other-slot root is private and does not clear data");
      Path outside=Files.createDirectory(temporary.resolve("other-environment"));Path other=marker(outside);
      Path trustedLink=Files.createSymbolicLink(temporary.resolve("trusted-link"),outside);
      require(rejected(trustedLink.toFile(),0)&&unchanged(other),"A linked trusted root is refused without touching another environment");
      Path profilesRoot=Files.createDirectory(temporary.resolve("profiles-link-root"));Files.createSymbolicLink(profilesRoot.resolve("profiles"),outside);
      require(rejected(profilesRoot.toFile(),1)&&unchanged(other),"A linked profiles ancestor is refused before directory enumeration");
      Path environmentRoot=Files.createDirectory(temporary.resolve("environment-link-root"));Path profiles=Files.createDirectory(environmentRoot.resolve("profiles"));Files.createSymbolicLink(profiles.resolve("env1"),outside);
      require(rejected(environmentRoot.toFile(),1)&&unchanged(other),"A linked environment ancestor is refused before child deletion");
      // First admission was valid. A writer then substitutes the environment
      // directory; a second admission after writers exit must reject it.
      Path secondRoot=Files.createDirectory(temporary.resolve("second-admission"));File first=EnvironmentBrowserData.root(secondRoot.toFile(),1);Files.delete(first.toPath());Files.createSymbolicLink(first.toPath(),outside);
      require(rejected(secondRoot.toFile(),1)&&unchanged(other),"Second admission catches an ancestor link introduced after first admission");
      Path terminal=Files.createSymbolicLink(valid.resolve("terminal-link"),outside);EnvironmentBrowserData.erase(terminal.toFile());
      require(!Files.exists(terminal,java.nio.file.LinkOption.NOFOLLOW_LINKS)&&unchanged(other),"Terminal links are unlinked and their target bytes survive");
      Path dangling=Files.createSymbolicLink(valid.resolve("dangling-link"),temporary.resolve("nonexistent"));EnvironmentBrowserData.erase(dangling.toFile());
      require(!Files.exists(dangling,java.nio.file.LinkOption.NOFOLLOW_LINKS)&&unchanged(other),"Dangling terminal links are safely removed");
      System.out.println("{\"status\":\"passed\",\"passed\":"+checks+",\"actualAndroidExecution\":false,\"actualProductionRootPolicyExecution\":true}");
    }finally{EnvironmentBrowserData.erase(temporary.toFile());}
  }
}
