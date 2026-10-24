package org.samahealth.quality

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Palm-clip grade from the pre-encoder ROI trace (`<clip>_roi.csv`) and, when present, the recorded-frame times
 * (`<clip>_frames.csv`). Metrics: duration, fps, dropped frames from frame-time gaps, median Y, median clipped
 * fraction, share of dark rows (the D-033 black-frame failure), motion (median relative change of the 3x3 grid
 * between rows, lit rows only), and the pulse: POS (Wang et al. 2017, 1.6 s windows) on R/G/B resampled to 30 Hz,
 * Hann periodogram, peak in 0.7-3.5 Hz, de Haan & Jeanne (2013) SNR (power within +/-0.1 Hz of f0 and +/-0.2 Hz of
 * 2 f0 over the rest of 0.5-4 Hz; f0 = the reference heart rate when given), perfusion (P95-P5 of the detrended
 * green over its mean) and skewness of the pulse. Thresholds: [VideoQualityConfig] (PROVISIONAL).
 */
object VideoQuality {

    fun score(
        roi: RoiSeries,
        frameTimesS: DoubleArray?,
        expectedSeconds: Double,
        refHrBpm: Double? = null,
        cfg: VideoQualityConfig = VideoQualityConfig(),
    ): Grade {
        val m = metrics(roi, frameTimesS, refHrBpm, cfg)
        val retake = ArrayList<String>()
        val border = ArrayList<String>()
        val dur = m.getValue("duration_s")!!
        if (roi.tS.isEmpty()) retake.add("No video analysis rows were written")
        if (expectedSeconds > 0 && dur < cfg.minDurationFrac * expectedSeconds) {
            retake.add("Clip too short (${fmt(dur, 1)} s of ${fmt(expectedSeconds, 1)} s)")
        }
        val lvl = m["mean_level"]
        val dark = m["dark_frac"]
        if (lvl != null && lvl < cfg.minMeanLevel) {
            retake.add("Too dark (level ${fmt(lvl, 1)}): check the torch and that the palm covers the camera")
        } else if (dark != null && dark > cfg.maxDarkFrac) {
            retake.add("Dark or black frames in ${fmt(100.0 * dark, 0)}% of the clip")
        }
        val clip = m["clipped_frac"]
        if (clip != null && clip > cfg.retakeClippedFrac) {
            retake.add("Overexposed: ${fmt(100.0 * clip, 0)}% of the palm area clipped")
        } else if (clip != null && clip > cfg.borderlineClippedFrac) {
            border.add("Some overexposure: ${fmt(100.0 * clip, 0)}% of the palm area clipped")
        }
        val drop = m["dropped_frac"]
        if (drop != null && drop > cfg.retakeDroppedFrac) {
            retake.add("Many dropped frames (${fmt(100.0 * drop, 1)}%)")
        } else if (drop != null && drop > cfg.borderlineDroppedFrac) {
            border.add("Some dropped frames (${fmt(100.0 * drop, 1)}%)")
        }
        val snr = m["snr_db"]
        if (snr == null) {
            if (roi.tS.isNotEmpty()) retake.add("No pulse signal could be measured")
        } else if (snr < cfg.retakeSnrDb) {
            retake.add("No clear pulse in the video (SNR ${fmt(snr, 1)} dB)")
        } else if (snr < cfg.borderlineSnrDb) {
            border.add("Weak pulse signal (SNR ${fmt(snr, 1)} dB)")
        }
        val mot = m["motion"]
        if (mot != null && mot > cfg.borderlineMotion) {
            border.add("Hand or phone moved (frame-to-frame change ${fmt(100.0 * mot, 1)}%)")
        }
        val pulse = m["pulse_bpm"]
        if (refHrBpm != null && pulse != null && abs(pulse - refHrBpm) > cfg.maxRefHrDiffBpm) {
            border.add("Video pulse ${fmt(pulse, 0)} bpm differs from the reference ${fmt(refHrBpm, 0)} bpm")
        }
        val level = if (retake.isNotEmpty()) "retake" else if (border.isNotEmpty()) "borderline" else "good"
        return Grade(level, retake + border, m)
    }

