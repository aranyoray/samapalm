package android.view;
import androidx.annotation.NonNull;
public interface SurfaceHolder {
  interface Callback {
    void surfaceCreated(@NonNull SurfaceHolder holder);
    void surfaceChanged(@NonNull SurfaceHolder holder, int format, int width, int height);
    void surfaceDestroyed(@NonNull SurfaceHolder holder);
  }
  void addCallback(Callback callback);
  void setFixedSize(int width, int height);
  Surface getSurface();
}
