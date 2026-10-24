package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Duration
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.abs

/** Derived values shown to the operator and exported (Python `derive`). */
object Derive {
    /** Python round(x, 1): correctly rounded half-even on the exact binary value. */
    fun round1(x: Double): Double = BigDecimal(x).setScale(1, RoundingMode.HALF_EVEN).toDouble()

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

    private fun js(s: String?): JsonElement = s?.let { JsonPrimitive(it) } ?: JsonNull

    private fun jb(b: Boolean?): JsonElement = b?.let { JsonPrimitive(it) } ?: JsonNull

    fun derive(eff: Map<String, JsonElement>, settings: Map<String, JsonElement>, now: OffsetDateTime): Map<String, JsonElement> {
        val out = LinkedHashMap<String, JsonElement>()
        val h = num(eff["height_cm"])
        val w = num(eff["weight_kg"])
        out["bmi"] = if (h != null && w != null && h > 0) JsonPrimitive(round1(w / ((h / 100.0) * (h / 100.0)))) else JsonNull
        out["cuff_suggestion"] = js(cuffSuggestion(num(eff["arm_circumference_cm"])))
        val ga = num(eff["gestational_age_weeks"])
        val trimester = if (ga != null) (if (ga < 14) 1 else if (ga < 28) 2 else 3) else null
        out["trimester"] = trimester?.let { JsonPrimitive(it) } ?: JsonNull
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
        // v2 enrol derivations (design section 2.5)
        val grade = anaemiaGrade(num(eff["hb_gdl"]), str(eff["sex"]), str(eff["pregnant"]), trimester)
        val anaemic = grade?.let { it != "none" }
        out["anaemia_grade"] = js(grade)
        out["anaemic"] = jb(anaemic)
        val mcv = num(eff["mcv_fl"])
        val rbc = num(eff["rbc_mill"])
        val mentzer = if (mcv != null && rbc != null && rbc > 0) round1(mcv / rbc) else null
        out["mentzer_index"] = mentzer?.let { JsonPrimitive(it) } ?: JsonNull
        out["mentzer_pattern"] = js(when {
            mentzer == null -> null
            mcv!! >= 80 -> "not_microcytic"
            mentzer < 13 -> "thal_trait_pattern"
            else -> "iron_deficiency_pattern"
        })
        out["hplc_reflex"] = jb(hplcReflex(mcv, num(eff["mch_pg"])))
        val lastTx = parseDate(eff["last_transfusion_date"])
        val days = lastTx?.let { ChronoUnit.DAYS.between(it, now.toLocalDate()) }
        out["days_since_transfusion"] = days?.let { JsonPrimitive(it) } ?: JsonNull
        out["transfusion_30d"] = jb(days?.let { it <= 30 })
        val haem = haemCell(eff, anaemic, num(settings["ferritin_id_cutoff"]) ?: 15.0)
        val dm = dmLabel(eff["conditions"], num(eff["hba1c_pct"]), num(settings["hba1c_dm_cutoff"]) ?: 6.5)
        out["haem_cell"] = js(haem)
        out["dm_label"] = js(dm)
        out["strata"] = strata(eff, haem, dm)?.let { l -> JsonArray(l.map { JsonPrimitive(it) }) } ?: JsonNull
        out["scan_strata"] = scanStrata(eff)?.let { l -> JsonArray(l.map { JsonPrimitive(it) }) } ?: JsonNull
        return out
    }

    /** WHO 2024 haemoglobin cut-offs (g/dL), aged 15 and over: lowest value graded none, mild, moderate. */
    private val HB_CUTOFFS = mapOf(
        "F" to doubleArrayOf(12.0, 11.0, 8.0), "M" to doubleArrayOf(13.0, 11.0, 8.0),
        "pregnant_t13" to doubleArrayOf(11.0, 10.0, 7.0), "pregnant_t2" to doubleArrayOf(10.5, 9.5, 7.0))

    /** none | mild | moderate | severe; pregnant with unknown trimester uses the trimester 1/3 cut-offs. */
    fun anaemiaGrade(hb: Double?, sex: String?, pregnant: String?, trimester: Int?): String? {
        if (hb == null || (sex != "F" && sex != "M")) return null
        val cut = if (sex == "F" && pregnant == "yes") HB_CUTOFFS[if (trimester == 2) "pregnant_t2" else "pregnant_t13"]!! else HB_CUTOFFS[sex]!!
        return when {
            hb >= cut[0] -> "none"
            hb >= cut[1] -> "mild"
            hb >= cut[2] -> "moderate"
            else -> "severe"
        }
    }

