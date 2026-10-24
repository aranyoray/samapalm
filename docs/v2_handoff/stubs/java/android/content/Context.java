package android.content;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public abstract class Context {
  public static final String CAMERA_SERVICE = "camera";
  public abstract Context getApplicationContext();
  public abstract android.content.res.AssetManager getAssets();
  public abstract android.content.pm.PackageManager getPackageManager();
  public abstract String getPackageName();
  public abstract @Nullable Object getSystemService(@NonNull String name);
  public abstract int checkSelfPermission(@NonNull String permission);
  public abstract @Nullable java.io.File getExternalFilesDir(@Nullable String type);
}
