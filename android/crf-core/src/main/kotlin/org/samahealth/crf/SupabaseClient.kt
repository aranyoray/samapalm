package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Supabase project endpoint and its public (anon) key; row-level security does the access control. */
data class SupabaseConfig(val url: String, val anonKey: String) {
    val base: String get() = url.trimEnd('/')
}

data class Session(val accessToken: String, val refreshToken: String, val expiresAtEpochS: Long, val userId: String, val email: String?)

/** Row sent to `public.visits` (one per participant; `visit_uuid` is generated on the tablet, so retries are idempotent). */
data class VisitPayload(
    val visitUuid: String,
    val pid: String,
    val status: String,               // draft | submitted | screen_fail
    val crf: JsonObject,
    val schemaVersion: String,
    val appVer: String,
    val deviceCode: String,
    val operatorCode: String,
    val stream: String?,
    val createdAt: String,
    val updatedAt: String,
    val submittedAt: String?,
    val screenFailReason: String?,
) {
    fun toJson(): JsonObject = JsonObject(mapOf(
        "visit_uuid" to JsonPrimitive(visitUuid), "pid" to JsonPrimitive(pid), "status" to JsonPrimitive(status), "crf" to crf,
        "schema_version" to JsonPrimitive(schemaVersion), "app_ver" to JsonPrimitive(appVer), "device_code" to JsonPrimitive(deviceCode),
        "operator_code" to JsonPrimitive(operatorCode), "stream" to (stream?.let { JsonPrimitive(it) } ?: JsonNull),
        "created_at" to JsonPrimitive(createdAt), "updated_at" to JsonPrimitive(updatedAt),
        "submitted_at" to (submittedAt?.let { JsonPrimitive(it) } ?: JsonNull),
        "screen_fail_reason" to (screenFailReason?.let { JsonPrimitive(it) } ?: JsonNull),
    ))
}

sealed class SyncResult {
    object Ok : SyncResult()
    data class DuplicatePid(val pid: String, val detail: String) : SyncResult()
    data class AuthExpired(val detail: String) : SyncResult()
    data class Rejected(val code: Int, val detail: String) : SyncResult()     // validation / RLS refusal: needs a person
    data class Retry(val detail: String) : SyncResult()                       // network or 5xx: try again later
}

class SupabaseException(val code: Int, msg: String) : IOException(msg)

/**
 * Minimal Supabase client over OkHttp (GoTrue auth + PostgREST). No Supabase SDK, so the same code is tested on the
 * JVM (MockWebServer) and runs on Android.
 *  - sign in / refresh: POST /auth/v1/token?grant_type=password|refresh_token
 *  - upsert visit: POST /rest/v1/visits?on_conflict=visit_uuid (merge-duplicates); a different visit with the same PID
 *    violates the unique PID constraint and comes back as HTTP 409 -> DuplicatePid
 *  - identity: POST /rest/v1/rpc/submit_identity (operators cannot read the identity table)
 *  - PID: POST /rest/v1/rpc/allocate_pid; existence check GET /rest/v1/visits?pid=eq.X
 */
class SupabaseClient(private val cfg: SupabaseConfig, private val http: OkHttpClient = defaultHttp()) {
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    private fun req(path: String, token: String?): Request.Builder =
        Request.Builder().url(cfg.base + path).header("apikey", cfg.anonKey)
            .header("Authorization", "Bearer " + (token ?: cfg.anonKey))

    private fun bodyOf(r: Response): String = r.body?.string() ?: ""

    private fun parseSession(text: String): Session {
        val o = CrfJson.parseToJsonElement(text).jsonObject
        val user = o["user"] as? JsonObject
        val expiresIn = num(o["expires_in"])?.toLong() ?: 3600L
        val expiresAt = num(o["expires_at"])?.toLong() ?: (System.currentTimeMillis() / 1000 + expiresIn)
        return Session(str(o["access_token"])!!, str(o["refresh_token"]) ?: "", expiresAt, str(user?.get("id")) ?: "", str(user?.get("email")))
    }

    fun signIn(email: String, password: String): Session {
        val body = CrfJson.encodeToString(JsonObject.serializer(), JsonObject(mapOf("email" to JsonPrimitive(email), "password" to JsonPrimitive(password))))
        http.newCall(req("/auth/v1/token?grant_type=password", null).post(body.toRequestBody(jsonType)).build()).execute().use { r ->
            val t = bodyOf(r)
            if (!r.isSuccessful) throw SupabaseException(r.code, "sign-in failed: ${r.code} $t")
            return parseSession(t)
        }
    }