    /** True when MCV < 80 fL or MCH < 27 pg; null when both are missing. */
    fun hplcReflex(mcv: Double?, mch: Double?): Boolean? {
        if (mcv == null && mch == null) return null
        return (mcv != null && mcv < 80) || (mch != null && mch < 27)
    }

    private fun conditions(eff: Map<String, JsonElement>): List<String> =
        (eff["conditions"] as? JsonArray)?.mapNotNull { str(it) } ?: emptyList()

    /** Recruitment cell for the haematology strata; the first matching rule wins. */
    fun haemCell(eff: Map<String, JsonElement>, anaemic: Boolean?, ferritinCutoff: Double): String? {
        val conds = conditions(eff)
        val tt = str(eff["thal_type"])
        val hp = str(eff["hplc_result"])
        val fer = num(eff["ferritin_ngml"])
        return when {
            tt in listOf("beta_major_intermedia", "hbe_beta", "hbe_disease") || hp in listOf("beta_major_intermedia", "hbe_beta") -> "thal_disease"
            tt in listOf("beta_trait", "hbe_trait") || hp in listOf("beta_trait", "hbe_trait") -> "thal_trait"
            "thal" in conds -> "thal_unspecified"
            "ida" in conds || (anaemic == true && fer != null && fer < ferritinCutoff) -> "ida"
            anaemic == true || "anaemia_other" in conds -> "anaemia_other"
            anaemic == false -> "non_anaemic"
            else -> null
        }
    }

    /** documented_hba1c | documented | hba1c_only | no_known; null before the conditions are answered. */
    fun dmLabel(conds: JsonElement?, hba1c: Double?, cutoff: Double): String? {
        val arr = conds as? JsonArray ?: return null
        val high = hba1c != null && hba1c >= cutoff
        return if (arr.any { str(it) == "diabetes" }) (if (high) "documented_hba1c" else "documented") else (if (high) "hba1c_only" else "no_known")
    }

    fun mstGroup(band: Int): String = if (band <= 4) "light" else if (band <= 6) "medium" else "dark"

    /** Recruitment strata keys of an enrol record in the contract order (design section 2.5); null when empty. */
    fun strata(eff: Map<String, JsonElement>, haem: String?, dm: String?): List<String>? {
        val sex = str(eff["sex"])?.takeIf { it.isNotBlank() }
        val band = eff["mst_band"]?.takeIf { isInt(it) }?.let { num(it)!! }?.takeIf { it in 1.0..10.0 }?.toInt()
        val grp = band?.let { mstGroup(it) }
        val have = conditions(eff)
        val ticked = CONDITION_ORDER.filter { it in have }
        val out = ArrayList<String>()
        if (sex != null) out.add("sex:$sex")
        if (band != null) { out.add("mst:$band"); out.add("mstgrp:$grp") }
        ticked.forEach { out.add("cond:$it") }
        if (haem != null) out.add("haem:$haem")
        if (dm != null) out.add("dm:$dm")
        if (str(eff["pregnant"]) == "yes") out.add("preg:yes")
        if (sex != null && band != null) out.add("sex_mst:$sex:$band")
        if (band != null) ticked.filter { it != "none" }.forEach { out.add("cond_mstgrp:$it:$grp") }
        if (haem != null && band != null) out.add("haem_mstgrp:$haem:$grp")
        return out.ifEmpty { null }
    }

    private fun kardia(clip: JsonElement?): String? = str((clip as? JsonObject)?.get("kardia_determination"))?.takeIf { it.isNotBlank() }

    /** rhythm:<Kardia determination> of clip1b (when present with a determination) else clip1, then scan:done. */
    fun scanStrata(eff: Map<String, JsonElement>): List<String>? {
        val out = ArrayList<String>()
        (kardia(eff["clip1b"]) ?: kardia(eff["clip1"]))?.let { out.add("rhythm:$it") }
        if (answered(eff["bp3"])) out.add("scan:done")
        return out.ifEmpty { null }
    }

    /** Order of the `conditions` choice list; cond:* strata keys follow it (the schema lint checks they agree). */
    val CONDITION_ORDER = listOf("htn", "af", "arrhythmia_other", "heart_other", "diabetes", "thal", "ida", "anaemia_other", "ckd", "none")

    val KNOWN = setOf(
        "bmi", "cuff_suggestion", "trimester", "rest_elapsed", "rest_elapsed_s", "recovery", "bracket_flag", "bp1_outlier",
        "eligible", "anaemic", "anaemia_grade", "mentzer_index", "mentzer_pattern", "hplc_reflex", "days_since_transfusion",
        "transfusion_30d", "haem_cell", "dm_label", "strata", "scan_strata")
}
