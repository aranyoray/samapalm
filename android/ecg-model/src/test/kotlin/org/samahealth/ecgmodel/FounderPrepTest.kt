package org.samahealth.ecgmodel

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The Kotlin preprocessing must reproduce palmppg/ecg/founder_prep.py sample for sample, or the phone would feed
 * the model something the laptop never saw. configs/founder_fixtures/preprocess.json holds the reference.
 */
class FounderPrepTest {

    private val dir = File(
        System.getProperty("founder.fixtures")
            ?: error("set -Dfounder.fixtures=<repo>/configs/founder_fixtures"),
    )
    private val fx = Json { ignoreUnknownKeys = true }
        .parseToJsonElement(dir.resolve("preprocess.json").readText()).jsonObject
    private val cases = fx["cases"]!!.jsonArray.map { it.jsonObject }

    /** The fixtures store float32, so the port is checked to the precision the model actually receives. */
    private fun f32(b64: String): DoubleArray {
        val raw = Base64.getDecoder().decode(b64)
        val bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        return DoubleArray(raw.size / 4) { bb.getFloat(it * 4).toDouble() }
    }

    private fun worst(want: DoubleArray, got: DoubleArray): Double {
        assertEquals(want.size, got.size, "length")
        var w = 0.0
        for (i in want.indices) w = maxOf(w, abs(want[i] - got[i]))
        return w
    }

    private fun str(o: JsonObject, k: String) = o[k]!!.jsonPrimitive.content

    @Test
    fun theFilterCoefficientsAreTheOnesThePythonChainUses() {
        val notch = fx["notch"]!!.jsonObject
        val band = fx["bandpass"]!!.jsonObject
        for ((want, got) in listOf(
            notch["b"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() } to FounderPrep.NOTCH_B.toList(),
            notch["a"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() } to FounderPrep.NOTCH_A.toList(),
            band["b"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() } to FounderPrep.BAND_B.toList(),
            band["a"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() } to FounderPrep.BAND_A.toList(),
        )) {
            assertEquals(want.size, got.size)
            for (i in want.indices) {
                assertTrue(abs(want[i] - got[i]) <= 1e-12 * maxOf(1.0, abs(want[i])),
                    "coefficient $i: expected ${want[i]}, got ${got[i]}")
            }
        }
        assertEquals(fx["median_kernel"]!!.jsonPrimitive.content.toInt(), FounderPrep.MEDIAN_KERNEL)
        assertEquals(fx["window_samples"]!!.jsonPrimitive.content.toInt(), FounderPrep.WIN)
    }

    @Test
    fun theResamplingFilterIsTheSameDesignScipyUses() {
        val want = f32(fx["resample_filter"]!!.jsonObject["taps_f32_b64"]!!.jsonPrimitive.content)
        val got = Dsp.firwinLowpass(101, 1.0 / 5.0).map { it * 5 }.toDoubleArray()
        assertTrue(worst(want, got) < 1e-7, "firwin taps differ by ${worst(want, got)}")
    }

    @Test
    fun resamplingMatchesScipyOnEveryCase() {
        for (c in cases) {
            val name = str(c, "name")
            val x = f32(str(c, "strip_f32_b64"))
            val want = f32(str(c, "resampled_f32_b64"))
            val (got, ud) = FounderPrep.resampleToModel(x, c["fs_in"]!!.jsonPrimitive.content.toDouble())
            val wantUd = c["resample_up_down"]!!.jsonArray.map { it.jsonPrimitive.content.toInt() }
            assertEquals(wantUd, listOf(ud.first, ud.second), "$name up/down")
            assertEquals(want.size, got.size, "$name length")
            // the reference is stored as float32, so this is the precision the model sees
            assertTrue(worst(want, got) < 2e-6, "$name resampled differs by ${worst(want, got)}")
        }
    }

    @Test
    fun threeHundredHertzGivesTheFiveOverThreeRatio() {
        assertEquals(5 to 3, FounderPrep.ratio(500.0 / 300.0))
        assertEquals(1 to 1, FounderPrep.ratio(1.0))
        assertEquals(5 to 2, FounderPrep.ratio(500.0 / 200.0))
    }

    @Test
    fun polarityIsJudgedTheSameWay() {
        for (c in cases) {
            val name = str(c, "name")
            val x = f32(str(c, "strip_f32_b64"))
            val (resampled, _) = FounderPrep.resampleToModel(x, c["fs_in"]!!.jsonPrimitive.content.toDouble())
            val (flip, frac, beats) = FounderPrep.polarityCheck(resampled)
            val want = c["polarity"]!!.jsonObject
            assertEquals(want["flipped"]!!.jsonPrimitive.content.toBooleanStrict(), flip, "$name flipped")
            assertEquals(want["beats"]!!.jsonPrimitive.content.toInt(), beats, "$name beats")
            val wf = want["negative_fraction"]
            if (wf != null && wf.jsonPrimitive.content != "null") {
                assertTrue(abs(wf.jsonPrimitive.content.toDouble() - frac) < 1e-9, "$name negative fraction")
            }
        }
    }

