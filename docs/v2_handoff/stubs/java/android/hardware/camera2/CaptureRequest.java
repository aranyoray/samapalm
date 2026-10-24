package android.hardware.camera2;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public final class CaptureRequest extends CameraMetadata<CaptureRequest.Key<?>> {
  public static final class Key<T> {}
  public static final class Builder {
    public void addTarget(@NonNull android.view.Surface outputTarget) {}
    public <T> void set(@NonNull Key<T> key, T value) {}
    public @NonNull CaptureRequest build() { return null; }
  }
  @NonNull public static final Key<Integer> CONTROL_MODE = new Key<>();
  @NonNull public static final Key<Integer> CONTROL_SCENE_MODE = new Key<>();
  @NonNull public static final Key<Integer> CONTROL_VIDEO_STABILIZATION_MODE = new Key<>();
  @NonNull public static final Key<Integer> LENS_OPTICAL_STABILIZATION_MODE = new Key<>();
  @NonNull public static final Key<Integer> NOISE_REDUCTION_MODE = new Key<>();
  @NonNull public static final Key<Integer> EDGE_MODE = new Key<>();
  @NonNull public static final Key<Integer> TONEMAP_MODE = new Key<>();
  @NonNull public static final Key<android.util.Range<Integer>> CONTROL_AE_TARGET_FPS_RANGE = new Key<>();
  @NonNull public static final Key<Integer> FLASH_MODE = new Key<>();
  @NonNull public static final Key<Boolean> CONTROL_AE_LOCK = new Key<>();
  @NonNull public static final Key<Boolean> CONTROL_AWB_LOCK = new Key<>();
  @NonNull public static final Key<Integer> CONTROL_AF_MODE = new Key<>();
  @NonNull public static final Key<Float> LENS_FOCUS_DISTANCE = new Key<>();
  @NonNull public static final Key<Integer> CONTROL_AF_TRIGGER = new Key<>();
}
