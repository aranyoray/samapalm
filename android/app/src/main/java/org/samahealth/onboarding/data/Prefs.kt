package org.samahealth.onboarding.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import org.samahealth.crf.Session

/**
 * Tablet settings and the sign-in session, encrypted at rest (Android Keystore). Configured once per tablet by the
 * study admin in Settings: Supabase project, device code, PID block, unit, clip plan, rest time, default stream.
 */
class Prefs(context: Context) {
    private val sp: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "samahealth_prefs",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    private fun s(k: String): String? = sp.getString(k, null)
    private fun put(k: String, v: String?) = sp.edit().putString(k, v).apply()

    var supabaseUrl: String? get() = s("supabase_url"); set(v) = put("supabase_url", v?.trim())
    var supabaseAnonKey: String? get() = s("supabase_anon_key"); set(v) = put("supabase_anon_key", v?.trim())
    var deviceCode: String get() = s("device_code") ?: "tab-A"; set(v) = put("device_code", v.trim())
    var unitId: String get() = s("unit_id") ?: "unit_01"; set(v) = put("unit_id", v.trim())
    var pidBlockStart: Int get() = sp.getInt("pid_block_start", 1); set(v) = sp.edit().putInt("pid_block_start", v).apply()
    var pidBlockEnd: Int get() = sp.getInt("pid_block_end", 999); set(v) = sp.edit().putInt("pid_block_end", v).apply()
    var clipPlan: String get() = s("clip_plan") ?: "1x60"; set(v) = put("clip_plan", v)
    var restSeconds: Int get() = sp.getInt("rest_seconds", 300); set(v) = sp.edit().putInt("rest_seconds", v).apply()
    var defaultStream: String get() = s("stream") ?: "pilot"; set(v) = put("stream", v)
    var captureMode: String get() = s("capture_mode") ?: "simultaneous"; set(v) = put("capture_mode", v)
    var purgeIdentityAfterUpload: Boolean
        get() = sp.getBoolean("purge_identity", true)
        set(v) = sp.edit().putBoolean("purge_identity", v).apply()

    var operatorCode: String? get() = s("operator_code"); set(v) = put("operator_code", v)
    var operatorRole: String? get() = s("operator_role"); set(v) = put("operator_role", v)

    var session: Session?
        get() {
            val at = s("access_token") ?: return null
            return Session(at, s("refresh_token") ?: "", sp.getLong("expires_at", 0L), s("user_id") ?: "", s("email"))
        }
        set(v) {
            sp.edit().apply {
                if (v == null) {
                    remove("access_token"); remove("refresh_token"); remove("expires_at"); remove("user_id"); remove("email")
                } else {
                    putString("access_token", v.accessToken); putString("refresh_token", v.refreshToken)
                    putLong("expires_at", v.expiresAtEpochS); putString("user_id", v.userId); putString("email", v.email)
                }
            }.apply()
        }

    val isConfigured: Boolean get() = !supabaseUrl.isNullOrBlank() && !supabaseAnonKey.isNullOrBlank()

    /** Settings the survey engine reads (`settings_defaults` overrides in configs/crf_schema.json). */
    fun engineSettings(): Map<String, JsonElement> = mapOf(
        "clip_plan" to JsonPrimitive(clipPlan),
        "rest_seconds" to JsonPrimitive(restSeconds),
        "stream" to JsonPrimitive(defaultStream),
        "unit_id" to JsonPrimitive(unitId),
        "capture_mode" to JsonPrimitive(captureMode),
    )
}
