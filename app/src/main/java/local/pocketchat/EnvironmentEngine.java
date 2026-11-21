package local.pocketchat;

import android.content.SharedPreferences;

/** A binding is written only while reserving a new environment identity. */
enum EnvironmentEngine {
  GECKO("Firefox（Gecko）"), CHROMIUM("Chromium"), UNAVAILABLE("无法读取");
  static final String KEY="browserStartScreen", GECKO_TOKEN="chatgpt-enhanced", CHROMIUM_TOKEN="chromium";
  final String label;
  EnvironmentEngine(String label){this.label=label;}

  static EnvironmentEngine read(SharedPreferences prefs){
    try{
      String token=prefs.getString(KEY,GECKO_TOKEN);
      return GECKO_TOKEN.equals(token)?GECKO:CHROMIUM_TOKEN.equals(token)?CHROMIUM:UNAVAILABLE;
    }catch(RuntimeException inaccessible){return UNAVAILABLE;}
  }

  static SharedPreferences.Editor stageNew(SharedPreferences.Editor edit,EnvironmentEngine engine){
    if(engine==null||engine==UNAVAILABLE)throw new IllegalArgumentException("无效的浏览器内核");
    return edit.putString(KEY,engine==CHROMIUM?CHROMIUM_TOKEN:GECKO_TOKEN);
  }
}
