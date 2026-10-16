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
    for(boolean system:new boolean[]{false,true}){
      check(AppearanceColors.dark("system",system)==system,"system events control automatic mode");
      check(AppearanceColors.dark("dark",system),"manual dark persists");check(!AppearanceColors.dark("light",system),"manual light persists");
    }
    Set<Integer> unique=new HashSet<>();
    for(int[] pair:AppearanceColors.PAIRS){
      check(unique.add(pair[0])&&unique.add(pair[1]),"palette colors must not alias roles");
      check(AppearanceColors.color(pair[0],true)==pair[1],"light to dark");
      check(AppearanceColors.color(pair[1],false)==pair[0],"dark to light without accumulating changes");
      check(AppearanceColors.color(pair[1],true)==pair[1],"idempotent native recolor");
    }
    for(int background:new int[]{0xff15181e,0xff20242c,0xff181b21})for(int text:new int[]{0xffe3e7ef,0xff9ea8b8,0xff8aafff,0xff65c99b,0xffff8693})check(contrast(background,text)>=4.5,"night text retains readable contrast");
    check(contrast(0xff2468f2,0xffffffff)>=4.5,"primary blue button stays readable");
    check(AppearanceColors.text(0xffffffff,true)==0xffffffff,"primary/brand white foreground is retained");
    check(AppearanceColors.color(0x00000000,true)==0x00000000,"transparency preserved");
    System.out.println("Appearance palette: "+checks+" checks passed");
  }
}
