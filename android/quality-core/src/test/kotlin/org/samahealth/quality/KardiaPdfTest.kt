package org.samahealth.quality

import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * The Kotlin PDF reader must recover the same trace as the Python one from the synthetic Kardia-style export
 * (configs/quality_fixtures/kardia_synthetic.pdf), whose samples are known: they are the `clean_75bpm` ECG case.
 */
class KardiaPdfTest {

    private val fx = Fixtures.load("kardia_pdf.json")
    private val expected = fx["expected"]!!.jsonObject
    private val pdf = Fixtures.dir.resolve(fx["pdf"].str()!!).readBytes()

    @Test
    fun recoversEverySampleAndThePageFields() {
        val tr = KardiaPdf.extract(pdf)
        assertEquals(expected["n"].dbl()!!.toInt(), tr.mv.size, "sample count")
        assertEquals(9000, tr.mv.size, "30 s at 300 Hz")
        assertEquals(expected["fs"].dbl(), tr.fs, "sample rate")
        assertEquals(expected["determination"].str(), tr.determination, "determination")
        assertEquals(expected["hr_bpm"].dbl()!!.toInt(), tr.hrBpm, "heart rate")
        assertEquals(expected["mains_hz"].dbl()!!.toInt(), tr.mainsHz, "mains")
        assertEquals(expected["enhanced_filter"].bool(), tr.enhancedFilter, "filter")
        assertEquals(expected["warnings"]!!.jsonArray.strings(), tr.warnings, "warnings")
    }

    @Test
    fun theSamplesMatchThePythonReaderAndTheTraceItWasDrawnFrom() {
        val tr = KardiaPdf.extract(pdf)
        val first = expected["first_mv"]!!.jsonArray.map { it.dbl()!! }
        for ((i, want) in first.withIndex()) assertClose(want, tr.mv[i], 1e-12, "sample $i")

        // the PDF was drawn from this ECG case, so the vector trace must come back within the stated error
        val truthCase = Fixtures.cases("ecg_cases.json").first { it["name"].str() == fx["truth_case"].str() }
        val (truth, _) = EcgCsv.parseLead1Mv(Fixtures.gunzipB64(truthCase["csv_gz_b64"].str()!!))
        var worst = 0.0
        for (i in tr.mv.indices) worst = maxOf(worst, abs(tr.mv[i] - truth[i]))
        assertTrue(worst <= fx["max_abs_err_mv"].dbl()!!, "vector trace off by $worst mV")
    }

    @Test
    fun theRecoveredTraceGradesTheSameAsTheSamples() {
        val tr = KardiaPdf.extract(pdf)
        val g = EcgQuality.score(tr.mv, tr.fs)
        val want = expected["grade"]!!.jsonObject
        assertEquals(want["level"].str(), g.level, "level")
        assertEquals(want["reasons"]!!.jsonArray.strings(), g.reasons, "reasons")
        assertTrue(abs(g.metrics["hr_bpm"]!! - 75.0) < 1.0, "heart rate ${g.metrics["hr_bpm"]}")
        assertEquals(37.0, g.metrics["n_beats"], "beat count")
    }

    @Test
    fun rubbishIsRejectedRatherThanGuessed() {
        assertFailsWith<IllegalArgumentException> { KardiaPdf.extract("not a pdf at all".toByteArray()) }
        val empty = ("%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" +
            "2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n").toByteArray(Charsets.ISO_8859_1)
        assertFailsWith<IllegalArgumentException> { KardiaPdf.extract(empty) }
    }
}
