package local.pocketchat;
import java.util.*;
public final class AppearanceColorsTest {
  static int checks;
  static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
  static double luminance(int color){double sum=0;double[] weights={.2126,.7152,.0722};for(int i=0;i<3;i++){double c=((color>>(16-i*8))&255)/255d;sum+=weights[i]*(c<=.04045?c/12.92:Math.pow((c+.055)/1.055,2.4));}return sum;}
  static double contrast(int a,int b){double x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
  public static void main(String[] args){
    check(AppearanceColors.mode(null).equals("system"),"old/missing preference follows system");
    check(AppearanceColors.mode("unknown").equals("system"),"unknown preference follows system");
    check(AppearanceColors.ownsUi("app","app"),"main UI initializes appearance");
    for(int i=1;i<8;i++)check(AppearanceColors.ownsUi("app","app:profile"+i),"environment UI initializes appearance");
    check(AppearanceColors.ownsUi("app","app:engine_restart"),"restart UI is themed");
    for(String process:new String[]{null,"app:network","app:isolatedTab_disable_art_image_0:org.mozilla.gecko.process.GeckoChildProcessServices$isolatedTab0:environment0","app:gpu","other","app:profile8"})check(!AppearanceColors.ownsUi("app",process),"non-UI children never access theme storage");
    for(boolean system:new boolean[]{false,true}){
      check(AppearanceColors.dark("system",system)==system,"system events control automatic mode");
      check(AppearanceColors.dark("dark",system),"manual dark persists");check(!AppearanceColors.dark("light",system),"manual light persists");
    }
    Map<Integer,String> roles=new HashMap<>();
    for(int[] pair:AppearanceColors.PAIRS){
      for(int value:pair){String role=pair[1]+":"+pair[2],old=roles.putIfAbsent(value,role);check(old==null||old.equals(role),"aliases cannot change semantic roles");}
      check(AppearanceColors.color(pair[0],false)==pair[1],"legacy semantic key resolves to the current light palette");
      check(AppearanceColors.color(pair[1],true)==pair[2],"light to dark");
      check(AppearanceColors.color(pair[2],false)==pair[1],"dark to light without accumulating changes");
      check(AppearanceColors.color(pair[2],true)==pair[2],"idempotent native recolor");
    }
    for(int background:new int[]{0xff0c0c0f,0xff1c1c1e,0xff111114})for(int text:new int[]{0xfff4f4f6,0xffaaaab4,0xff82b3ff,0xff70cf97,0xffff8c96})check(contrast(background,text)>=4.5,"night text retains readable contrast");
    check(contrast(AppearanceColors.color(0xff1268ff,false),0xffffffff)>=4.5,"primary blue button stays readable");
    check(AppearanceColors.text(0xffffffff,true)==0xffffffff,"primary/brand white foreground is retained");
    check(AppearanceColors.color(0x00000000,true)==0x00000000,"transparency preserved");
    check(AppearanceColors.text(AppearanceColors.text(0x61172033,true),false)==0x611b1b1f,"disabled text keeps alpha across night/day roundtrip");
    check(AppearanceColors.text(AppearanceColors.text(0x61000000,true),false)==0x611b1b1f,"native translucent black returns to readable day foreground");
    System.out.println("Appearance palette: "+checks+" checks passed");
  }
}
