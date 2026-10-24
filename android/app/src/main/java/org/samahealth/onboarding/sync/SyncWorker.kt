package org.samahealth.onboarding.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.AuthFailedException
import org.samahealth.crf.CrfJson
import org.samahealth.crf.Session
import org.samahealth.crf.SupabaseClient
import org.samahealth.crf.SyncResult
import org.samahealth.crf.VisitPayload
import org.samahealth.crf.str
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.VisitEntity

/**
 * Uploads queued records, one record per row (`part` enrol or scan; v1 rows go up as "full"). Only 'pending' rows
 * are taken: a row the server rejected is left for the operator to retry by hand from Home. A refused sign-in
 * raises the "Sign in again" banner and stops the queue instead of retrying for ever. No name ever leaves the
 * phone in v2: there is no identity table.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    companion object {
        /** One upload at a time in this process, whichever worker instance runs. */
        private val uploading = Mutex()
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val c = applicationContext.container
        val client = c.client() ?: return@withContext Result.success()
        if (c.prefs.signInRequired) return@withContext Result.success()      // waiting for the operator to sign in
        var session = c.prefs.session ?: return@withContext Result.success()
        uploading.withLock {
            val queue = c.repo.queued()
            if (queue.isEmpty()) return@withLock Result.success()
            session = try {
                fresh(client, session)
            } catch (e: AuthFailedException) {
                c.prefs.signInRequired = true
                return@withLock Result.success()
            } ?: return@withLock Result.retry()
            c.prefs.session = session
            var retry = false
            for (v in queue) {
                val r = try {
                    uploadOne(client, session, v)
                } catch (e: AuthFailedException) {
                    c.prefs.signInRequired = true
                    return@withLock Result.success()
                }
                when (r) {
                    is SyncResult.AuthExpired -> {
                        session = try {
                            fresh(client, session, force = true)
                        } catch (e: AuthFailedException) {
                            c.prefs.signInRequired = true
                            return@withLock Result.success()
                        } ?: return@withLock Result.retry()
                        c.prefs.session = session
                        if (uploadOne(client, session, v) is SyncResult.Retry) retry = true
                    }
                    is SyncResult.Retry -> retry = true
                    else -> Unit
                }
            }
            if (retry) Result.retry() else Result.success()
        }
    }

    private fun fresh(client: SupabaseClient, s: Session, force: Boolean = false): Session? {
        val now = System.currentTimeMillis() / 1000
        if (!force && s.expiresAtEpochS - now > 120) return s
        return client.refresh(s.refreshToken)
    }

    private suspend fun uploadOne(client: SupabaseClient, session: Session, v: VisitEntity): SyncResult {
        val c = applicationContext.container
        val crf = v.crfJson?.let { CrfJson.parseToJsonElement(it).jsonObject }
            ?: return SyncResult.Rejected(0, "no frozen CRF")
        val pid = v.pid ?: str(crf["study_id"]) ?: return SyncResult.Rejected(0, "no PID")
        val payload = VisitPayload(
            visitUuid = v.visitUuid, pid = pid, part = v.part, status = v.status, crf = crf,
            schemaVersion = str(crf["schema_version"]) ?: "unknown", appVer = str(crf["app_ver"]) ?: c.appVersion,
            deviceCode = str(crf["device_code"]) ?: c.prefs.deviceCode,
            operatorCode = str(crf["operator"]) ?: c.prefs.operatorCode ?: "unknown",
            stream = str(crf["stream"]), createdAt = v.createdAt, updatedAt = v.updatedAt,
            submittedAt = v.submittedAt, screenFailReason = v.screenFailReason,
        )
        val r = client.upsertVisit(session.accessToken, payload)
        when (r) {
            // the server has the row: the PID is settled and may no longer be edited
            is SyncResult.Ok -> c.repo.markSync(v, "synced", null, serverAccepted = true)
            is SyncResult.DuplicatePid ->
                c.repo.markSync(v, "duplicate", "PID $pid is already used on the server for the ${v.part} record")
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
