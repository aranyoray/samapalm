package android.hardware.camera2;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public abstract class CameraCaptureSession implements AutoCloseable {
  public abstract int setRepeatingRequest(@NonNull CaptureRequest request, @Nullable CaptureCallback listener, @Nullable android.os.Handler handler) throws CameraAccessException;
  public abstract void stopRepeating() throws CameraAccessException;
  public abstract void close();
  public static abstract class StateCallback {
    public abstract void onConfigured(@NonNull CameraCaptureSession session);
    public abstract void onConfigureFailed(@NonNull CameraCaptureSession session);
  }
  public static abstract class CaptureCallback {
    public void onCaptureCompleted(@NonNull CameraCaptureSession session, @NonNull CaptureRequest request, @NonNull TotalCaptureResult result) {}
  }
}
