package org.samahealth.onboarding.ui

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The operator's ECG readout. The grade alone was all the app used to show, which is what sent someone
 * looking for the heart rate and finding nothing.
 */
class EcgReadoutTest {

    private fun metrics(json: String): JsonObject = Json.parseToJsonElement(json).jsonObject

    private val good = metrics(
        """{"hr_bpm": 72.4, "n_beats": 74.0, "duration_s": 60.0,
            "template_corr": 0.962, "ksqi": 11.23, "flat_frac": 0.0, "inverted": 0.0}""",
    )

    @Test
    fun `the rate, the beats and the confidence all appear`() {
        val lines = EcgReadout.lines(good, "good")
        assertEquals("Measured here: 72 bpm from 74 beats in 60 s", lines[0])
        assertEquals(
            "Confidence in that number: high (beat shape match 0.96, baseline kurtosis 11.2, flat 0%)",
            lines[1],
        )
    }

    @Test
    fun `the grade is restated as confidence, never as a rhythm`() {
        assertEquals("high", EcgReadout.confidence("good"))
        assertEquals("moderate", EcgReadout.confidence("borderline"))
        assertEquals("low", EcgReadout.confidence("retake"))
        assertEquals(null, EcgReadout.confidence(null))
        val lines = EcgReadout.lines(good, "retake")
        assertTrue(lines.any { it.startsWith("Confidence in that number: low") })
        // nothing in the readout may name a rhythm on its own account
        val named = listOf("fibrillation", "flutter", "tachycardia", "bradycardia", "normal sinus")
        for (l in lines) for (w in named) assertTrue("$l must not say $w", !l.lowercase().contains(w))
    }

    @Test
    fun `the Kardia device reading leads, as the device's own word`() {
        val lines = EcgReadout.lines(good, "good", deviceDetermination = "Normal Sinus Rhythm", deviceHrBpm = 75)
        assertEquals("Kardia device reading: Normal Sinus Rhythm, 75 bpm", lines[0])
        assertTrue(lines[1].startsWith("Measured here: 72 bpm"))
    }

    @Test
    fun `a device reading with no rate, and a rate with no determination`() {
        assertEquals(
            "Kardia device reading: 75 bpm",
            EcgReadout.lines(good, "good", deviceHrBpm = 75)[0],
        )
        assertEquals(
            "Kardia device reading: Normal Sinus Rhythm",
            EcgReadout.lines(good, "good", deviceDetermination = "Normal Sinus Rhythm")[0],
        )
    }

    @Test
    fun `an inverted trace is called out`() {
        val inv = metrics("""{"hr_bpm": 64.0, "n_beats": 64.0, "duration_s": 60.0, "inverted": 1.0}""")
        assertTrue(EcgReadout.lines(inv, "good").any { it.startsWith("The trace reads upside down") })
        assertTrue(EcgReadout.lines(good, "good").none { it.startsWith("The trace reads upside down") })
    }

    @Test
    fun `the participant sentences come last and are passed through unchanged`() {
        val sentences = Json.parseToJsonElement("""["The beats were evenly spaced.", "Not a medical opinion."]""")
        val lines = EcgReadout.lines(good, "good", rhythmSentences = sentences)
        assertEquals("The beats were evenly spaced.", lines[lines.size - 2])
        assertEquals("Not a medical opinion.", lines.last())
    }

    @Test
    fun `nothing measured means nothing claimed`() {
        assertEquals(emptyList<String>(), EcgReadout.lines(null, null))
        assertEquals(emptyList<String>(), EcgReadout.lines(metrics("{}"), "good"))
        // a grade with no numbers under it must not produce a bare confidence line
        assertTrue(EcgReadout.lines(metrics("""{"ksqi": 9.0}"""), "good").none { it.startsWith("Confidence") })
    }

    @Test
    fun `missing metrics are left out rather than printed as null`() {
        val sparse = metrics("""{"hr_bpm": 80.0, "n_beats": 80.0}""")
        val lines = EcgReadout.lines(sparse, "borderline")
        assertEquals("Measured here: 80 bpm from 80 beats", lines[0])
        assertEquals("Confidence in that number: moderate", lines[1])
        for (l in lines) assertTrue(l, !l.contains("null"))
    }
}
