package android.app;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public class Activity extends android.view.ContextThemeWrapper {
  public static final int RESULT_OK = -1; public static final int RESULT_CANCELED = 0;
  protected void onCreate(@Nullable android.os.Bundle savedInstanceState) {}
  protected void onDestroy() {}
  public android.content.Intent getIntent() { return null; }
  public void setContentView(android.view.View view) {}
  public final void requestPermissions(@NonNull String[] permissions, int requestCode) {}
  public final void runOnUiThread(Runnable action) {}
  public final void setResult(int resultCode, android.content.Intent data) {}
  public void finish() {}
}
