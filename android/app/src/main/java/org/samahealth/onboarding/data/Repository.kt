package org.samahealth.onboarding.data

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.CrfJson
import org.samahealth.crf.PidAllocator
import org.samahealth.crf.str
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * Local persistence for visit records. Every write goes through [writer], so the survey's autosave, a submission
 * and the sync worker's bookkeeping can never interleave on one row. Names are not stored at all in v2.
 */
class Repository(private val db: AppDatabase, private val prefs: Prefs) {
    private val pids = PidAllocator()

    /** One serial writer for every visit write (design section 6). */
    private val writer = Mutex()

    fun observeVisits(): Flow<List<VisitEntity>> = db.visits().observeAll()

    fun observeVisits(part: String): Flow<List<VisitEntity>> = db.visits().observePart(part)

    suspend fun visit(id: String): VisitEntity? = db.visits().get(id)

    /** Every record on this phone, newest first; a one-shot read for screens that do not need a Flow. */
    suspend fun allVisits(): List<VisitEntity> = db.visits().all()

    fun now(): String = OffsetDateTime.now(ZoneId.systemDefault()).format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)

    /** A new record for [part]; [settings] is the engine snapshot it will always re-open on. */
    suspend fun newVisit(part: String, firstScreen: String, settings: Map<String, JsonElement>): VisitEntity =
        writer.withLock {
            val t = now()
            val v = VisitEntity(
                visitUuid = UUID.randomUUID().toString(), pid = null, part = part, answersJson = "{}",
                screenLogJson = "[]", currentScreen = firstScreen,
                settingsJson = CrfJson.encodeToString(JsonObject.serializer(), JsonObject(settings)),
                status = "draft", createdAt = t, updatedAt = t, submittedAt = null, screenFailReason = null,
                crfJson = null, syncState = "local", syncError = null, serverAccepted = false, everSubmitted = false,
            )
            db.visits().upsert(v)
            v
        }

    /** The engine settings a visit was created with; empty for a v1 row. */
    suspend fun settingsOf(visitUuid: String): Map<String, JsonElement> {
        val v = db.visits().get(visitUuid) ?: return emptyMap()
        return runCatching { CrfJson.parseToJsonElement(v.settingsJson).jsonObject.toMap() }.getOrDefault(emptyMap())
    }

    /** Next PID from this tablet's block, skipping every PID already on this tablet. */
    suspend fun nextPid(): String? = pids.next(prefs.pidBlockStart, prefs.pidBlockEnd, db.visits().usedPids())

    /** Another record of the same part on this phone already uses the PID (the two parts share one PID). */
    suspend fun pidUsedLocally(pid: String, part: String, visitUuid: String): Boolean =
        db.visits().pidUsedByOther(pid, part, visitUuid) > 0

    /** Autosave. A conditional update: once the visit leaves draft the write is dropped. */
    suspend fun saveDraft(
        visitUuid: String,
        answers: Map<String, JsonElement>,
        screenLog: JsonElement,
        currentScreen: String,
    ): Boolean = writer.withLock {
        db.visits().updateDraft(
            id = visitUuid, pid = str(answers["study_id"]),
            answers = CrfJson.encodeToString(JsonObject.serializer(), JsonObject(answers)),
            log = CrfJson.encodeToString(JsonElement.serializer(), screenLog),
            screen = currentScreen, t = now(),
        ) > 0
    }

    suspend fun loadAnswers(visitUuid: String): Map<String, JsonElement> {
        val v = db.visits().get(visitUuid) ?: return emptyMap()
        return runCatching { CrfJson.parseToJsonElement(v.answersJson).jsonObject.toMap() }.getOrDefault(emptyMap())
    }

    /** Freeze the export and queue the record for upload. [crf] is the snapshot the caller built. */
    suspend fun submit(visitUuid: String, status: String, crf: JsonObject, screenFailReason: String?) =
        writer.withLock {
            val old = db.visits().get(visitUuid) ?: return@withLock
            val t = now()
            db.visits().upsert(
                old.copy(
                    status = status, crfJson = CrfJson.encodeToString(JsonObject.serializer(), crf),
                    submittedAt = t, updatedAt = t, screenFailReason = screenFailReason, syncState = "pending",
                    syncError = null, pid = str(crf["study_id"]) ?: old.pid, everSubmitted = true,
                ),
            )
        }

    /** Re-open a submitted record for correction (for example after a duplicate-PID rejection). */
    suspend fun reopen(visitUuid: String) = writer.withLock {
        val old = db.visits().get(visitUuid) ?: return@withLock
        db.visits().upsert(old.copy(status = "draft", syncState = "local", syncError = null, updatedAt = now()))
    }

    /** Only a draft that was never submitted can be discarded. Returns false when the row was kept. */
    suspend fun deleteDraft(visitUuid: String): Boolean = writer.withLock { db.visits().deleteDraft(visitUuid) > 0 }

    /** Rows the automatic queue may send; 'error' rows wait for the operator to press Retry. */
    suspend fun queued(): List<VisitEntity> = db.visits().queued()

    /** Rows the operator can retry by hand. */
    suspend fun pending(): List<VisitEntity> = db.visits().pending()

    suspend fun activeScanDrafts(): List<VisitEntity> = db.visits().activeScanDrafts()

    suspend fun submittedEnrolments(): List<VisitEntity> = db.visits().submittedEnrolments()

    /** Submitted enrol parts this phone has not uploaded yet: they are added to the server's strata counts. */
    suspend fun unsyncedEnrolments(): List<VisitEntity> = db.visits().unsyncedEnrolments()

    /**
     * Record an upload outcome. Skipped when the row changed while the upload ran, so a correction made during
     * the upload is never overwritten.
     */
    suspend fun markSync(v: VisitEntity, state: String, error: String?, serverAccepted: Boolean = v.serverAccepted) =
        writer.withLock {
            val cur = db.visits().get(v.visitUuid) ?: return@withLock
            if (cur.updatedAt != v.updatedAt || cur.status != v.status) return@withLock
            db.visits().upsert(cur.copy(syncState = state, syncError = error, serverAccepted = serverAccepted))
        }

    // ---- Kardia files shared in from the Kardia app
    fun observeEcgInbox(visitUuid: String): Flow<List<EcgInboxEntity>> = db.ecgInbox().observe(visitUuid)

    suspend fun addEcgInbox(visitUuid: String, clipId: String, relPath: String) =
        db.ecgInbox().upsert(EcgInboxEntity(visitUuid = visitUuid, clipId = clipId, relPath = relPath, createdAt = now()))

    suspend fun consumeEcgInbox(id: Long) = db.ecgInbox().consume(id)
}
