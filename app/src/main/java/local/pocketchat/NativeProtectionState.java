package local.pocketchat;

/** Correlated native-setting confirmation only; it does not attest every Web API. */
final class NativeProtectionState {
  static final int MAX_ATTEMPTS=3;
  static final long WAIT_MS=8000,RETRY_MS=500;
  private int level=-1,attempt;
  private long generation,token;
  private boolean inFlight,received,acknowledged,fingerprinting;
  private String state="pending",reason="not-requested";

  void begin(int requested){
    level=requested;generation++;attempt=0;inFlight=received=acknowledged=fingerprinting=false;
    state="pending";reason="awaiting-setting";
    if(requested<0||requested>2)fail("invalid-level");
  }
  long request(){
    if(level<0||level>2||attempt>=MAX_ATTEMPTS||inFlight)throw new IllegalStateException("No protection attempt available");
    attempt++;token++;inFlight=true;received=acknowledged=fingerprinting=false;
    state="pending";reason="awaiting-setting";return token;
  }
  boolean matches(long replyToken,long replyGeneration,int replyLevel){
    return inFlight&&token==replyToken&&generation==replyGeneration&&level==replyLevel;
  }
  boolean receive(long replyToken,long replyGeneration,int replyLevel,boolean ack,boolean observed,String failure){
    if(!matches(replyToken,replyGeneration,replyLevel))return false;
    inFlight=false;received=true;acknowledged=ack;fingerprinting=observed;
    boolean exact=ack&&observed==(level>=2);
    state=exact?"confirmed":"failed";reason=exact?"":safeReason(failure,"setting-mismatch");return true;
  }
  boolean timeout(long replyToken,long replyGeneration,int replyLevel){
    if(!matches(replyToken,replyGeneration,replyLevel))return false;
    fail("setting-timeout");return true;
  }
  boolean changed(long replyToken,long replyGeneration,int replyLevel){
    if(!confirmed()||token!=replyToken||generation!=replyGeneration||level!=replyLevel)return false;
    fail("setting-changed");return true;
  }
  void disconnected(){generation++;token++;received=false;fail("bridge-disconnected");}
  void closed(){generation++;token++;level=-1;attempt=0;received=false;fail("browser-closed");}
  void fail(String why){inFlight=false;acknowledged=false;fingerprinting=false;state="failed";reason=safeReason(why,"setting-failed");}
  boolean canRetry(){return level==2&&"failed".equals(state)&&attempt<MAX_ATTEMPTS;}
  void awaitingRetry(){if(!canRetry())throw new IllegalStateException("Protection retry unavailable");state="pending";reason="retrying-setting";}
  boolean confirmed(){return "confirmed".equals(state)&&acknowledged&&fingerprinting==(level>=2);}
  boolean allows(int desired){return desired>=0&&desired<2||level==desired&&confirmed()&&fingerprinting;}
  int level(){return level;}int attempt(){return attempt;}
  long generation(){return generation;}long token(){return token;}
  String state(){return state;}String reason(){return reason;}
  boolean received(){return received;}boolean fingerprinting(){return fingerprinting;}
  static String safeReason(String value,String fallback){
    if(value!=null&&value.matches("[a-z][a-z0-9-]{0,63}"))return value;
    return fallback;
  }
}
