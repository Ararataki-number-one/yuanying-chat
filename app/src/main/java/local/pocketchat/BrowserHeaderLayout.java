package local.pocketchat;

/** Pixel geometry for a compact network strip with a full-sized side hit area. */
final class BrowserHeaderLayout {
  private BrowserHeaderLayout() {}

  static int networkMinimumHeight(int width,int environmentWidth,int minimum,int compact){
    // Each side of the centred environment button must retain a complete
    // minimum-sized target. Narrow windows fall back to a separate full row.
    return environmentWidth>0&&width>=Math.max(minimum,environmentWidth)+2*minimum?compact:minimum;
  }

  static int[] networkTouch(int left,int top,int right,int bottom,int headerTop,int minimum){
    // Borrow blank space above the strip; never borrow pixels from the webpage.
    return new int[]{left,Math.max(headerTop,Math.min(top,bottom-minimum)),right,bottom};
  }

  static boolean contains(int[] bounds,int x,int y){
    return bounds!=null&&bounds.length==4&&x>=bounds[0]&&y>=bounds[1]&&x<bounds[2]&&y<bounds[3];
  }

  static int targetAt(int[] environment,int[] network,int x,int y){
    // The capsule owns the shared middle area, including its invisible padding.
    return contains(environment,x,y)?0:contains(network,x,y)?1:-1;
  }
}
