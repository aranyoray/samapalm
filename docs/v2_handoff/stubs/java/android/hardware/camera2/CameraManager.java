package android.hardware.camera2;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public final class CameraManager {
  public @NonNull String[] getCameraIdList() throws CameraAccessException { return null; }
  public @NonNull CameraCharacteristics getCameraCharacteristics(@NonNull String cameraId) throws CameraAccessException { return null; }
  public void openCamera(@NonNull String cameraId, @NonNull final CameraDevice.StateCallback callback, @Nullable android.os.Handler handler) throws CameraAccessException {}
}