    @Test
    fun anInvertedStripIsFlippedAndACleanOneIsNot() {
        val clean = cases.first { str(it, "name") == "clean_72bpm_30s" }
        val inverted = cases.first { str(it, "name") == "inverted_60bpm_30s" }
        assertTrue(inverted["known"]!!.jsonObject["inverted_input"]!!.jsonPrimitive.content.toBooleanStrict())
        val fs = clean["fs_in"]!!.jsonPrimitive.content.toDouble()
        assertTrue(!FounderPrep.preprocess(f32(str(clean, "strip_f32_b64")), fs).polarityFlipped)
        assertTrue(FounderPrep.preprocess(f32(str(inverted, "strip_f32_b64")), fs).polarityFlipped)
    }

    @Test
    fun theFilteredWindowsMatchScipy() {
        for (c in cases) {
            val name = str(c, "name")
            if (c["n_windows"]!!.jsonPrimitive.content.toInt() == 0) continue
            val want = f32(str(c, "filtered_f32_b64"))
            val x = f32(str(c, "strip_f32_b64"))
            val fs = c["fs_in"]!!.jsonPrimitive.content.toDouble()
            val (res, _) = FounderPrep.resampleToModel(x, fs)
            val (flip, _, _) = FounderPrep.polarityCheck(res)
            val signed = if (flip) DoubleArray(res.size) { -res[it] } else res
            val starts = c["window_starts_s"]!!.jsonArray.map {
                (it.jsonPrimitive.content.toDouble() * FounderPrep.FS_MODEL).toInt()
            }
            val got = DoubleArray(starts.size * FounderPrep.WIN)
            for ((i, s) in starts.withIndex()) {
                val f = FounderPrep.filterBandpass(signed.copyOfRange(s, s + FounderPrep.WIN))
                System.arraycopy(f, 0, got, i * FounderPrep.WIN, FounderPrep.WIN)
            }
            assertTrue(worst(want, got) < 5e-6, "$name filtered differs by ${worst(want, got)}")
        }
    }

    @Test
    fun theModelInputMatchesThePythonRunnerSampleForSample() {
        for (c in cases) {
            val name = str(c, "name")
            val x = f32(str(c, "strip_f32_b64"))
            val fs = c["fs_in"]!!.jsonPrimitive.content.toDouble()
            val w = FounderPrep.preprocess(x, fs)
            assertEquals(c["n_windows"]!!.jsonPrimitive.content.toInt(), w.n, "$name window count")
            val wantStarts = c["window_starts_s"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() }
            assertEquals(wantStarts, w.startsS, "$name window starts")
            val want = f32(str(c, "model_input_f32_b64"))
            val got = w.toFloatArray().map { it.toDouble() }.toDoubleArray()
            assertEquals(want.size, got.size, "$name tensor size")
            // z-scored windows are order 1, so this is a few float32 ulps
            assertTrue(worst(want, got) < 1e-4, "$name model input differs by ${worst(want, got)}")
        }
    }

    @Test
    fun aStripShorterThanTenSecondsGivesNoWindow() {
        val c = cases.first { str(it, "name") == "short_8s" }
        val w = FounderPrep.preprocess(f32(str(c, "strip_f32_b64")), c["fs_in"]!!.jsonPrimitive.content.toDouble())
        assertEquals(0, w.n)
        assertTrue(w.notes.any { "shorter than 10 s" in it }, w.notes.toString())
        assertEquals(0, w.toFloatArray().size)
    }

    @Test
    fun everyWindowIsZeroMeanAndUnitScale() {
        val c = cases.first { str(it, "name") == "clean_72bpm_30s" }
        val w = FounderPrep.preprocess(f32(str(c, "strip_f32_b64")), 300.0)
        assertEquals(3, w.n, "30 s gives three non-overlapping 10 s windows")
        for (win in w.windows) {
            assertTrue(abs(Dsp.mean(win)) < 1e-9, "mean ${Dsp.mean(win)}")
            assertTrue(abs(Dsp.std(win) - 1.0) < 1e-6, "std ${Dsp.std(win)}")
        }
    }

    @Test
    fun theWindowCombinationFollowsTheRuleFixedInAdvance() {
        val wantMax = fx["combine"]!!.jsonObject["max_rule_indices"]!!.jsonArray
            .map { it.jsonPrimitive.content.toInt() }
        assertEquals(wantMax, FounderPrep.MAX_RULE_INDICES.toList())
        val probs = arrayOf(
            DoubleArray(150) { 0.1 },
            DoubleArray(150) { 0.9 },
            DoubleArray(150) { 0.2 },
        )
        val c = FounderPrep.combineWindows(probs)
        for (i in 0 until 150) {
            if (i in wantMax) {
                assertEquals(0.9, c[i], 1e-12, "index $i is an ectopy or pause label: max over windows")
            } else {
                assertEquals((0.1 + 0.9 + 0.2) / 3.0, c[i], 1e-12, "index $i: mean over windows")
            }
        }
        assertEquals("max", FounderPrep.combineRule(9))
        assertEquals("mean", FounderPrep.combineRule(5))
        assertEquals(0, FounderPrep.combineWindows(emptyArray()).size)
    }
}
