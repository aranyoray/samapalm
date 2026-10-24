package android.view;
public abstract class ViewGroup extends View {
  public ViewGroup(android.content.Context context) { super(context); }
  public void addView(View child, ViewGroup.LayoutParams params) {}
  public static class LayoutParams { public static final int MATCH_PARENT = -1; public static final int WRAP_CONTENT = -2; public LayoutParams(int w, int h) {} }
  public static class MarginLayoutParams extends LayoutParams { public MarginLayoutParams(int w, int h) { super(w, h); } }
}
