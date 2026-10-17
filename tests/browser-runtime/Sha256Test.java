package local.pocketchat;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.*;

/** Known vectors and persisted v2.0.7 encoding compatibility, including concurrent callers. */
public final class Sha256Test {
  private static int checks;
  private static void equal(String expected,String actual) {
    if(!expected.equals(actual))throw new AssertionError("Digest/encoding changed");
    checks++;
  }
  private static String legacyHex(byte[] bytes) {
    StringBuilder out=new StringBuilder();
    for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));
    return out.toString();
  }
  public static void main(String[] args)throws Exception {
    equal("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",Sha256.hash(""));
    equal("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",Sha256.hash("abc"));
    byte[] allBytes=new byte[256];for(int i=0;i<allBytes.length;i++)allBytes[i]=(byte)i;
    equal(legacyHex(allBytes),Sha256.hex(allBytes));
    equal("",Sha256.hex(new byte[0]));
    Random random=new Random(207);
    for(int size:new int[]{0,1,31,32,63,64,65,1024,65536,1048576}) {
      byte[] bytes=new byte[size];random.nextBytes(bytes);
      equal(legacyHex(MessageDigest.getInstance("SHA-256").digest(bytes)),Sha256.hash(bytes));
    }
    for(String value:new String[]{"默认环境","入口|日本東京","x\0y","emoji 🌙","invalid \ud800"})
      equal(legacyHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))),Sha256.hash(value));
    ExecutorService pool=Executors.newFixedThreadPool(8);
    try {
      java.util.List<Future<String>> results=new java.util.ArrayList<>();
      for(int i=0;i<256;i++){final String text="environment-"+i;results.add(pool.submit(()->Sha256.hash(text)));}
      for(int i=0;i<results.size();i++)equal(legacyHex(MessageDigest.getInstance("SHA-256").digest(("environment-"+i).getBytes(StandardCharsets.UTF_8))),results.get(i).get());
    }finally{pool.shutdownNow();}
    System.out.println("Sha256Test: "+checks+" checks passed (JVM only)");
  }
}
