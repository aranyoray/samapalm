package org.samahealth.quality

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.roundToInt
import kotlin.math.roundToLong
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Known answers computed independently of the Python reference: signals built here with a heart rate and a beat
 * count that are known by construction, and the readers against hand-written files.
 */
class QualityKnownAnswersTest {

    private val fs = 300.0

    /** Lead-I-like beats at known times: P, QRS and T as Gaussians. Returns the signal and the beat times. */
    private fun synthEcg(
        seconds: Double = 30.0,
        bpm: Double = 75.0,
        start: Double = 0.4,
        rr: DoubleArray? = null,
        invert: Boolean = false,
    ): Pair<DoubleArray, List<Double>> {
        val n = (seconds * fs).roundToInt()
        val times = ArrayList<Double>()
        times.add(start)
        if (rr == null) {
            val step = 60.0 / bpm
            while (times.last() + step < seconds) times.add(times.last() + step)
        } else {
            for (d in rr) {
                if (times.last() + d >= seconds) break
                times.add(times.last() + d)
            }
        }
        val waves = listOf(
            doubleArrayOf(0.12, -0.16, 0.030), doubleArrayOf(-0.10, -0.020, 0.008),
            doubleArrayOf(1.00, 0.0, 0.010), doubleArrayOf(-0.20, 0.025, 0.010),
            doubleArrayOf(0.25, 0.180, 0.050),
        )
        val x = DoubleArray(n)
        for (tb in times) {
            for (w in waves) {
                val mu = tb + w[1]
                val sd = w[2]
                val lo = maxOf(0, ((mu - 6 * sd) * fs).toInt())
                val hi = minOf(n, ((mu + 6 * sd) * fs).toInt() + 1)
                for (i in lo until hi) {
                    val d = (i / fs - mu) / sd
                    x[i] += w[0] * exp(-0.5 * d * d)
                }
            }
        }
        if (invert) for (i in x.indices) x[i] = -x[i]
        return x to times
    }

    /** A recorder-format roi.csv whose pulse rate is known exactly. */
    private fun roiText(
        seconds: Double = 20.0,
        fps: Double = 30.0,
        bpm: Double = 72.0,
        ac: Double = 1.0,
        level: Double = 1.0,
        clipFrac: Double = 0.004,
        darkFrom: Double? = null,
    ): String {
        val n = (seconds * fps).roundToInt()
        val dc = doubleArrayOf(180.0, 110.0, 80.0)
        val rel = doubleArrayOf(0.004, 0.010, 0.006)
        val grid = (0..8).joinToString(",") { "g${it / 3}${it % 3}" }
        val sb = StringBuilder("roi_idx,sensor_ts_ns_raw,t_ref_ns,n_px,y_mean,u_mean,v_mean,r_mean,g_mean,b_mean," +
            "clip_frac,$grid\n")
        for (i in 0 until n) {
            val t = i / fps
            val ph = 2.0 * PI * (bpm / 60.0) * t
            val w = sin(ph) + 0.35 * sin(2.0 * ph - 0.8)
            val ch = DoubleArray(3) { k -> dc[k] * level * (1.0 - rel[k] * ac * w) }
            if (darkFrom != null && t >= darkFrom) for (k in 0..2) ch[k] = 2.0
            val y = 0.299 * ch[0] + 0.587 * ch[1] + 0.114 * ch[2]
            val tref = (t * 1e9).roundToLong()
            sb.append("$i,${tref - 1500},$tref,36864,$y,128,128,${ch[0]},${ch[1]},${ch[2]},$clipFrac,")
            sb.append((0..8).joinToString(",") { "$y" }).append('\n')
        }
        return sb.toString()
    }

    // ---- readers
    @Test
    fun roiCsvSortsByTimeAndSkipsRowsItCannotRead() {
        val lines = roiText(seconds = 1.0).trim().lines().toMutableList()
        assertEquals(31, lines.size, "header plus 30 rows")
        val roi = RoiCsv.parse(lines.joinToString("\n"))
        assertEquals(30, roi.tS.size)
        assertEquals(0.0, roi.tS[0])
        assertTrue(abs(roi.tS[29] - 29.0 / 30.0) < 1e-6)
        assertTrue(roi.grid != null && roi.grid!!.size == 9)

        val shuffled = (listOf(lines[0]) + lines.drop(1).reversed()).joinToString("\n")
        assertTrue(RoiCsv.parse(shuffled).tS.contentEquals(roi.tS), "row order must not matter")

        lines[3] = lines[3].replaceFirst(lines[3].split(",")[2], "x")
        lines.add(7, "garbage")
        assertEquals(29, RoiCsv.parse(lines.joinToString("\n")).tS.size, "the two bad rows are dropped")
        assertFailsWith<IllegalArgumentException> { RoiCsv.parse("a,b,c\n1,2,3\n") }
    }

    @Test
    fun framesCsvTimesAreRelativeAndSorted() {
        val t = FramesCsv.parseTimesS("frame_idx,sensor_ts_ns\n2,2000000000\n0,1000000000\n1,1500000000\n")
        assertTrue(t.contentEquals(doubleArrayOf(0.0, 0.5, 1.0)))
        assertEquals(0, FramesCsv.parseTimesS("").size)
    }

