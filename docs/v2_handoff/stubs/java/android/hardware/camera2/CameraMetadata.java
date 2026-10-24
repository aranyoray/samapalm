package android.hardware.camera2;
public abstract class CameraMetadata<TKey> {
  public static final int LENS_FACING_BACK = 1;
  public static final int CONTROL_MODE_AUTO = 1;
  public static final int CONTROL_SCENE_MODE_DISABLED = 0;
  public static final int CONTROL_VIDEO_STABILIZATION_MODE_OFF = 0;
  public static final int LENS_OPTICAL_STABILIZATION_MODE_OFF = 0;
  public static final int NOISE_REDUCTION_MODE_OFF = 0;
  public static final int EDGE_MODE_OFF = 0;
  public static final int TONEMAP_MODE_FAST = 1;
  public static final int FLASH_MODE_OFF = 0;
  public static final int FLASH_MODE_TORCH = 2;
  public static final int CONTROL_AF_MODE_OFF = 0;
  public static final int CONTROL_AF_MODE_AUTO = 1;
  public static final int CONTROL_AF_TRIGGER_START = 1;
}
