package local.pocketchat;

/** Reversible presentation palette. Images and website pixels are never filtered. */
final class AppearanceColors {
  static final int[][] PAIRS={
    {0xfff4f7fb,0xff15181e},{0xffffffff,0xff20242c},{0xfff8fafc,0xff191d24},
    {0xffe0e7f0,0xff363d49},{0xff172033,0xffe3e7ef},{0xff64748b,0xff9ea8b8},
    {0xff2468f2,0xff8aafff},{0xff16845b,0xff65c99b},{0xffc93747,0xffff8693},
    {0xfff9fbfe,0xff181b21},{0xffedf4ff,0xff25344e},{0xffa96c0a,0xffe5b765},
    {0xff1e293b,0xffdce2eb},{0xfff4f6fa,0xff16191f},{0xffeaf1ff,0xff263650},
    {0xfff0f2f6,0xff282d36},{0xfff0f5ff,0xff26364d},{0xfff5f9ff,0xff202e43},
    {0xfff7faff,0xff26374e},{0xffcfe0ff,0xff3c5274},{0xffd4e3ff,0xff405474},
    {0xff8fb4ff,0xff638bd1},{0xfffff1f2,0xff38262c},{0xffedf5ff,0xff25334a},
    {0xfffecdd3,0xff69404b},{0xff1268ff,0xff8db1ff},{0xff2563eb,0xff8da9ff}
  };
  static String mode(String value){return "light".equals(value)||"dark".equals(value)?value:"system";}
  static boolean dark(String mode,boolean systemDark){return "dark".equals(mode)||!"light".equals(mode)&&systemDark;}
  static int color(int value,boolean dark){for(int[] pair:PAIRS)if(value==pair[0]||value==pair[1])return pair[dark?1:0];return value;}
  static int text(int value,boolean dark){
    // White is intentional on primary buttons and the brand screen.
    if(value==0xffffffff)return value;
    if((value&0x00ffffff)==0&&(value>>>24)>0)return (color(0xff172033,dark)&0x00ffffff)|(value&0xff000000);
    if((value>>>24)>0&&(value>>>24)<255)for(int[] pair:PAIRS){
      if(pair[0]==0xffffffff)continue;
      int rgb=value&0x00ffffff;
      if(rgb==(pair[0]&0x00ffffff)||rgb==(pair[1]&0x00ffffff))return (value&0xff000000)|(pair[dark?1:0]&0x00ffffff);
    }
    return color(value,dark);
  }
}