    private fun metrics(roi: RoiSeries, frameTimesS: DoubleArray?, refHrBpm: Double?, cfg: VideoQualityConfig):
        Map<String, Double?> {
        val out = LinkedHashMap<String, Double?>()
        for (k in listOf("duration_s", "fps", "dropped_frac", "mean_level", "clipped_frac", "dark_frac", "motion",
            "snr_db", "pulse_bpm", "perfusion_pct", "skewness")) out[k] = null
        val t = roi.tS
        val timing = if (frameTimesS != null && frameTimesS.size >= 2) frameTimesS else t
        if (timing.size >= 2 && timing.last() > timing.first()) {
            val dts = DoubleArray(timing.size - 1) { timing[it + 1] - timing[it] }
            val d = Dsp.median(dts.filter { it > 0 }.toDoubleArray())
            val span = timing.last() - timing.first()
            out["duration_s"] = span + d
            out["fps"] = (timing.size - 1) / span
            var missing = 0
            for (dt in dts) missing += max(0, floor(dt / d + 0.5).toInt() - 1)
            out["dropped_frac"] = missing.toDouble() / (timing.size - 1 + missing)
        } else {
            out["duration_s"] = 0.0
        }
        val n = t.size
        if (n == 0) return out
        out["mean_level"] = Dsp.median(roi.y)
        out["clipped_frac"] = Dsp.median(roi.clipFrac)
        out["dark_frac"] = roi.y.count { it < cfg.darkLevel }.toDouble() / n

        val ratios = ArrayList<Double>()
        val grid = roi.grid
        for (i in 1 until n) {
            val num: Double
            val den: Double
            if (grid != null) {
                var sn = 0.0
                var sd = 0.0
                for (k in 0 until 9) { sn += abs(grid[k][i] - grid[k][i - 1]); sd += grid[k][i - 1] }
                num = sn / 9.0
                den = sd / 9.0
            } else {
                num = abs(roi.y[i] - roi.y[i - 1])
                den = roi.y[i - 1]
            }
            if (den >= cfg.darkLevel) ratios.add(num / den)       // motion is judged on lit rows only
        }
        if (ratios.isNotEmpty()) out["motion"] = Dsp.median(ratios.toDoubleArray())

        val keepIdx = ArrayList<Int>()
        var last = Double.NEGATIVE_INFINITY
        for (i in 0 until n) if (t[i] > last) { keepIdx.add(i); last = t[i] }
        val tt = DoubleArray(keepIdx.size) { t[keepIdx[it]] }
        val hz = cfg.resampleHz
        val r30 = resample(tt, DoubleArray(keepIdx.size) { roi.r[keepIdx[it]] }, hz)
        val g30 = resample(tt, DoubleArray(keepIdx.size) { roi.g[keepIdx[it]] }, hz)
        val b30 = resample(tt, DoubleArray(keepIdx.size) { roi.b[keepIdx[it]] }, hz)
        if (r30.size >= Dsp.rhu(cfg.posWindowS * hz)) {
            val h = pos(r30, g30, b30, hz, cfg.posWindowS)
            val (f, p) = Dsp.periodogram(h, hz)
            val df = hz / Dsp.nfft(h.size)
            val fpk = Dsp.spectralPeak(f, p, cfg.pulseLoHz, cfg.pulseHiHz, df)
            var bandPower = false
            for (i in f.indices) if (f[i] >= cfg.snrLoHz && f[i] <= cfg.snrHiHz && p[i] > 0) bandPower = true
            if (fpk != null && bandPower) {
                out["pulse_bpm"] = 60.0 * fpk
                val f0 = if (refHrBpm != null) refHrBpm / 60.0 else fpk
                var sPow = 0.0
                var nPow = 0.0
                for (i in f.indices) {
                    if (f[i] < cfg.snrLoHz || f[i] > cfg.snrHiHz) continue
                    val sig = abs(f[i] - f0) <= cfg.snrF0HalfwidthHz || abs(f[i] - 2.0 * f0) <= cfg.snrH2HalfwidthHz
                    if (sig) sPow += p[i] else nPow += p[i]
                }
                out["snr_db"] = if (nPow <= 0) 99.0 else 10.0 * log10(max(sPow, 1e-300) / nPow)
            }
            val mu = Dsp.mean(h)
            var m2 = 0.0
            var m3 = 0.0
            for (v in h) { val d = v - mu; m2 += d * d; m3 += d * d * d }
            m2 /= h.size
            m3 /= h.size
            if (m2 > 0) out["skewness"] = m3 / m2.pow(1.5)
            val gm = Dsp.mean(g30)
            if (gm >= 1.0) {
                val half = Dsp.rhu(hz) / 2
                val cs = DoubleArray(g30.size + 1)
                for (i in g30.indices) cs[i + 1] = cs[i] + g30[i]
                val ac = DoubleArray(g30.size) {
                    val lo = max(0, it - half)
                    val hi = min(g30.size, it + half + 1)
                    g30[it] - (cs[hi] - cs[lo]) / (hi - lo)
                }
                out["perfusion_pct"] = 100.0 * (Dsp.quantile(ac, 0.95) - Dsp.quantile(ac, 0.05)) / gm
            }
        }
        return out
    }

