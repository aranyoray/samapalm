package android.hardware.camera2;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
public abstract class CameraDevice implements AutoCloseable {
  public static final int TEMPLATE_RECORD = 3;
  public abstract @NonNull CaptureRequest.Builder createCaptureRequest(int templateType) throws CameraAccessException;
  @Deprecated public abstract void createCaptureSession(@NonNull java.util.List<android.view.Surface> outputs, @NonNull CameraCaptureSession.StateCallback callback, @Nullable android.os.Handler handler) throws CameraAccessException;
  public abstract void close();
  public static abstract class StateCallback {
    public abstract void onOpened(@NonNull CameraDevice camera);
    public abstract void onDisconnected(@NonNull CameraDevice camera);
    public abstract void onError(@NonNull CameraDevice camera, int error);
    public void onClosed(@NonNull CameraDevice camera) {}
  }
}
