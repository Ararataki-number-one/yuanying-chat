package android.content;
public interface SharedPreferences {
  String getString(String key,String fallback);int getInt(String key,int fallback);
  Editor edit();
  interface Editor {Editor clear();Editor putBoolean(String key,boolean value);Editor putString(String key,String value);Editor putInt(String key,int value);boolean commit();}
}
