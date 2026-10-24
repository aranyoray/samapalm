package androidx.security.crypto;
import androidx.annotation.NonNull;
public final class MasterKey {
  public enum KeyScheme { AES256_GCM }
  public static final class Builder {
    public Builder(@NonNull android.content.Context context) {}
    public Builder(@NonNull android.content.Context context, @NonNull String keyAlias) {}
    public @NonNull Builder setKeyScheme(@NonNull KeyScheme keyScheme) { return this; }
    public @NonNull MasterKey build() throws java.security.GeneralSecurityException, java.io.IOException { return null; }
  }
}