    @Test
    fun ecgCsvRecoversTheSampleRateFromTheTimestamps() {
        val sb = StringBuilder("idx,t_ref_ns,lead1_mv\n")
        for (i in 0 until 600) sb.append("$i,${(i * 1e9 / 300).toLong()},${i / 1000.0}\n")
        val (mv, rate) = EcgCsv.parseLead1Mv(sb.toString())
        assertEquals(600, mv.size)
        assertTrue(abs(rate - 300.0) < 0.01, "fs $rate")
        assertTrue(abs(mv[599] - 0.599) < 1e-9)
    }

    @Test
    fun atcDamageBecomesAWarningNotAnException() {
        val good = Fixtures.b64(Fixtures.cases("ecg_cases.json").first()["atc_b64"].str()!!)
        val tr = AtcReader.read(good)
        assertEquals(9000, tr.mv.size)
        assertTrue(tr.warnings.isEmpty(), "a clean file has no warnings: ${tr.warnings}")
        val damaged = good.copyOf()
        damaged[damaged.size - 40] = (damaged[damaged.size - 40].toInt() xor 0xFF).toByte()
        val bad = AtcReader.read(damaged)
        assertTrue(bad.mv.isNotEmpty() && bad.warnings.any { "crc" in it }, bad.warnings.toString())
        assertFailsWith<IllegalArgumentException> { AtcReader.read("NOTATC".toByteArray() + ByteArray(40)) }
    }

    // ---- video
    @Test
    fun aCleanClipRecoversTheKnownPulseRate() {
        val g = VideoQuality.score(RoiCsv.parse(roiText(seconds = 20.0, bpm = 72.0)), null, 20.0)
        assertEquals("good", g.level, g.reasons.toString())
        assertTrue(g.reasons.isEmpty())
        assertTrue(abs(g.metrics["pulse_bpm"]!! - 72.0) < 1.0, "pulse ${g.metrics["pulse_bpm"]}")
        assertTrue(g.metrics["snr_db"]!! > 5.0, "snr ${g.metrics["snr_db"]}")
        assertTrue(abs(g.metrics["duration_s"]!! - 20.0) < 0.1)
        assertEquals(0.0, g.metrics["dark_frac"])
    }

    @Test
    fun aClipShorterThanNineTenthsOfTheLengthAskedForIsARetake() {
        val roi = RoiCsv.parse(roiText(seconds = 12.0, bpm = 72.0))
        val short = VideoQuality.score(roi, null, 20.0)
        assertEquals("retake", short.level)
        assertTrue(short.reasons[0].startsWith("Clip too short"), short.reasons.toString())
        assertEquals("good", VideoQuality.score(roi, null, 13.0).level, "12 s of 13 s is above 0.9")
    }

    @Test
    fun darkAndBlackFramesAreCaught() {
        val dark = VideoQuality.score(RoiCsv.parse(roiText(seconds = 20.0, level = 0.02)), null, 20.0)
        assertEquals("retake", dark.level)
        assertTrue(dark.reasons[0].startsWith("Too dark"), dark.reasons.toString())

        val tail = VideoQuality.score(RoiCsv.parse(roiText(seconds = 20.0, darkFrom = 13.0)), null, 20.0)
        assertEquals("retake", tail.level)
        assertTrue(tail.reasons.any { it.startsWith("Dark or black frames") }, tail.reasons.toString())
        assertTrue(abs(tail.metrics["dark_frac"]!! - 0.35) < 0.02, "7 s of 20 s dark")
    }

    @Test
    fun clippingUsesTheDocumentedThresholds() {
        val cfg = VideoQualityConfig()
        assertEquals(0.25, cfg.retakeClippedFrac)
        assertEquals(0.05, cfg.borderlineClippedFrac)
        assertEquals("retake", VideoQuality.score(RoiCsv.parse(roiText(clipFrac = 0.30)), null, 20.0).level)
        val warm = VideoQuality.score(RoiCsv.parse(roiText(clipFrac = 0.10)), null, 20.0)
        assertEquals("borderline", warm.level)
        assertTrue(abs(warm.metrics["clipped_frac"]!! - 0.10) < 1e-6)
    }

    @Test
    fun droppedFramesAreCountedFromTheFrameTimes() {
        val dropped = setOf(100, 200, 300, 400, 500, 550)          // 6 of 600 frames missing
        val times = (0 until 600).filter { it !in dropped }.map { it / 30.0 }.toDoubleArray()
        val g = VideoQuality.score(RoiCsv.parse(roiText(seconds = 20.0)), times, 20.0)
        assertTrue(abs(g.metrics["dropped_frac"]!! - 6.0 / 600.0) < 0.002, "${g.metrics["dropped_frac"]}")
        assertEquals("borderline", g.level)
        assertTrue(g.reasons.any { "dropped frames" in it }, g.reasons.toString())
    }

