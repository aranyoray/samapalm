package org.samahealth.onboarding.ui

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.util.Locale

/**
 * The numbers behind an ECG grade, for the operator.
 *
 * A grade on its own ("Borderline") says what to do about the recording but nothing about what was in it, so
 * the rate, the beat count and the two signal-quality numbers the grade is built from are shown beside it.
 *
 * "Confidence" here is the grade restated, and it is confidence in the measurement, not in a diagnosis: it
 * says how well the beats could be picked out, never how normal they were. Naming a rhythm is the study
 * clinician's job (D-037), so nothing here does, and where a Kardia export carries the device's own printed
 * determination that is shown as the device's word rather than folded into ours.
 */
object EcgReadout {

    /** The signal-quality grade as confidence in the numbers measured from it. */
    fun confidence(level: String?): String? = when (level) {
        "good" -> "high"
        "borderline" -> "moderate"
        "retake" -> "low"
        else -> null
    }

    private fun num(e: JsonElement?): Double? =
        (e as? JsonPrimitive)?.takeIf { it !is JsonNull }?.content?.toDoubleOrNull()

    private fun fmt(v: Double, dp: Int) = String.format(Locale.US, "%.${dp}f", v)

    /**
     * One line per thing worth reading, in the order an operator wants them: what the device said, what we
     * measured, how far to trust it, then the participant-facing sentences. Empty when there is nothing
     * measured yet, so a caller can render it unconditionally.
     */
    fun lines(
        metrics: JsonObject?,
        level: String?,
        rhythmSentences: JsonElement? = null,
        deviceDetermination: String? = null,
        deviceHrBpm: Int? = null,
    ): List<String> {
        val out = ArrayList<String>()

        if (deviceDetermination != null || deviceHrBpm != null) {
            val bits = listOfNotNull(deviceDetermination, deviceHrBpm?.let { "$it bpm" })
            out.add("Kardia device reading: " + bits.joinToString(", "))
        }

        val hr = num(metrics?.get("hr_bpm"))
        val beats = num(metrics?.get("n_beats"))
        val dur = num(metrics?.get("duration_s"))
        if (hr != null || beats != null) {
            val rate = if (hr != null) "Measured here: ${fmt(hr, 0)} bpm" else "Measured here: no rate"
            val over = when {
                beats != null && dur != null -> " from ${fmt(beats, 0)} beats in ${fmt(dur, 0)} s"
                beats != null -> " from ${fmt(beats, 0)} beats"
                else -> ""
            }
            out.add(rate + over)
        }

        val conf = confidence(level)
        if (conf != null && (hr != null || beats != null)) {
            val why = ArrayList<String>()
            num(metrics?.get("template_corr"))?.let { why.add("beat shape match ${fmt(it, 2)}") }
            num(metrics?.get("ksqi"))?.let { why.add("baseline kurtosis ${fmt(it, 1)}") }
            num(metrics?.get("flat_frac"))?.let { why.add("flat ${fmt(100.0 * it, 0)}%") }
            out.add(
                "Confidence in that number: $conf" +
                    if (why.isEmpty()) "" else " (" + why.joinToString(", ") + ")"
            )
        }

        if (num(metrics?.get("inverted")) == 1.0) {
            out.add("The trace reads upside down: check the electrodes were the right way round.")
        }

        (rhythmSentences as? JsonArray)?.forEach { s ->
            (s as? JsonPrimitive)?.content?.let { out.add(it) }
        }
        return out
    }
}
