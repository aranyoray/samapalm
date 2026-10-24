package androidx.security.crypto;
import androidx.annotation.NonNull;
public abstract class EncryptedSharedPreferences implements android.content.SharedPreferences {
  public enum PrefKeyEncryptionScheme { AES256_SIV }
  public enum PrefValueEncryptionScheme { AES256_GCM }
  public static @NonNull android.content.SharedPreferences create(@NonNull android.content.Context context, @NonNull String fileName, @NonNull MasterKey masterKey,
      @NonNull PrefKeyEncryptionScheme prefKeyEncryptionScheme, @NonNull PrefValueEncryptionScheme prefValueEncryptionScheme) throws java.security.GeneralSecurityException, java.io.IOException { return null; }
  @Deprecated public static @NonNull android.content.SharedPreferences create(@NonNull String fileName, @NonNull String masterKeyAlias, @NonNull android.content.Context context,
      @NonNull PrefKeyEncryptionScheme prefKeyEncryptionScheme, @NonNull PrefValueEncryptionScheme prefValueEncryptionScheme) throws java.security.GeneralSecurityException, java.io.IOException { return null; }
}
