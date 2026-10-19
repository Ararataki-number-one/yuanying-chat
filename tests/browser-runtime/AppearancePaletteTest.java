package local.pocketchat;

/** Contrast and reversible theme transitions, independent of Android rendering. */
public final class AppearancePaletteTest {
  static int checks;
  static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
  static double linear(int channel){double v=channel/255.0;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4);}
  static double luminance(int color){return .2126*linear(color>>16&255)+.7152*linear(color>>8&255)+.0722*linear(color&255);}
  static double contrast(int a,int b){double x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
  public static void main(String[] args){
    int[] semantic={0xfff4f7fb,0xffffffff,0xfff8fafc,0xffe0e7f0,0xff172033,0xff64748b,0xff2468f2,0xff16845b,0xffc93747,0xfff9fbfe,0xffedf4ff,0xfff0f2f6,0xfff0f5ff,0xffedf5ff,0xff1268ff};
    for(int key:semantic)for(boolean dark:new boolean[]{false,true}){
      int color=AppearanceColors.color(key,dark);
      check(AppearanceColors.color(color,dark)==color,"Repeated theme changes must not change a semantic role");
      check(AppearanceColors.color(AppearanceColors.color(color,!dark),dark)==color,"Theme transition must be reversible");
    }
    for(boolean dark:new boolean[]{false,true}){
      for(int paper:new int[]{0xffffffff,0xfff4f7fb,0xfff9fbfe,0xfff8fafc})for(int ink:new int[]{0xff172033,0xff64748b,0xff2468f2,0xff16845b,0xffc93747})
        check(contrast(AppearanceColors.color(ink,dark),AppearanceColors.color(paper,dark))>=4.5,"Native text needs AA contrast");
      check(contrast(0xffffffff,AppearanceColors.color(0xff1268ff,dark))>=4.5,"Filled actions need legible white text");
      check(AppearanceColors.text(0xffffffff,dark)==0xffffffff,"Filled-action labels retain white text");
    }
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+"}");
  }
}
