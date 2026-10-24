package android.media;
public class MediaRecorder {
  @Deprecated public MediaRecorder() {}
  public MediaRecorder(@androidx.annotation.NonNull android.content.Context context) {}
  public final class AudioSource { public static final int MIC = 1; }
  public final class VideoSource { public static final int SURFACE = 2; }
  public final class OutputFormat { public static final int MPEG_4 = 2; }
  public final class VideoEncoder { public static final int H264 = 2; }
  public final class AudioEncoder { public static final int AAC = 3; }
  public native void setAudioSource(int audioSource) throws IllegalStateException;
  public native void setVideoSource(int videoSource) throws IllegalStateException;
  public void setOutputFormat(int output_format) throws IllegalStateException {}
  public void setOutputFile(String path) throws IllegalStateException {}
  public native void setVideoEncoder(int video_encoder) throws IllegalStateException;
  public void setVideoSize(int width, int height) throws IllegalStateException {}
  public void setVideoFrameRate(int rate) throws IllegalStateException {}
  public void setVideoEncodingBitRate(int bitRate) {}
  public native void setAudioEncoder(int audio_encoder) throws IllegalStateException;
  public void setAudioSamplingRate(int samplingRate) {}
  public void setAudioChannels(int numChannels) {}
  public void setAudioEncodingBitRate(int bitRate) {}
  public void prepare() throws IllegalStateException, java.io.IOException {}
  public native void start() throws IllegalStateException;
  public native void stop() throws IllegalStateException;
  public native void release();
  public native android.view.Surface getSurface();
}
