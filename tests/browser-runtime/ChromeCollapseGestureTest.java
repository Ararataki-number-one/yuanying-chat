package local.pocketchat;

/** Gesture intent only: no claim about actual Android dispatch or webpage scrolling. */
public final class ChromeCollapseGestureTest {
  static int checks;
  static void check(boolean value,String name){if(!value)throw new AssertionError(name);checks++;}
  static ChromeCollapseGesture gesture(){return new ChromeCollapseGesture(40,8,500);}
  static int swipe(ChromeCollapseGesture g,float x,float y,float endX,float endY){
    g.begin(x,y,100,true);g.move(endX,endY,1,220);return g.finish(endX,endY,250);
  }
  public static void main(String[] args){
    ChromeCollapseGesture g=gesture();
    check(swipe(g,100,300,101,200)==ChromeCollapseGesture.HIDE,"Reading upward hides the native header after finger release");
    check(swipe(g,100,200,99,300)==ChromeCollapseGesture.SHOW,"A deliberate downward swipe can recover hidden controls");
    check(swipe(g,100,200,102,201)==ChromeCollapseGesture.NONE,"Tapping the real webpage does not change native controls");
    check(swipe(g,100,200,101,172)==ChromeCollapseGesture.NONE,"Small caret and finger adjustments do not hide controls");
    check(swipe(g,100,200,220,180)==ChromeCollapseGesture.NONE,"Horizontal code and table scrolling keeps the header unchanged");
    g.begin(100,300,100,true);g.move(170,295,1,180);g.move(170,170,1,240);
    check(g.finish(170,170,260)==ChromeCollapseGesture.NONE,"A horizontal gesture cannot turn into a header action midway");
    g.begin(100,300,100,true);g.move(101,200,2,200);g.move(101,120,1,250);
    check(g.finish(101,120,280)==ChromeCollapseGesture.NONE,"A pinch remains excluded after one finger is lifted");
    g.begin(100,300,100,true);g.move(100,200,1,200);g.cancel();
    check(g.finish(100,200,250)==ChromeCollapseGesture.NONE,"Android cancellation cannot complete a pending header action");
    g.begin(100,300,100,false);g.move(100,200,1,200);
    check(g.finish(100,200,250)==ChromeCollapseGesture.NONE,"Disabled contexts such as keyboard or accessibility do not collapse");
    g.begin(100,300,100,true);g.move(101,301,1,650);g.move(100,180,1,750);
    check(g.finish(100,180,780)==ChromeCollapseGesture.NONE,"Long press followed by selection dragging keeps the header still");
    g.begin(100,300,100,true);g.move(100,260,1,200);g.move(100,180,1,950);
    check(g.finish(100,180,1000)==ChromeCollapseGesture.HIDE,"A slow continuous reading scroll remains a reading gesture");
    check(g.finish(100,100,1100)==ChromeCollapseGesture.NONE,"A completed gesture cannot schedule a second layout change");
    g.begin(100,300,100,true);g.move(100,200,1,200);g.begin(100,300,250,true);
    check(g.finish(100,300,300)==ChromeCollapseGesture.NONE,"A fresh touch abandons any older gesture intent");
    g.begin(100,300,100,true);g.move(100,200,1,200);g.cancel();
    check(swipe(g,100,200,100,300)==ChromeCollapseGesture.SHOW,"Controls remain recoverable after an interrupted earlier gesture");
    check(gesture().finish(100,100,200)==ChromeCollapseGesture.NONE,"An orphan finger-up event cannot hide controls");
    check(swipe(g,100,300,100,200)==ChromeCollapseGesture.HIDE&&swipe(g,100,200,100,300)==ChromeCollapseGesture.SHOW,"Consecutive opposing reading gestures each have an independent intent");
    System.out.println("ChromeCollapseGestureTest: "+checks+" checks passed (JVM intent policy only)");
  }
}
