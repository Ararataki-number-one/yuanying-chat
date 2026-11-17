package local.pocketchat;

/** Exercises the unchanged production geometry without Android view substitutes. */
public final class BrowserHeaderLayoutHost {
  private static int checks,cases;
  private static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
  private static int px(int dp,int density){return Math.round(dp*density/160f);}

  public static void main(String[] args){
    for(int density:new int[]{160,213,320,420,480,640})
      for(int widthDp:new int[]{240,280,300,320,360,412,720})
        for(int capsuleDp:new int[]{112,160,192})
          for(int textHeightDp:new int[]{20,40,64}){
            int minimum=px(48,density),compact=px(28,density),width=px(widthDp-32,density);
            int capsuleWidth=Math.min(px(capsuleDp,density),width),topHeight=px(48,density);
            int visualMinimum=BrowserHeaderLayout.networkMinimumHeight(width,capsuleWidth,minimum,compact);
            int contentHeight=px(textHeightDp+2,density),rowHeight=Math.max(visualMinimum,contentHeight);
            int left=(width-capsuleWidth)/2;
            int[] capsule={left,0,left+capsuleWidth,topHeight};
            int[] network=BrowserHeaderLayout.networkTouch(0,topHeight,width,topHeight+rowHeight,0,minimum);
            check(network[3]==topHeight+rowHeight,"Touch region must end with the network strip");
            check(network[1]<=topHeight&&network[1]>=0,"Touch region must remain within the header");
            check(network[3]-network[1]>=minimum,"Network action must retain 48 dp vertically");
            if(visualMinimum==compact){
              check(left>=minimum&&width-(left+capsuleWidth)>=minimum,"Compact strip needs full-sized side targets");
              check(BrowserHeaderLayout.targetAt(capsule,network,left/2,network[1])==1,"Left extension must open network details");
              check(BrowserHeaderLayout.targetAt(capsule,network,left+capsuleWidth+(width-left-capsuleWidth)/2,network[1])==1,"Right extension must open network details");
            }else check(visualMinimum==minimum,"Narrow geometry must keep the full network row");
            for(int y=0;y<network[3];y+=Math.max(1,minimum/6))
              for(int x=0;x<width;x+=Math.max(1,minimum/6)){
                int target=BrowserHeaderLayout.targetAt(capsule,network,x,y);
                if(x>=left&&x<left+capsuleWidth&&y<topHeight)check(target==0,"Network cannot steal any capsule pixel");
                if(y>=topHeight)check(target==1,"All visible network pixels remain clickable");
              }
            check(BrowserHeaderLayout.targetAt(capsule,network,width/2,network[3])==-1,"First webpage pixel must not belong to header");
            check(BrowserHeaderLayout.targetAt(capsule,network,-1,topHeight)==-1,"Outside left edge must not receive a header action");
            check(BrowserHeaderLayout.targetAt(capsule,network,width,topHeight)==-1,"Outside right edge must not receive a header action");
            cases++;
          }
    check(BrowserHeaderLayout.networkMinimumHeight(328,192,48,28)==28,"Normal phone shrinks to a 28 dp network strip");
    check(48+BrowserHeaderLayout.networkMinimumHeight(328,192,48,28)==76,"Normal two-row header is 76 dp before its divider");
    check(BrowserHeaderLayout.networkMinimumHeight(328,0,48,28)==48,"Unmeasured environment must fail back to a full target");
    System.out.println("{\"status\":\"passed\",\"cases\":"+cases+",\"checks\":"+checks+",\"actualAndroidExecution\":false}");
  }
}
