package android.os;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public class Handler {
  public Handler(@NonNull Looper looper) {}
  public final boolean postDelayed(@NonNull Runnable r, long delayMillis) { return true; }
  public final boolean postDelayed(@NonNull Runnable r, @Nullable Object token, long delayMillis) { return true; }
  public final boolean post(@NonNull Runnable r) { return true; }
}
