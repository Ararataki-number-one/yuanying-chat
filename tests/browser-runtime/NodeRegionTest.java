package local.pocketchat;
public final class NodeRegionTest {
  static int checks;static void expect(String input,String region){if(!NodeRegion.identify(input).equals(region))throw new AssertionError(input+" → "+NodeRegion.identify(input));checks++;}
  public static void main(String[] args){expect("大阪 03","日本");expect("🇯🇵 Premium 03","日本");expect("HK 01","中国香港");expect("中国香港 02","中国香港");expect("Singapore 07","新加坡");expect("United States 02","美国");expect("JP 01","日本");expect("status premium"," ".trim());expect("unusual"," ".trim());expect("日本 → 美国","");expect("🇯🇵 🇺🇸 relay","");expect("未命名 03","");expect("韩国首尔","韩国");expect("英国 London","英国");if(!NodeRegion.country("ZZ").isEmpty())throw new AssertionError("Unknown ISO code");checks++;System.out.println("{\"passed\":"+checks+",\"total\":"+checks+",\"scope\":\"Real name parsing; labels are not exit IP verification\"}");}
}
