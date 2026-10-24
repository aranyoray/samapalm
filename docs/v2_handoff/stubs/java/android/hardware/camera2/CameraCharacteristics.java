package android.hardware.camera2;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public final class CameraCharacteristics extends CameraMetadata<CameraCharacteristics.Key<?>> {
  public static final class Key<T> {}
  public <T> @Nullable T get(@NonNull Key<T> key) { return null; }
  @NonNull public static final Key<Integer> LENS_FACING = new Key<Integer>();
}