    /** Linear interpolation of v(t) onto t0 + k / hz, k = 0 .. floor(span * hz). */
    private fun resample(t: DoubleArray, v: DoubleArray, hz: Double): DoubleArray {
        val n = t.size
        if (n < 2) return DoubleArray(0)
        val m = floor((t[n - 1] - t[0]) * hz + 1e-9).toInt() + 1
        val out = DoubleArray(m)
        var j = 0
        for (k in 0 until m) {
            val tg = t[0] + k / hz
            while (j < n - 2 && t[j + 1] <= tg) j++
            val slope = (v[j + 1] - v[j]) / (t[j + 1] - t[j])
            out[k] = v[j] + slope * (tg - t[j])
        }
        return out
    }

    /** POS pulse with overlap-add; windows with a channel mean below 1 code (black frames) are skipped. */
    private fun pos(r: DoubleArray, g: DoubleArray, b: DoubleArray, fs: Double, windowS: Double): DoubleArray {
        val n = r.size
        val win = Dsp.rhu(windowS * fs)
        val h = DoubleArray(n)
        val s1 = DoubleArray(win)
        val s2 = DoubleArray(win)
        for (s0 in 0..n - win) {
            var mr = 0.0; var mg = 0.0; var mb = 0.0
            for (i in 0 until win) { mr += r[s0 + i]; mg += g[s0 + i]; mb += b[s0 + i] }
            mr /= win; mg /= win; mb /= win
            if (minOf(mr, mg, mb) < 1.0) continue
            for (i in 0 until win) {
                val nr = r[s0 + i] / mr
                val ng = g[s0 + i] / mg
                val nb = b[s0 + i] / mb
                s1[i] = ng - nb
                s2[i] = -2.0 * nr + ng + nb
            }
            val sd1 = std(s1)
            val sd2 = std(s2)
            val alpha = if (sd2 > 0) sd1 / sd2 else 0.0
            var pm = 0.0
            for (i in 0 until win) pm += s1[i] + alpha * s2[i]
            pm /= win
            for (i in 0 until win) h[s0 + i] += (s1[i] + alpha * s2[i]) - pm
        }
        return h
    }

    private fun std(x: DoubleArray): Double {
        val mu = Dsp.mean(x)
        var s = 0.0
        for (v in x) s += (v - mu) * (v - mu)
        return sqrt(s / x.size)
    }
}
