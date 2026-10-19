package local.pocketchat;

/** Reversible presentation palette. Images and website pixels are never filtered. */
final class AppearanceColors {
  static final int[][] PAIRS={
    // Existing semantic color, light presentation, dark presentation. Keeping
    // the original keys also updates legacy screens and already open views.
    {0xfff4f7fb,0xfff2f2f7,0xff0c0c0f},{0xffffffff,0xffffffff,0xff1c1c1e},{0xfff8fafc,0xfff7f7f9,0xff242427},
    {0xffe0e7f0,0xffe0e0e5,0xff3a3a3e},{0xff172033,0xff1b1b1f,0xfff4f4f6},{0xff64748b,0xff686873,0xffaaaab4},
    {0xff2468f2,0xff0067d8,0xff82b3ff},{0xff16845b,0xff1c7c48,0xff70cf97},{0xffc93747,0xffc52a3a,0xffff8c96},
    {0xfff9fbfe,0xfffafafc,0xff111114},{0xffedf4ff,0xffeaf2ff,0xff1c2d49},{0xffa96c0a,0xff986000,0xffedc074},
    {0xff1e293b,0xff1b1b1f,0xfff4f4f6},{0xfff4f6fa,0xfff2f2f7,0xff0c0c0f},{0xffeaf1ff,0xffeaf2ff,0xff1c2d49},
    {0xfff0f2f6,0xffeeeef2,0xff29292d},{0xfff0f5ff,0xffedf3ff,0xff20304b},{0xfff5f9ff,0xfff2f6ff,0xff202c40},
    {0xfff7faff,0xfff6f8ff,0xff26344a},{0xffcfe0ff,0xffd4e2fa,0xff3e5272},{0xffd4e3ff,0xffd9e5fa,0xff435674},
    {0xff8fb4ff,0xff8fb4ff,0xff638bd1},{0xfffff1f2,0xfffff0f1,0xff38262c},{0xffedf5ff,0xfff1f5fd,0xff25334a},
    {0xfffecdd3,0xfffecdd3,0xff69404b},{0xff1268ff,0xff0064d2,0xff075fcb},{0xff2563eb,0xff0067d8,0xff82b3ff}
  };
  static String mode(String value){return "light".equals(value)||"dark".equals(value)?value:"system";}
  static boolean ownsUi(String app,String process){
    if(app==null||process==null)return false;
    if(process.equals(app)||process.equals(app+":engine_restart"))return true;
    for(int i=1;i<8;i++)if(process.equals(app+":profile"+i))return true;
    return false;
  }
  static boolean dark(String mode,boolean systemDark){return "dark".equals(mode)||!"light".equals(mode)&&systemDark;}
  static int color(int value,boolean dark){for(int[] pair:PAIRS)for(int candidate:pair)if(value==candidate)return pair[dark?2:1];return value;}
  static int text(int value,boolean dark){
    // White is intentional on primary buttons and the brand screen.
    if(value==0xffffffff)return value;
    if((value&0x00ffffff)==0&&(value>>>24)>0)return (color(0xff172033,dark)&0x00ffffff)|(value&0xff000000);
    if((value>>>24)>0&&(value>>>24)<255)for(int[] pair:PAIRS){
      if(pair[0]==0xffffffff)continue;
      int rgb=value&0x00ffffff;
      for(int candidate:pair)if(rgb==(candidate&0x00ffffff))return (value&0xff000000)|(pair[dark?2:1]&0x00ffffff);
    }
    return color(value,dark);
  }
}
