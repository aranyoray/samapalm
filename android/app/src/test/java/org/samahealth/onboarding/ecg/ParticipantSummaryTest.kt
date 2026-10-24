package org.samahealth.onboarding.ecg

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** The page a participant takes home: what it says, and what it must never say. */
class ParticipantSummaryTest {

    private fun clip(
        hr: Double? = 72.0,
        grade: String? = "good",
        determination: String? = null,
        sentences: List<String> = listOf("Your heart rate was about 72 beats per minute."),
    ): JsonObject {
        val m = LinkedHashMap<String, kotlinx.serialization.json.JsonElement>()
        hr?.let { m["ecg_metrics"] = JsonObject(mapOf("hr_bpm" to JsonPrimitive(it))) }
        grade?.let { m["ecg_grade"] = JsonPrimitive(it) }
        determination?.let { m["kardia_determination"] = JsonPrimitive(it) }
        m["rhythm_sentences"] = JsonArray(sentences.map { JsonPrimitive(it) })
        return JsonObject(m)
    }

    private fun text(o: JsonObject, reviewed: Boolean = false) =
        ParticipantSummary.lines("SW-001", "2026-10-24", o, reviewed).joinToString("\n") { it.first }

    @Test
    fun theHeadingPidDateAndRateAreOnThePage() {
        val t = text(clip())
        assertTrue("Your heart recording (research study)" in t)
        assertTrue("Participant ID: SW-001" in t)
        assertTrue("Date: 2026-10-24" in t)
        assertTrue("About 72 beats per minute" in t, t)
    }

    @Test
    fun aMissingRateSaysSoRatherThanPrintingNothing() {
        val t = text(clip(hr = null))
        assertTrue("could not be measured" in t, t)
    }

    @Test
    fun theDisclaimerAndTheReviewStatusAreAlwaysThere() {
        val notYet = text(clip(), reviewed = false)
        assertTrue("This is not a medical result" in notYet)
        assertTrue("has not looked at this recording yet" in notYet, notYet)
        val done = text(clip(), reviewed = true)
        assertTrue("A study doctor has looked at this recording." in done, done)
        assertTrue("This is not a medical result" in done)
    }

    @Test
    fun theKardiaResultIsLabelledAsTheDevicesOwn() {
        val t = text(clip(determination = "af"))
        assertTrue("The Kardia device's own result" in t, t)
        assertTrue("The Kardia app showed:" in t, t)
    }

    @Test
    fun theParticipantPageNeverNamesARhythm() {
        val banned = listOf("fibrillation", "flutter", "tachycardia", "bradycardia", "ectopic", "arrhythmia",
            "normal sinus")
        for (det in listOf("nsr", "af", "bradycardia", "tachycardia", "sinus_pvc", "unreadable", "too_short")) {
            val t = text(clip(determination = det)).lowercase()
            for (w in banned) assertTrue(w !in t, "the summary named a rhythm ($w) for determination $det:\n$t")
        }
    }

    @Test
    fun qualityIsPutInPlainWords() {
        assertEquals("The recording was clear.", ParticipantSummary.qualityWords("good"))
        assertTrue("not perfectly clear" in ParticipantSummary.qualityWords("borderline"))
        assertTrue("not clear enough" in ParticipantSummary.qualityWords("retake"))
        assertTrue("not been checked" in ParticipantSummary.qualityWords(null))
    }

    @Test
    fun theRhythmSentencesFromTheSignalCheckAreCarriedThrough() {
        val t = text(clip(sentences = listOf("A.", "B.", "This is not a medical opinion.")))
        assertTrue("A." in t && "B." in t, t)
    }
}