    fun refresh(refreshToken: String): Session {
        val body = CrfJson.encodeToString(JsonObject.serializer(), JsonObject(mapOf("refresh_token" to JsonPrimitive(refreshToken))))
        http.newCall(req("/auth/v1/token?grant_type=refresh_token", null).post(body.toRequestBody(jsonType)).build()).execute().use { r ->
            val t = bodyOf(r)
            if (!r.isSuccessful) throw SupabaseException(r.code, "refresh failed: ${r.code} $t")
            return parseSession(t)
        }
    }

    private fun classify(code: Int, text: String, pid: String?): SyncResult = when {
        code in 200..299 -> SyncResult.Ok
        code == 409 || text.contains("23505") -> SyncResult.DuplicatePid(pid ?: "", text)
        code == 401 || (code == 403 && text.contains("JWT", ignoreCase = true)) -> SyncResult.AuthExpired(text)
        code == 408 || code == 429 || code >= 500 -> SyncResult.Retry("$code $text")
        else -> SyncResult.Rejected(code, text)
    }

    private fun post(path: String, token: String, payload: JsonElement, prefer: String?, pid: String?): SyncResult {
        val b = req(path, token).post(CrfJson.encodeToString(JsonElement.serializer(), payload).toRequestBody(jsonType))
        if (prefer != null) b.header("Prefer", prefer)
        return try {
            http.newCall(b.build()).execute().use { r -> classify(r.code, bodyOf(r), pid) }
        } catch (e: IOException) {
            SyncResult.Retry(e.message ?: "network error")
        }
    }

    fun upsertVisit(token: String, v: VisitPayload): SyncResult =
        post("/rest/v1/visits?on_conflict=visit_uuid", token, v.toJson(), "resolution=merge-duplicates,return=minimal", v.pid)

    fun submitIdentity(token: String, identity: JsonObject): SyncResult {
        val p = JsonObject(mapOf(
            "p_pid" to (identity["pid"] ?: JsonNull), "p_name" to (identity["name"] ?: JsonNull),
            "p_hospital_reg_no" to (identity["hospital_reg_no"] ?: JsonNull), "p_phone" to (identity["phone"] ?: JsonNull)))
        return post("/rest/v1/rpc/submit_identity", token, p, null, str(identity["pid"]))
    }

    fun allocatePid(token: String, deviceCode: String): String {
        val body = CrfJson.encodeToString(JsonObject.serializer(), JsonObject(mapOf("p_device" to JsonPrimitive(deviceCode))))
        http.newCall(req("/rest/v1/rpc/allocate_pid", token).post(body.toRequestBody(jsonType)).build()).execute().use { r ->
            val t = bodyOf(r)
            if (!r.isSuccessful) throw SupabaseException(r.code, "allocate_pid failed: ${r.code} $t")
            return str(CrfJson.parseToJsonElement(t)) ?: throw SupabaseException(r.code, "allocate_pid returned $t")
        }
    }

    /** True when the server already has a visit with this PID under a different visit_uuid. */
    fun pidTakenElsewhere(token: String, pid: String, visitUuid: String): Boolean {
        val url = "/rest/v1/visits?select=visit_uuid&pid=eq." + java.net.URLEncoder.encode(pid, "UTF-8")
        http.newCall(req(url, token).get().build()).execute().use { r ->
            val t = bodyOf(r)
            if (!r.isSuccessful) throw SupabaseException(r.code, "lookup failed: ${r.code} $t")
            val arr = CrfJson.parseToJsonElement(t) as? JsonArray ?: return false
            return arr.any { str(it.jsonObject["visit_uuid"]) != visitUuid }
        }
    }

    /** (operator_code, role) of the signed-in user from public.operators, or null if the account has no profile. */
    fun operatorProfile(token: String, userId: String): Pair<String, String>? {
        val url = "/rest/v1/operators?select=operator_code,role,active&user_id=eq." + java.net.URLEncoder.encode(userId, "UTF-8")
        http.newCall(req(url, token).get().build()).execute().use { r ->
            val t = bodyOf(r)
            if (!r.isSuccessful) throw SupabaseException(r.code, "profile lookup failed: ${r.code} $t")
            val row = (CrfJson.parseToJsonElement(t) as? JsonArray)?.firstOrNull()?.jsonObject ?: return null
            if (bool(row["active"]) == false) return null
            return (str(row["operator_code"]) ?: return null) to (str(row["role"]) ?: "operator")
        }
    }

    companion object {
        fun defaultHttp(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS).writeTimeout(30, TimeUnit.SECONDS).build()
    }
}
