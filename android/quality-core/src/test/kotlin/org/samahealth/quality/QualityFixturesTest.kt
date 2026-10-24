package org.samahealth.quality

import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * The Kotlin scorers must reproduce the Python reference (palmppg/quality/onsite.py) on every shared fixture:
 * the same grade, the same reasons word for word, and the same metrics to [TOL] relative.
 */
class QualityFixturesTest {

    private companion object {
        /** Both sides run the same operations in double precision; the gap is accumulated rounding only. */
        const val TOL = 1e-9
    }

    @Test
    fun videoCasesMatchThePythonReference() {
        val cases = Fixtures.cases("video_cases.json")
        assertTrue(cases.size >= 9, "expected the full video fixture set, got ${cases.size}")
        val failures = ArrayList<String>()
        for (c in cases) {
            val name = c["name"].str()!!
            try {
                val roi = RoiCsv.parse(Fixtures.gunzipB64(c["roi_csv_gz_b64"].str()!!))
                val frames = c["frames_csv_gz_b64"].str()?.let { FramesCsv.parseTimesS(Fixtures.gunzipB64(it)) }
                val g = VideoQuality.score(roi, frames, c["expected_seconds"].dbl()!!, c["ref_hr_bpm"].dbl())
                val exp = c["expected"]!!.jsonObject
                assertEquals(exp["level"].str(), g.level, "$name level")
                assertEquals(exp["reasons"]!!.jsonArray.strings(), g.reasons, "$name reasons")
                assertMetrics(exp["metrics"]!!.jsonObject, g.metrics, TOL, name)
            } catch (e: AssertionError) {
                failures.add(e.message ?: name)
            }
        }
        if (failures.isNotEmpty()) fail(failures.joinToString("\n"))
    }

    @Test
    fun videoCasesMeetTheirKnownAnswers() {
        for (c in Fixtures.cases("video_cases.json")) {
            val name = c["name"].str()!!
            val roi = RoiCsv.parse(Fixtures.gunzipB64(c["roi_csv_gz_b64"].str()!!))
            val frames = c["frames_csv_gz_b64"].str()?.let { FramesCsv.parseTimesS(Fixtures.gunzipB64(it)) }
            val g = VideoQuality.score(roi, frames, c["expected_seconds"].dbl()!!, c["ref_hr_bpm"].dbl())
            val known = c["known"]!!.jsonObject
            assertEquals(known["level"].str(), g.level, "$name level")
            known["reason_prefix"].str()?.let { pre ->
                assertTrue(g.reasons.any { it.startsWith(pre) }, "$name: no reason starting '$pre' in ${g.reasons}")
            }
            for ((key, tol) in listOf("pulse_bpm" to 1.5, "duration_s" to 0.2, "dropped_frac" to 0.01,
                "dark_frac" to 0.05, "clipped_frac" to 0.02)) {
                val want = known[key].dbl() ?: continue
                val got = g.metrics[key] ?: fail("$name.$key is missing")
                assertTrue(abs(got - want) <= tol, "$name.$key: expected ~$want, got $got")
            }
        }
    }

    @Test
    fun ecgCasesFromAtcMatchThePythonReference() {
        val cases = Fixtures.cases("ecg_cases.json")
        assertTrue(cases.size >= 7, "expected the full ECG fixture set, got ${cases.size}")
        val failures = ArrayList<String>()
        for (c in cases) {
            val name = c["name"].str()!!
            try {
                val tr = AtcReader.read(Fixtures.b64(c["atc_b64"].str()!!))
                assertEquals(300.0, tr.fs, "$name fs")
                val g = EcgQuality.score(tr.mv, tr.fs)
                val exp = c["expected"]!!.jsonObject
                assertEquals(exp["level"].str(), g.level, "$name level")
                assertEquals(exp["reasons"]!!.jsonArray.strings(), g.reasons, "$name reasons")
                assertMetrics(exp["metrics"]!!.jsonObject, g.metrics, TOL, name)

                val s = EcgSummary.summarise(tr.mv, tr.fs)
                val want = c["summary"]!!.jsonObject
                assertEquals(want["rhythm"].str(), s.rhythm, "$name rhythm")
                assertEquals(want["inverted"].bool(), s.inverted, "$name inverted")
                assertEquals(want["n_beats"].dbl()!!.toInt(), s.nBeats, "$name n_beats")
                assertEquals(want["irregular_flag"].bool(), s.irregularFlag, "$name irregular_flag")
                assertEquals(want["sentences"]!!.jsonArray.strings(), s.sentences, "$name sentences")
                val hr = want["hr_bpm"].dbl()
                if (hr == null) assertEquals(null, s.hrBpm, "$name summary hr") else assertClose(hr, s.hrBpm!!, TOL, "$name summary hr")
            } catch (e: AssertionError) {
                failures.add(e.message ?: name)
            }
        }
        if (failures.isNotEmpty()) fail(failures.joinToString("\n"))
    }

