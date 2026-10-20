package org.samahealth.crf

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Duration
import java.time.OffsetDateTime
import kotlin.math.abs

/** Derived values shown to the operator and exported (Python `derive`). */
object Derive {
    /** Python round(x, 1): correctly rounded half-even on the exact binary value. */
    fun round1(x: Double): Double = BigDecimal(x).setScale(1, RoundingMode.HALF_EVEN).toDouble()

    fun initials(name: String): String =
        name.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }.take(3).joinToString("") { it.substring(0, 1).uppercase() }

    fun cuffSuggestion(circ: Double?): String? = when {
        circ == null -> null
        circ < 17 -> "below small adult range"
        circ < 22 -> "small adult"
        circ < 32 -> "adult"
        circ < 42 -> "large adult"
        circ <= 52 -> "thigh"
        else -> "above thigh range"
    }

    private fun seconds(a: OffsetDateTime, b: OffsetDateTime): Double = Duration.between(a, b).toMillis() / 1000.0

    fun derive(eff: Map<String, JsonElement>, settings: Map<String, JsonElement>, now: OffsetDateTime): Map<String, JsonElement> {
        val out = LinkedHashMap<String, JsonElement>()
        val h = num(eff["height_cm"])
        val w = num(eff["weight_kg"])
        out["bmi"] = if (h != null && w != null && h > 0) JsonPrimitive(round1(w / ((h / 100.0) * (h / 100.0)))) else JsonNull
        out["cuff_suggestion"] = cuffSuggestion(num(eff["arm_circumference_cm"]))?.let { JsonPrimitive(it) } ?: JsonNull
        val ga = num(eff["gestational_age_weeks"])
        out["trimester"] = if (ga != null) JsonPrimitive(if (ga < 14) 1 else if (ga < 28) 2 else 3) else JsonNull
        val bp1 = eff["bp1"] as? JsonObject
        val bp2 = eff["bp2"] as? JsonObject
        val bp3 = eff["bp3"] as? JsonObject
        val t1 = bp1?.let { parseTs(it["wall_ts"]) }
        val t2 = bp2?.let { parseTs(it["wall_ts"]) }
        out["rest_elapsed_s"] = if (t1 != null) JsonPrimitive(Duration.between(t1, t2 ?: now).toMillis() / 1000) else JsonNull
        val tc = (eff["clip1"] as? JsonObject)?.let { parseTs(it["started_at"]) }
        out["recovery"] = if (t1 != null && tc != null) {
            JsonPrimitive(if (seconds(t1, tc) >= (num(settings["rest_seconds"]) ?: 300.0)) "pass" else "short_rest")
        } else JsonNull
        fun okReading(r: JsonObject?) = r != null && isNum(r["sbp"]) && isNum(r["dbp"])
        val readings = listOf(bp1, bp2, bp3).filter { okReading(it) }.map { it!! }
        out["bracket_flag"] = if (readings.size >= 2) {
            val lim = num(settings["bracket_mmhg"]) ?: 10.0
            JsonPrimitive(listOf("sbp", "dbp").any { k ->
                val xs = readings.map { num(it[k])!! }
                xs.max() - xs.min() > lim
            })
        } else JsonNull
        val later = listOf(bp2, bp3).filter { okReading(it) }.map { it!! }
        out["bp1_outlier"] = if (okReading(bp1) && later.isNotEmpty()) {
            val lim = num(settings["bp1_outlier_mmhg"]) ?: 15.0
            JsonPrimitive(listOf("sbp", "dbp").any { k -> abs(num(bp1!![k])!! - later.map { num(it[k])!! }.average()) > lim })
        } else JsonNull
        val age = num(eff["age"])
        val consent = eff["consent"]
        out["eligible"] = if (consent != null && consent !is JsonNull && age != null) {
            JsonPrimitive(str(consent) == "yes" && age >= 18)
        } else JsonNull
        out["rest_elapsed"] = out["rest_elapsed_s"]!!
        return out
    }

    val KNOWN = setOf("bmi", "cuff_suggestion", "trimester", "rest_elapsed", "rest_elapsed_s", "recovery", "bracket_flag", "bp1_outlier", "eligible")
}
