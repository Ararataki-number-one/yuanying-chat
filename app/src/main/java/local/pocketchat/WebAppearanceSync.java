package local.pocketchat;

import java.util.*;
import java.util.regex.Pattern;
import org.json.*;

/** A bounded, document-bound acknowledgement flow. All calls belong to the UI thread. */
final class WebAppearanceSync {
  interface Sender { void send(Object port, JSONObject command); }
  static final int PROTOCOL=1, MAX_ATTEMPTS=3;
  static final long RETRY_DELAY_MS=1500;
  private static final Set<String> STORAGE=new HashSet<>(Arrays.asList("written","unchanged","unavailable","failed"));
  private static final Set<String> COLORS=new HashSet<>(Arrays.asList("verified","mismatch","unavailable"));
  private static final Set<String> REGIONS=new HashSet<>(Arrays.asList("root","body","main","composer"));
  private static final Set<String> REASONS=new HashSet<>(Arrays.asList("","root-unavailable","attribute-write-failed",
    "storage-unavailable","storage-write-failed","storage-preference-mismatch","chat-region-unavailable","color-unavailable","color-mismatch",
    "page-hidden","script-unavailable","script-error"));
  private static final Pattern NUMBER=Pattern.compile("[+-]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?%?");
  private static final class Entry {
    final Object port;
    final String document;
    boolean dark,received,applied;
    int version,attempt;
    String status="pending",storage="unavailable",colorStatus="unavailable",reason="waiting";
    JSONArray samples=new JSONArray();
    Runnable timeout;
    long timerGeneration;
    Entry(Object port,String document){this.port=port;this.document=document;}
  }
  private static final class Observation {
    boolean applied,colorsMatch;
    String storage,colorStatus,reason;
    JSONArray samples;
  }
  private final BrowserBridgeRequests.Timer timer;
  private final Sender sender;
  private final Map<Object,Entry> entries=new IdentityHashMap<>();
  private int sequence;

  WebAppearanceSync(BrowserBridgeRequests.Timer timer,Sender sender){this.timer=Objects.requireNonNull(timer);this.sender=Objects.requireNonNull(sender);}

  boolean connect(Object port,String document,boolean dark){
    if(port==null||document==null||!document.matches("[a-zA-Z0-9-]{16,80}"))return false;
    Entry existing=entries.get(port);
    if(existing!=null&&existing.document.equals(document)){
      if(existing.dark!=dark)request(port,dark);
      return true;
    }
    disconnect(port);
    entries.put(port,new Entry(port,document));
    return request(port,dark);
  }
  boolean request(Object port,boolean dark){
    Entry entry=entries.get(port);if(entry==null)return false;
    cancel(entry);entry.dark=dark;entry.attempt=0;
    send(entry);return true;
  }
  void disconnect(Object port){Entry entry=entries.remove(port);if(entry!=null)cancel(entry);}
  void clear(){for(Entry entry:entries.values())cancel(entry);entries.clear();}

  private void send(Entry entry){
    cancel(entry);
    if(sequence==Integer.MAX_VALUE){entry.status="failed";entry.reason="version-exhausted";return;}
    entry.version=++sequence;entry.attempt++;
    entry.status="pending";entry.received=false;entry.applied=false;
    entry.storage="unavailable";entry.colorStatus="unavailable";entry.reason="waiting";entry.samples=new JSONArray();
    arm(entry);
    final int sentVersion=entry.version;
    try{sender.send(entry.port,object("kind","appearance","protocol",PROTOCOL,"documentId",entry.document,"version",entry.version,"dark",entry.dark));}
    catch(RuntimeException unavailable){if(entries.get(entry.port)==entry&&entry.version==sentVersion&&"pending".equals(entry.status))entry.reason="send-failed";}
  }
  private void arm(Entry entry){
    final int version=entry.version;
    final long ticket=++entry.timerGeneration;
    Runnable timeout=()->{
      if(entries.get(entry.port)!=entry||entry.version!=version||entry.timerGeneration!=ticket||!"pending".equals(entry.status))return;
      entry.timeout=null;
      if(entry.attempt<MAX_ATTEMPTS)send(entry);
      else{
        entry.status=partial(entry)?"partial":"failed";
        if("waiting".equals(entry.reason))entry.reason="receipt-timeout";
      }
    };
    entry.timeout=timeout;timer.schedule(timeout,RETRY_DELAY_MS);
  }
  private void cancel(Entry entry){entry.timerGeneration++;if(entry.timeout!=null){timer.cancel(entry.timeout);entry.timeout=null;}}

