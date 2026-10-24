package android.content;
import androidx.annotation.Nullable;
public interface SharedPreferences {
  @Nullable String getString(String key, @Nullable String defValue);
  int getInt(String key, int defValue);
  long getLong(String key, long defValue);
  boolean getBoolean(String key, boolean defValue);
  Editor edit();
  interface Editor {
    Editor putString(String key, @Nullable String value);
    Editor putInt(String key, int value);
    Editor putLong(String key, long value);
    Editor putBoolean(String key, boolean value);
    Editor remove(String key);
    Editor clear();
    boolean commit();
    void apply();
  }
}
