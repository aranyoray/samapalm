package org.samahealth.onboarding.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.CrfJson
import org.samahealth.crf.Session
import org.samahealth.crf.SupabaseClient
import org.samahealth.crf.SyncResult
import org.samahealth.crf.VisitPayload
import org.samahealth.crf.str
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.VisitEntity

/**
 * Uploads queued visits. Order per visit: the CRF first, then the identity record only after the server accepted the
 * CRF, so a PID that turns out to be taken never gets a name attached to someone else's record. Identity is removed
 * from the tablet after upload when Settings > "Remove names after upload" is on.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val c = applicationContext.container
        val client = c.client() ?: return@withContext Result.success()
        var session = c.prefs.session ?: return@withContext Result.success()      // nobody signed in yet: nothing to do
        val queue = c.repo.pending()
        if (queue.isEmpty()) return@withContext Result.success()
        session = fresh(client, session) ?: return@withContext Result.retry()
        c.prefs.session = session
        var retry = false
        for (v in queue) {
            when (val r = uploadOne(client, session, v)) {
                is SyncResult.AuthExpired -> {
                    session = fresh(client, session, force = true) ?: return@withContext Result.retry()
                    c.prefs.session = session
                    if (uploadOne(client, session, v) is SyncResult.Retry) retry = true
                }
                is SyncResult.Retry -> retry = true
                else -> Unit
            }
        }
        if (retry) Result.retry() else Result.success()
    }

    private fun fresh(client: SupabaseClient, s: Session, force: Boolean = false): Session? {
        val now = System.currentTimeMillis() / 1000
        if (!force && s.expiresAtEpochS - now > 120) return s
        return try { client.refresh(s.refreshToken) } catch (e: Exception) { null }
    }

    private suspend fun uploadOne(client: SupabaseClient, session: Session, v: VisitEntity): SyncResult {
        val c = applicationContext.container
        val crf = v.crfJson?.let { CrfJson.parseToJsonElement(it).jsonObject } ?: return SyncResult.Rejected(0, "no frozen CRF")
        val pid = v.pid ?: str(crf["study_id"]) ?: return SyncResult.Rejected(0, "no PID")
        val payload = VisitPayload(
            // v1 rows carry no part; the server treats "full" as a single legacy record
            visitUuid = v.visitUuid, pid = pid, part = str(crf["part"]) ?: "full", status = v.status, crf = crf,
            schemaVersion = str(crf["schema_version"]) ?: "unknown", appVer = str(crf["app_ver"]) ?: c.appVersion,
            deviceCode = str(crf["device_code"]) ?: c.prefs.deviceCode,
            operatorCode = str(crf["operator"]) ?: c.prefs.operatorCode ?: "unknown", stream = str(crf["stream"]), createdAt = v.createdAt,
            updatedAt = v.updatedAt, submittedAt = v.submittedAt, screenFailReason = v.screenFailReason,
        )
        val r = client.upsertVisit(session.accessToken, payload)
        when (r) {
            is SyncResult.Ok -> {
                var identityOk = v.identitySynced
                if (!identityOk) {
                    val ident = c.repo.identity(v.visitUuid)
                    if (ident?.name.isNullOrBlank()) {
                        identityOk = true                       // nothing to send (screen failure before identity, or purged)
                    } else {
                        val body = JsonObject(mapOf("pid" to JsonPrimitive(pid), "name" to JsonPrimitive(ident!!.name),
                            "hospital_reg_no" to (ident.hospitalRegNo?.let { JsonPrimitive(it) } ?: JsonNull),
                            "phone" to (ident.phone?.let { JsonPrimitive(it) } ?: JsonNull)))
                        val ir = client.submitIdentity(session.accessToken, body)
                        identityOk = ir is SyncResult.Ok
                        if (!identityOk) {
                            c.repo.markSync(v, if (ir is SyncResult.Retry) "pending" else "error", "identity: ${describe(ir)}", false)
                            return ir
                        }
                    }
                }
                c.repo.markSync(v, "synced", null, identityOk)
                if (identityOk && c.prefs.purgeIdentityAfterUpload) c.repo.purgeIdentity(v.visitUuid)
            }
            is SyncResult.DuplicatePid -> c.repo.markSync(v, "duplicate", "PID $pid is already used on the server by another visit")
            is SyncResult.Rejected -> c.repo.markSync(v, "error", describe(r))
            is SyncResult.Retry -> c.repo.markSync(v, "pending", describe(r))
            is SyncResult.AuthExpired -> Unit
        }
        return r
    }

    private fun describe(r: SyncResult): String = when (r) {
        is SyncResult.Ok -> "ok"
        is SyncResult.DuplicatePid -> "duplicate PID ${r.pid}"
        is SyncResult.AuthExpired -> "sign-in expired"
        is SyncResult.Rejected -> "rejected (${r.code}): ${r.detail.take(200)}"
        is SyncResult.Retry -> "will retry: ${r.detail.take(200)}"
    }
}