  /** False means malformed/stale/unbound; such a receipt cannot change any state. */
  boolean receive(Object port,JSONObject receipt){
    Entry entry=entries.get(port);
    if(entry==null||receipt==null||!"appearanceReceipt".equals(receipt.opt("kind"))
      ||!integer(receipt.opt("protocol"),PROTOCOL)||!integer(receipt.opt("version"),entry.version)
      ||!entry.document.equals(receipt.opt("documentId"))||!(receipt.opt("dark") instanceof Boolean)
      ||((Boolean)receipt.opt("dark"))!=entry.dark)return false;
    Object rawStage=receipt.opt("stage"),rawReason=receipt.opt("reason");
    if(!(rawStage instanceof String)||rawReason!=null&&(!(rawReason instanceof String)||!REASONS.contains(rawReason)))return false;
    String stage=(String)rawStage;
    if("received".equals(stage)){
      if(!"pending".equals(entry.status))return false;
      entry.received=true;return true;
    }
    if(!"applied".equals(stage)&&!"observed".equals(stage))return false;
    if(!(receipt.opt("attributesApplied") instanceof Boolean)||!(receipt.opt("storage") instanceof String)||!STORAGE.contains(receipt.opt("storage")))return false;
    if("applied".equals(stage)){
      if(!"pending".equals(entry.status))return false;
      entry.received=true;entry.applied=(Boolean)receipt.opt("attributesApplied");entry.storage=(String)receipt.opt("storage");return true;
    }
    // A confirmed current document may later report drift. It can consume only
    // this request's remaining attempts; it cannot start another three attempts.
    if(!"pending".equals(entry.status)&&!"confirmed".equals(entry.status))return false;
    Observation observed=observation(receipt,entry.dark);if(observed==null)return false;
    boolean wasConfirmed="confirmed".equals(entry.status);
    entry.received=true;entry.applied=observed.applied;entry.storage=observed.storage;
    entry.colorStatus=observed.colorStatus;entry.samples=observed.samples;entry.reason=observed.reason;
    if(observed.applied&&observed.colorsMatch&&persisted(observed.storage)){
      cancel(entry);entry.status="confirmed";entry.reason="";
    }else{
      if(entry.attempt>=MAX_ATTEMPTS){cancel(entry);entry.status=partial(entry)?"partial":"failed";}
      else{entry.status="pending";if(wasConfirmed)arm(entry);}
    }
    return true;
  }
  private static boolean persisted(String storage){return "written".equals(storage)||"unchanged".equals(storage);}
  private static boolean partial(Entry entry){return entry.applied&&"verified".equals(entry.colorStatus)&&!persisted(entry.storage);}

