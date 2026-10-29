package local.pocketchat.inputdriver;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Host-only wrapper around the unchanged pre-emission window parser. */
public final class NativePreEmitReadinessCli {
  private static final String COMPONENT=
      "local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity";

  private static int uid(String value) {
    if (!value.matches("[1-9][0-9]{4}")) throw new IllegalArgumentException();
    return Integer.parseInt(value);
  }

  public static void main(String[] args) {
    try {
      if (args.length != 4 || !COMPONENT.equals(args[2])
          || !args[3].matches("[0-9a-f]+")) throw new IllegalArgumentException();
      int targetUid=uid(args[0]), systemUiUid=uid(args[1]);
      ByteArrayOutputStream output=new ByteArrayOutputStream();
      byte[] bytes=new byte[16384];
      int count;
      while ((count=System.in.read(bytes)) != -1) {
        if (count > NativePreEmitReadiness.MAX_BYTES-output.size())
          throw new IllegalArgumentException();
        output.write(bytes,0,count);
      }
      String raw=StandardCharsets.UTF_8.newDecoder()
          .onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT)
          .decode(ByteBuffer.wrap(output.toByteArray())).toString();
      NativePreEmitReadiness.State state=
          NativePreEmitReadiness.parse(raw,targetUid,systemUiUid);
      Matcher focus=Pattern.compile("^[ \\t]*mCurrentFocus=([^\\r\\n]*)$",
          Pattern.MULTILINE).matcher(raw);
      String expected="Window{"+args[3]+" u0 "+COMPONENT+"}";
      if (!focus.find() || !expected.equals(focus.group(1).trim()) || focus.find())
        throw new IllegalArgumentException();
      System.out.println(state.name());
    } catch (Exception failure) {
      System.err.println("invalid-observation");
      System.exit(2);
    }
  }

  private NativePreEmitReadinessCli() {}
}
