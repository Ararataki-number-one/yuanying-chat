package local.pocketchat;

import java.nio.file.Files;
import java.nio.file.Path;

/** Execute the exact integration adapter for the independent host controls. */
public final class ContinuityDriverAdapterHost {
  public static void main(String[] args)throws Exception{
    Files.writeString(Path.of(args[2]),ContinuityDriverAdapter.adapt(Files.readString(Path.of(args[0])),args[1]));
  }
}
