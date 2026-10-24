package android.hardware.camera2;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public class CaptureResult extends CameraMetadata<CaptureResult.Key<?>> {
  public static final class Key<T> {}
  public @Nullable <T> T get(Key<T> key) { return null; }
  @NonNull public static final Key<Long> SENSOR_TIMESTAMP = new Key<>();
  @NonNull public static final Key<Integer> SENSOR_SENSITIVITY = new Key<>();
  @NonNull public static final Key<Long> SENSOR_EXPOSURE_TIME = new Key<>();
  @NonNull public static final Key<Float> LENS_FOCUS_DISTANCE = new Key<>();
}