    @Test
    fun anEmptyRoiFileIsARetakeAndNotACrash() {
        val header = roiText(seconds = 1.0).lines()[0]
        val g = VideoQuality.score(RoiCsv.parse(header + "\n"), null, 20.0)
        assertEquals("retake", g.level)
        assertNull(g.metrics["pulse_bpm"])
    }

    // ---- ECG
    @Test
    fun aCleanEcgRecoversTheKnownRateAndBeatCount() {
        val (mv, times) = synthEcg(seconds = 30.0, bpm = 75.0)
        assertEquals(37, times.size, "0.4 s to 29.2 s every 0.8 s")
        val g = EcgQuality.score(mv, fs)
        assertEquals("good", g.level, g.reasons.toString())
        assertTrue(g.reasons.isEmpty())
        assertTrue(abs(g.metrics["hr_bpm"]!! - 75.0) < 0.5, "hr ${g.metrics["hr_bpm"]}")
        assertEquals(37.0, g.metrics["n_beats"])
        assertTrue(g.metrics["template_corr"]!! > 0.95)
        assertEquals(0.0, g.metrics["flat_frac"])
        assertEquals(0.0, g.metrics["irregular_flag"])
    }

    @Test
    fun qrsDetectionLandsOnTheKnownBeatTimes() {
        val (mv, times) = synthEcg(seconds = 20.0, bpm = 60.0)
        val r = EcgQuality.detectQrs(mv, fs)
        assertEquals(times.size, r.size)
        for (i in r.indices) assertTrue(abs(r[i] / fs - times[i]) < 0.02, "beat $i at ${r[i] / fs} vs ${times[i]}")
    }

    @Test
    fun anInvertedRecordingIsFlaggedAndStillMeasured() {
        val (mv, times) = synthEcg(seconds = 30.0, bpm = 64.0, invert = true)
        val g = EcgQuality.score(mv, fs)
        assertEquals(1.0, g.metrics["inverted"])
        assertTrue(abs(g.metrics["hr_bpm"]!! - 64.0) < 0.5, "hr ${g.metrics["hr_bpm"]}")
        assertEquals(times.size.toDouble(), g.metrics["n_beats"])
        val s = EcgSummary.summarise(mv, fs)
        assertTrue(s.inverted)
        assertEquals("regular", s.rhythm)
    }

    @Test
    fun aFlatRecordingIsARetake() {
        val g = EcgQuality.score(DoubleArray((25 * fs).toInt()), fs)
        assertEquals("retake", g.level)
        assertEquals(1.0, g.metrics["flat_frac"])
        assertEquals(0.0, g.metrics["n_beats"])
        assertTrue(g.reasons.any { "Flat line" in it }, g.reasons.toString())
        assertTrue(g.reasons.any { "Too few beats" in it }, g.reasons.toString())
    }

    @Test
    fun aRecordingUnderTwentySecondsIsARetake() {
        val (mv, _) = synthEcg(seconds = 15.0, bpm = 75.0)
        val g = EcgQuality.score(mv, fs)
        assertEquals("retake", g.level)
        assertTrue(g.reasons[0].startsWith("ECG too short"), g.reasons.toString())
        assertTrue(abs(g.metrics["duration_s"]!! - 15.0) < 1e-9)
    }

    @Test
    fun aLongGapBetweenBeatsIsBorderline() {
        val rr = DoubleArray(33) { if (it == 12) 3.6 else 0.8 }
        val (mv, _) = synthEcg(seconds = 40.0, rr = rr)
        val g = EcgQuality.score(mv, fs)
        assertTrue(g.metrics["rr_max_s"]!! > 3.0, "${g.metrics["rr_max_s"]}")
        assertEquals("borderline", g.level)
        assertTrue(g.reasons.any { "Long gap" in it }, g.reasons.toString())
    }

    @Test
    fun steadyBeatsAreNotFlaggedAsIrregular() {
        val (mv, _) = synthEcg(seconds = 40.0, bpm = 72.0)
        val g = EcgQuality.score(mv, fs)
        assertEquals(0.0, g.metrics["irregular_flag"])
        assertTrue(g.metrics["rmssd_ratio"]!! < 0.1, "${g.metrics["rmssd_ratio"]}")
    }

    @Test
    fun theEcgThresholdsAreTheDocumentedOnes() {
        val cfg = EcgQualityConfig()
        assertEquals(20.0, cfg.minDurationS)
        assertEquals(8, cfg.minBeats)
        assertEquals(0.5, cfg.retakeTemplateCorr)
        assertEquals(0.66, cfg.borderlineTemplateCorr)
        assertEquals(30.0, cfg.retakeHrLo)
        assertEquals(220.0, cfg.retakeHrHi)
        assertEquals(40.0, cfg.borderlineHrLo)
        assertEquals(180.0, cfg.borderlineHrHi)
    }

    @Test
    fun anUnusableRecordingReportsInsufficientAndNoRate() {
        val s = EcgSummary.summarise(DoubleArray((25 * fs).toInt()), fs)
        assertEquals("insufficient", s.rhythm)
        assertNull(s.hrBpm)
        assertEquals(0, s.nBeats)
        assertEquals(RhythmSummary.CLOSING, s.sentences.last())
    }
}