  private static Observation observation(JSONObject receipt,boolean dark){
    Object colors=receipt.opt("colorStatus");JSONArray input=receipt.optJSONArray("samples");
    if(!(colors instanceof String)||!COLORS.contains(colors)||input==null||input.length()>4
      ||input.length()==0&&!"unavailable".equals(colors))return null;
    Observation result=new Observation();result.applied=(Boolean)receipt.opt("attributesApplied");
    result.storage=(String)receipt.opt("storage");result.colorStatus=(String)colors;result.samples=new JSONArray();
    Set<String> seen=new HashSet<>();boolean chat=false,matching=true,known=true;
    for(int i=0;i<input.length();i++){
      JSONObject sample=input.optJSONObject(i);if(sample==null)return null;
      Object region=sample.opt("region"),background=sample.opt("background"),foreground=sample.opt("foreground"),visible=sample.opt("visible");
      if(!(region instanceof String)||!REGIONS.contains(region)||!seen.add((String)region)
        ||!(background instanceof String)||!(foreground instanceof String)||!(visible instanceof Boolean))return null;
      String cleanBackground=color((String)background),cleanForeground=color((String)foreground);
      if(cleanBackground==null||cleanForeground==null)return null;
      Object bg=sample.opt("backgroundLuminance"),fg=sample.opt("foregroundLuminance");
      // Unknown colours are useful diagnostics, but must be explicitly null.
      if(!luminance(bg)&&bg!=JSONObject.NULL||!luminance(fg)&&fg!=JSONObject.NULL)return null;
      if(!(Boolean)visible&&("main".equals(region)||"composer".equals(region))){matching=false;known=false;}
      if((Boolean)visible&&("main".equals(region)||"composer".equals(region))){
        chat=true;if(!luminance(bg)||!luminance(fg)||cleanBackground.isEmpty()||cleanForeground.isEmpty()){matching=false;known=false;}
        else{double value=((Number)bg).doubleValue();if(dark?value>=.35:value<=.5)matching=false;}
      }
      result.samples.put(object("region",region,"background",cleanBackground,"foreground",cleanForeground,"backgroundLuminance",measurement(bg),"foregroundLuminance",measurement(fg),"visible",visible));
    }
    result.colorsMatch=chat&&matching&&"verified".equals(colors);
    // Do not let a page's claimed verdict outrank native structural/numeric checks.
    if(!result.colorsMatch&&"verified".equals(result.colorStatus))result.colorStatus=chat&&known?"mismatch":"unavailable";
    String reported=receipt.optString("reason","");
    if(!result.applied)result.reason=Arrays.asList("root-unavailable","attribute-write-failed","page-hidden","script-unavailable","script-error").contains(reported)?reported:"attributes-not-applied";
    else if(!result.colorsMatch)result.reason=!chat?(Arrays.asList("root-unavailable","page-hidden","script-unavailable","script-error").contains(reported)?reported:"chat-region-unavailable"):"unavailable".equals(result.colorStatus)?"color-unavailable":"color-mismatch";
    else if(!persisted(result.storage))result.reason="storage-preference-mismatch".equals(reported)&&"failed".equals(result.storage)?reported:"failed".equals(result.storage)?"storage-write-failed":"storage-unavailable";
    else result.reason="";
    return result;
  }
  /** Parse a small computed-colour grammar, then discard its original spelling. */
  private static String color(String value){
    if(value.isEmpty()||"transparent".equals(value))return value;
    if(value.length()>160||!value.endsWith(")"))return null;
    for(int i=0;i<value.length();i++)if(value.charAt(i)<32||value.charAt(i)>126)return null;
    int open=value.indexOf('(');if(open<1)return null;
    String name=value.substring(0,open),body=value.substring(open+1,value.length()-1);
    boolean rgb="rgb".equals(name)||"rgba".equals(name),srgb="color".equals(name),lab="oklab".equals(name),lch="oklch".equals(name);
    if(!rgb&&!srgb&&!lab&&!lch)return null;
    if(srgb){if(!body.startsWith("srgb "))return null;body=body.substring(5);}
    String[] slash=body.split("/",-1);if(slash.length>2)return null;
    String[] channels;String alpha="1";
    if(body.indexOf(',')>=0){
      if(!rgb||slash.length!=1)return null;
      channels=body.split(",",-1);if(channels.length==4){alpha=channels[3].trim();channels=Arrays.copyOf(channels,3);}else if(channels.length!=3)return null;
    }else{channels=slash[0].trim().split(" +",-1);if(channels.length!=3)return null;if(slash.length==2)alpha=slash[1].trim();}
    double[] numbers=new double[3];
    for(int i=0;i<3;i++){
      String token=channels[i].trim();double unit=rgb?255:(lab||lch)&&i>0?.4:1;
      if(lch&&i==2&&token.endsWith("%"))return null;
      Double number=number(token,unit);if(number==null)return null;numbers[i]=number;
      if(rgb&&(number<0||number>255)||srgb&&Math.abs(number)>1000
        ||(lab||lch)&&i==0&&(number<0||number>1)||lab&&i>0&&Math.abs(number)>10
        ||lch&&i==1&&(number<0||number>10)||lch&&i==2&&Math.abs(number)>100000)return null;
    }
    Double opacity=number(alpha,1);if(opacity==null||opacity<0||opacity>1)return null;
    if(lch)numbers[2]=(numbers[2]%360+360)%360;
    String a=format(numbers[0]),b=format(numbers[1]),c=format(numbers[2]);
    if(rgb)return opacity==1?"rgb("+a+", "+b+", "+c+")":"rgba("+a+", "+b+", "+c+", "+format(opacity)+")";
    String prefix=srgb?"color(srgb ":name+"(";
    return prefix+a+" "+b+" "+c+(opacity==1?"":" / "+format(opacity))+")";
  }
  private static Double number(String text,double percentUnit){
    if(!NUMBER.matcher(text).matches())return null;
    try{boolean percent=text.endsWith("%");double value=Double.parseDouble(percent?text.substring(0,text.length()-1):text);if(percent)value=value/100*percentUnit;return Double.isFinite(value)?value:null;}
    catch(NumberFormatException invalid){return null;}
  }
  private static String format(double value){String text=String.format(Locale.ROOT,"%.6f",value==0?0:value);int end=text.length();while(end>0&&text.charAt(end-1)=='0')end--;if(end>0&&text.charAt(end-1)=='.')end--;return text.substring(0,end);}
  private static Object measurement(Object value){return value==JSONObject.NULL?JSONObject.NULL:Math.round(((Number)value).doubleValue()*1000000d)/1000000d;}
  private static boolean luminance(Object value){if(!(value instanceof Number))return false;double n=((Number)value).doubleValue();return Double.isFinite(n)&&n>=0&&n<=1;}
  private static boolean integer(Object value,int expected){if(!(value instanceof Number))return false;double n=((Number)value).doubleValue();return Double.isFinite(n)&&n==expected;}
  JSONObject snapshot(Object port){
    Entry entry=entries.get(port);
    if(entry==null)return object("status","unavailable","desiredDark",JSONObject.NULL,"attempt",0,"version",0,"received",false,"applied",false,"storage","unavailable","colorStatus","unavailable","reason","bridge-unavailable","samples",new JSONArray());
    // Clone the small allowlisted result so a UI consumer cannot mutate state.
    return object("status",entry.status,"desiredDark",entry.dark,"attempt",entry.attempt,"version",entry.version,
      "received",entry.received,"applied",entry.applied,"storage",entry.storage,"colorStatus",entry.colorStatus,
      "reason",entry.reason,"samples",copy(entry.samples));
  }
  private static JSONArray copy(JSONArray source){try{return new JSONArray(source.toString());}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
  private static JSONObject object(Object... values){JSONObject result=new JSONObject();try{for(int i=0;i<values.length;i+=2)result.put((String)values[i],values[i+1]);return result;}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
}
