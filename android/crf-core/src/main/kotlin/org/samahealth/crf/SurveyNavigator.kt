package org.samahealth.crf

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** One screen visit in the CRF `screen_log`. */
data class ScreenVisit(val screen: String, val enteredAt: String, var leftAt: String? = null)

/**
 * Screen-by-screen navigation over the visible flow. Moving forward requires the current screen to have no errors;
 * moving back is always allowed. A stop condition (no consent, under 18) ends the flow as a screen failure.
 * The UI holds one navigator per participant and persists `answers` and `screenLog` after every change.
 */
class SurveyNavigator(
    val engine: CrfEngine,
    initial: Map<String, JsonElement> = engine.initialAnswers(),
    private val clock: () -> OffsetDateTime = { OffsetDateTime.now(ZoneId.systemDefault()) },
) {
    val answers: MutableMap<String, JsonElement> = LinkedHashMap(initial)
    val screenLog: MutableList<ScreenVisit> = ArrayList()
    var current: String = engine.flow().first()
        private set

    init { enter(current) }

    fun evaluation(): Evaluation = engine.evaluate(answers, clock())

    fun set(id: String, value: JsonElement?) {
        if (value == null || value is JsonNull) answers.remove(id) else answers[id] = value
    }

    fun visibleScreens(): List<String> = evaluation().visibleScreens

    fun canAdvance(): Boolean {
        val ev = evaluation()
        return ev.errorsOn(current).isEmpty()
    }

    /** Move to the next visible screen; returns false (and stays) when the current screen has errors or is last. */
    fun next(): Boolean {
        val ev = evaluation()
        if (ev.errorsOn(current).isNotEmpty()) return false
        val target = neighbour(ev.visibleScreens, forward = true) ?: return false
        leave(); current = target; enter(current)
        return true
    }

    fun back(): Boolean {
        val target = neighbour(visibleScreens(), forward = false) ?: return false
        leave(); current = target; enter(current)
        return true
    }

    /** Next or previous visible screen by flow position, so it still works when an answer hid the current screen. */
    private fun neighbour(visible: List<String>, forward: Boolean): String? {
        val order = engine.flow()
        val pos = order.indexOf(current)
        val candidates = visible.filter { s -> order.indexOf(s).let { if (forward) it > pos else it < pos } }
        return if (forward) candidates.firstOrNull() else candidates.lastOrNull()
    }

    /** Jump to an earlier visible screen (review screen "edit" links). */
    fun goTo(screen: String): Boolean {
        val vis = visibleScreens()
        if (screen !in vis || vis.indexOf(screen) > vis.indexOf(current)) return false
        leave(); current = screen; enter(current)
        return true
    }

    /** Resume a saved draft on the screen the operator left (if it is still visible); earlier screen visits are kept. */
    fun resume(screen: String, previousLog: List<ScreenVisit> = emptyList()): Boolean {
        screenLog.clear()
        screenLog.addAll(previousLog)
        screenLog.lastOrNull()?.let { if (it.leftAt == null) it.leftAt = stamp() }
        val target = if (screen in visibleScreens()) screen else current
        current = target
        enter(current)
        return target == screen
    }

    fun isLast(): Boolean = neighbour(visibleScreens(), forward = true) == null

    fun stopped(): Issue? = evaluation().stopped

    /** Submittable when every visible screen is clean; a stopped flow is submittable only as a screen failure. */
    fun submissionStatus(): String? {
        val ev = evaluation()
        if (ev.stopped != null) return "screen_fail"
        return if (ev.errors.isEmpty()) "submitted" else null
    }

    fun screenLogJson(): JsonElement = jsonOf(screenLog.map { mapOf("screen" to it.screen, "entered_at" to it.enteredAt, "left_at" to it.leftAt) })

    fun export(context: Map<String, JsonElement>): Exported {
        val ctx = LinkedHashMap(context)
        ctx["screen_log"] = screenLogJson()
        return engine.export(answers, ctx, now = clock())
    }

    private fun stamp(): String = clock().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)

    private fun enter(screen: String) { screenLog.add(ScreenVisit(screen, stamp())) }

    private fun leave() { screenLog.lastOrNull()?.let { if (it.leftAt == null) it.leftAt = stamp() } }

    companion object {
        fun nowIso(clock: OffsetDateTime = OffsetDateTime.now(ZoneId.systemDefault())): JsonPrimitive =
            JsonPrimitive(clock.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME))

        /** Parse a stored `screen_log` back into visits (for resuming a draft). */
        fun parseLog(json: JsonElement?): List<ScreenVisit> = (json as? kotlinx.serialization.json.JsonArray)?.mapNotNull { e ->
            val o = e as? JsonObject ?: return@mapNotNull null
            val sc = str(o["screen"]) ?: return@mapNotNull null
            ScreenVisit(sc, str(o["entered_at"]) ?: "", str(o["left_at"]))
        } ?: emptyList()

        fun bp(sbp: Int, dbp: Int, hr: Int, wallTs: String): JsonObject = JsonObject(mapOf(
            "sbp" to JsonPrimitive(sbp), "dbp" to JsonPrimitive(dbp), "hr" to JsonPrimitive(hr), "wall_ts" to JsonPrimitive(wallTs)))
    }
}
