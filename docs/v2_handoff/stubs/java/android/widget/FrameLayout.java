package android.widget;
public class FrameLayout extends android.view.ViewGroup {
  public FrameLayout(android.content.Context context) { super(context); }
  public static class LayoutParams extends android.view.ViewGroup.MarginLayoutParams {
    public LayoutParams(int width, int height) { super(width, height); }
    public LayoutParams(int width, int height, int gravity) { super(width, height); }
  }
}
