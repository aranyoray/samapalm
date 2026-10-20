package org.samahealth.onboarding.data

import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.CrfEngine
import org.samahealth.crf.CrfJson
import org.samahealth.crf.PidAllocator
import org.samahealth.crf.str
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

/** Local persistence for visits, with identity answers split off into their own table (name and PID kept apart). */
class Repository(private val db: AppDatabase, private val prefs: Prefs) {
    private val pids = PidAllocator()

    fun observeVisits(): Flow<List<VisitEntity>> = db.visits().observeAll()

    suspend fun visit(id: String): VisitEntity? = db.visits().get(id)

    suspend fun identity(id: String): IdentityEntity? = db.identity().get(id)

    fun now(): String = OffsetDateTime.now(ZoneId.systemDefault()).format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)

    suspend fun newVisit(firstScreen: String): VisitEntity {
        val t = now()
        val v = VisitEntity(UUID.randomUUID().toString(), null, "{}", "[]", firstScreen, "draft", t, t, null, null, null, "local", null, false)
        db.visits().upsert(v)
        return v
    }

    /** Next PID from this tablet's block, skipping every PID already on this tablet. */
    suspend fun nextPid(): String? = pids.next(prefs.pidBlockStart, prefs.pidBlockEnd, db.visits().usedPids())

    suspend fun pidUsedLocally(pid: String, visitUuid: String): Boolean = db.visits().pidUsedByOther(pid, visitUuid) > 0

    /** Persist a draft: identity-store answers go to the identity table, everything else to the visit row. */
    suspend fun saveDraft(visitUuid: String, engine: CrfEngine, answers: Map<String, JsonElement>, screenLog: JsonElement, currentScreen: String) {
        val old = db.visits().get(visitUuid) ?: return
        val identityIds = engine.questions.filterValues { str(it.second["store"]) == "identity" }.keys
        val crfPart = JsonObject(answers.filterKeys { it !in identityIds })
        val pid = str(answers["study_id"])
        db.visits().upsert(old.copy(pid = pid, answersJson = CrfJson.encodeToString(JsonObject.serializer(), crfPart),
            screenLogJson = CrfJson.encodeToString(JsonElement.serializer(), screenLog), currentScreen = currentScreen, updatedAt = now()))
        if (answers.keys.any { it in identityIds }) {
            db.identity().upsert(IdentityEntity(visitUuid, pid, str(answers["name"]), str(answers["hospital_reg_no"]), str(answers["phone"])))
        }
    }

    /** Answers to resume a draft: visit answers plus the identity answers kept on the tablet. */
    suspend fun loadAnswers(visitUuid: String): Map<String, JsonElement> {
        val v = db.visits().get(visitUuid) ?: return emptyMap()
        val out = LinkedHashMap<String, JsonElement>(CrfJson.parseToJsonElement(v.answersJson).jsonObject)
        db.identity().get(visitUuid)?.let { i ->
            i.name?.let { out["name"] = JsonPrimitive(it) }
            i.hospitalRegNo?.let { out["hospital_reg_no"] = JsonPrimitive(it) }
            i.phone?.let { out["phone"] = JsonPrimitive(it) }
        }
        return out
    }

    /** Freeze the export and queue the visit for upload. */
    suspend fun submit(visitUuid: String, status: String, crf: JsonObject, screenFailReason: String?) {
        val old = db.visits().get(visitUuid) ?: return
        val t = now()
        db.visits().upsert(old.copy(status = status, crfJson = CrfJson.encodeToString(JsonObject.serializer(), crf), submittedAt = t,
            updatedAt = t, screenFailReason = screenFailReason, syncState = "pending", syncError = null, pid = str(crf["study_id"]) ?: old.pid))
    }

    /** Re-open a submitted visit for correction (for example after a duplicate-PID rejection). */
    suspend fun reopen(visitUuid: String) {
        val old = db.visits().get(visitUuid) ?: return
        db.visits().upsert(old.copy(status = "draft", syncState = "local", syncError = null, updatedAt = now()))
    }

    suspend fun deleteDraft(visitUuid: String) {
        db.visits().deleteDraft(visitUuid)
        db.identity().delete(visitUuid)
    }

    suspend fun pending(): List<VisitEntity> = db.visits().pending()

    /** Record an upload outcome, unless the visit was reopened or edited while the upload ran (then it stays as edited). */
    suspend fun markSync(v: VisitEntity, state: String, error: String?, identitySynced: Boolean = v.identitySynced) {
        val cur = db.visits().get(v.visitUuid) ?: return
        if (cur.updatedAt != v.updatedAt || cur.status != v.status) return
        db.visits().upsert(cur.copy(syncState = state, syncError = error, identitySynced = identitySynced))
    }

    suspend fun purgeIdentity(visitUuid: String) = db.identity().delete(visitUuid)
}
