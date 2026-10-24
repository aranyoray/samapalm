package android.content;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public class Intent {
  public Intent() {}
  public Intent(Context packageContext, Class<?> cls) {}
  public @NonNull Intent putExtra(String name, @Nullable String value) { return this; }
  public @NonNull Intent putExtra(String name, int value) { return this; }
  public @NonNull Intent putExtra(String name, boolean value) { return this; }
  public @Nullable String getStringExtra(String name) { return null; }
}