    @Test
    fun ecgCasesMeetTheirKnownAnswers() {
        for (c in Fixtures.cases("ecg_cases.json")) {
            val name = c["name"].str()!!
            val tr = AtcReader.read(Fixtures.b64(c["atc_b64"].str()!!))
            val g = EcgQuality.score(tr.mv, tr.fs)
            val known = c["known"]!!.jsonObject
            assertEquals(known["level"].str(), g.level, "$name level")
            known["hr_bpm"].dbl()?.let { assertTrue(abs(g.metrics["hr_bpm"]!! - it) <= 1.0, "$name hr") }
            known["n_beats"].dbl()?.let { assertEquals(it, g.metrics["n_beats"], "$name n_beats") }
            known["flat_frac"].dbl()?.let { assertTrue(abs(g.metrics["flat_frac"]!! - it) <= 0.05, "$name flat") }
            known["rr_max_s"].dbl()?.let { assertTrue(abs(g.metrics["rr_max_s"]!! - it) <= 0.05, "$name rr_max") }
            if (known["irregular"].bool() == true) {
                assertEquals(1.0, g.metrics["irregular_flag"], "$name irregular_flag")
            }
            known["rr_ratio_over"].dbl()?.let {
                // an irregular record turns the RR-ratio rule off, so a high ratio does not lower the grade
                assertTrue(g.metrics["rr_ratio"]!! > it, "$name rr_ratio")
                assertEquals("good", g.level, "$name level with the RR-ratio rule off")
            }
            known["reason_prefix"].str()?.let { pre ->
                assertTrue(g.reasons.any { it.startsWith(pre) }, "$name: no reason starting '$pre' in ${g.reasons}")
            }
            assertEquals(known["rhythm"].str(), EcgSummary.summarise(tr.mv, tr.fs).rhythm, "$name rhythm")
        }
    }

    @Test
    fun ecgCasesFromTheSamplesCsvMatchThePythonReference() {
        val cases = Fixtures.cases("ecg_cases.json").filter { it["csv_gz_b64"] != null }
        assertTrue(cases.isNotEmpty(), "no fixture carries a samples CSV")
        for (c in cases) {
            val name = c["name"].str()!!
            val (mv, fs) = EcgCsv.parseLead1Mv(Fixtures.gunzipB64(c["csv_gz_b64"].str()!!))
            val exp = c["csv_expected"]!!.jsonObject
            assertEquals(exp["n"].dbl()!!.toInt(), mv.size, "$name n")
            assertClose(exp["fs"].dbl()!!, fs, 1e-12, "$name fs")
            val g = EcgQuality.score(mv, fs)
            assertEquals(exp["level"].str(), g.level, "$name level")
            assertEquals(exp["reasons"]!!.jsonArray.strings(), g.reasons, "$name reasons")
            assertMetrics(exp["metrics"]!!.jsonObject, g.metrics, TOL, name)
        }
    }

    @Test
    fun theSummaryNeverNamesARhythmAndAlwaysClosesTheSameWay() {
        val banned = listOf("fibrillation", " af ", "flutter", "tachycardia", "bradycardia", "ectopic",
            "arrhythmia", "normal sinus")
        for (c in Fixtures.cases("ecg_cases.json")) {
            val tr = AtcReader.read(Fixtures.b64(c["atc_b64"].str()!!))
            val s = EcgSummary.summarise(tr.mv, tr.fs)
            assertEquals(RhythmSummary.CLOSING, s.sentences.last(), "closing sentence")
            val text = s.text.lowercase()
            assertTrue("study doctor" in text, "the summary must point at the study doctor")
            for (w in banned) assertTrue(w !in text, "the summary named a rhythm ($w): ${s.text}")
            assertTrue(s.rhythm in setOf("regular", "irregular", "insufficient"), s.rhythm)
        }
    }
}
