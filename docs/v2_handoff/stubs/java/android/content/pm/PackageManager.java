package android.content.pm;
import androidx.annotation.NonNull;
public abstract class PackageManager {
  public static final int PERMISSION_GRANTED = 0;
  public static class NameNotFoundException extends Exception {}
  public static final class PackageInfoFlags { public static @NonNull PackageInfoFlags of(long value) { return null; } }
  @Deprecated public abstract PackageInfo getPackageInfo(@NonNull String packageName, int flags) throws NameNotFoundException;
  public @NonNull PackageInfo getPackageInfo(@NonNull String packageName, @NonNull PackageInfoFlags flags) throws NameNotFoundException { return null; }
}
