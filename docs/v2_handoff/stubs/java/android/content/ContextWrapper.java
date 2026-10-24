package android.content;
public class ContextWrapper extends Context {
  public Context getApplicationContext() { return null; }
  public android.content.res.AssetManager getAssets() { return null; }
  public android.content.pm.PackageManager getPackageManager() { return null; }
  public String getPackageName() { return null; }
  public Object getSystemService(String name) { return null; }
  public int checkSelfPermission(String permission) { return 0; }
  public java.io.File getExternalFilesDir(String type) { return null; }
}
