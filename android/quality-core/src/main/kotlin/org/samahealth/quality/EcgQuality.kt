package org.samahealth.quality

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Lead-I ECG grade (mV at fs Hz). 0.5-40 Hz Butterworth biquads run forward and backward; Pan-Tompkins style QRS
 * detection (5-point derivative, square, 150 ms moving integration, adaptive thresholds with search-back, 250 ms
 * refractory) with one polarity for the record and R moved to that extreme within +/-75 ms; metrics: template
 * correlation with the median beat (-0.25..+0.45 s, Orphanidou et al. 2015), kSQI (Pearson kurtosis, Clifford et al.
 * 2012), flat-line share (1 s windows below 0.05 mV peak-to-peak), RR checks after Orphanidou, and RR irregularity after
 * Dash et al. 2009 (RMSSD/mean RR, turning points inside the random band, Shannon entropy over 16 bins after trimming
 * n/16 RRs at each end). The irregular flag is a screening heuristic for clinician review: it never lowers the grade and
 * switches off the RR-ratio rule. Thresholds: [EcgQualityConfig] (PROVISIONAL).
 */
object EcgQuality {

    fun score(mv: DoubleArray, fs: Double, cfg: EcgQualityConfig = EcgQualityConfig()): Grade {
        val a = analyse(mv, fs, cfg)
        val (level, reasons) = grade(a.metrics, a.irregular, cfg)
        return Grade(level, reasons, a.metrics)
    }

    /** R-peak sample indices (band-passed 0.5-40 Hz first). */
    fun detectQrs(mv: DoubleArray, fs: Double): IntArray = detect(Dsp.ecgBandpass(mv, fs), fs).first

    internal class Analysis(val metrics: Map<String, Double?>, val irregular: Boolean, val rrMinS: Double?)

    internal fun analyse(mv: DoubleArray, fs: Double, cfg: EcgQualityConfig): Analysis {
        val x = DoubleArray(mv.size) { if (mv[it].isFinite()) mv[it] else 0.0 }
        val n = x.size
        val m = LinkedHashMap<String, Double?>()
        for (k in listOf("duration_s", "hr_bpm", "n_beats", "rr_max_s", "rr_ratio", "template_corr", "ksqi",
            "flat_frac", "irregular_flag", "rmssd_ratio", "tpr", "shannon", "inverted")) m[k] = null
        m["duration_s"] = if (fs > 0) n / fs else 0.0
        m["n_beats"] = 0.0
        m["irregular_flag"] = 0.0
        m["inverted"] = 0.0
        if (n == 0) {
            m["flat_frac"] = 1.0
            return Analysis(m, false, null)
        }
        val y = Dsp.ecgBandpass(x, fs, cfg.bandLoHz, cfg.bandHiHz, cfg.mainsHz, cfg.mainsQ)
        val (r, inverted) = detect(y, fs)
        m["n_beats"] = r.size.toDouble()
        m["inverted"] = if (inverted) 1.0 else 0.0
        val w = Dsp.rhu(fs)
        val nw = if (w > 0) n / w else 0
        if (nw == 0) {
            m["flat_frac"] = if ((x.max() - x.min()) < cfg.flatPtpMv) 1.0 else 0.0
        } else {
            var flat = 0
            for (k in 0 until nw) {
                var lo = Double.POSITIVE_INFINITY
                var hi = Double.NEGATIVE_INFINITY
                for (i in k * w until (k + 1) * w) { lo = min(lo, x[i]); hi = max(hi, x[i]) }
                if (hi - lo < cfg.flatPtpMv) flat++
            }
            m["flat_frac"] = flat.toDouble() / nw
        }
        val mu = Dsp.mean(y)
        var m2 = 0.0
        var m4 = 0.0
        for (v in y) { val d = (v - mu) * (v - mu); m2 += d; m4 += d * d }
        m2 /= n
        m4 /= n
        if (m2 > 0) m["ksqi"] = m4 / (m2 * m2)
        var irregular = false
        var rrMin: Double? = null
        if (r.size >= 2) {
            val rr = DoubleArray(r.size - 1) { (r[it + 1] - r[it]) / fs }
            rrMin = rr.min()
            m["hr_bpm"] = 60.0 / Dsp.median(rr)
            m["rr_max_s"] = rr.max()
            m["rr_ratio"] = rr.max() / rrMin
            if (rr.size >= cfg.minRrForRhythm) {
                val irr = irregularity(rr)
                m["rmssd_ratio"] = irr.rmssdRatio
                m["tpr"] = irr.tpr
                m["shannon"] = irr.shannon
                irregular = irr.rmssdRatio >= cfg.irregularRmssdRatio && irr.tpRandom &&
                    irr.shannon >= cfg.irregularShannon
                m["irregular_flag"] = if (irregular) 1.0 else 0.0
            }
        }
        val pre = Dsp.rhu(0.25 * fs)
        val post = Dsp.rhu(0.45 * fs)
        val beats = r.filter { it - pre >= 0 && it + post <= n }.map { y.copyOfRange(it - pre, it + post) }
        if (beats.size >= 3) {
            val len = pre + post
            val tmpl = DoubleArray(len) { j -> Dsp.median(DoubleArray(beats.size) { beats[it][j] }) }
            val tm = Dsp.mean(tmpl)
            val tc = DoubleArray(len) { tmpl[it] - tm }
            var tss = 0.0
            for (v in tc) tss += v * v
            if (tss > 0) {
                val cors = DoubleArray(beats.size)
                for ((bi, beat) in beats.withIndex()) {
                    val bm = Dsp.mean(beat)
                    var bss = 0.0
                    var cross = 0.0
                    for (j in 0 until len) { val bc = beat[j] - bm; bss += bc * bc; cross += bc * tc[j] }
                    val den = sqrt(bss * tss)
                    cors[bi] = if (den > 0) cross / den else 0.0
                }
                m["template_corr"] = Dsp.mean(cors)
            }
        }
        return Analysis(m, irregular, rrMin)
    }

    internal fun grade(m: Map<String, Double?>, irregular: Boolean, cfg: EcgQualityConfig): Pair<String, List<String>> {
        val retake = ArrayList<String>()
        val border = ArrayList<String>()
        val dur = m.getValue("duration_s")!!
        if (dur < cfg.minDurationS) retake.add("ECG too short (${fmt(dur, 1)} s, need ${fmt(cfg.minDurationS, 0)} s)")
        val flat = m.getValue("flat_frac")!!
        if (flat > cfg.retakeFlatFrac) {
            retake.add("Flat line in ${fmt(100.0 * flat, 0)}% of the recording: fingers off the electrodes?")
        } else if (flat > cfg.borderlineFlatFrac) {
            border.add("Flat line in ${fmt(100.0 * flat, 0)}% of the recording")
        }
        val nb = m.getValue("n_beats")!!.toInt()
        if (nb < cfg.minBeats) retake.add("Too few beats detected ($nb)")
        val tcor = m["template_corr"]
        if (tcor != null && tcor < cfg.retakeTemplateCorr) {
            retake.add("Beats do not look alike (template match ${fmt(tcor, 2)}): noise or movement")
        } else if (tcor != null && tcor < cfg.borderlineTemplateCorr) {
            border.add("Noisy beats (template match ${fmt(tcor, 2)})")
        }
        val hr = m["hr_bpm"]
        if (hr != null && (hr < cfg.retakeHrLo || hr > cfg.retakeHrHi)) {
            retake.add("Heart rate out of range (${fmt(hr, 0)} bpm): beats probably mis-detected")
        } else if (hr != null && (hr < cfg.borderlineHrLo || hr > cfg.borderlineHrHi)) {
            border.add("Heart rate ${fmt(hr, 0)} bpm is outside ${fmt(cfg.borderlineHrLo, 0)}-${fmt(cfg.borderlineHrHi, 0)} bpm")
        }
        val ks = m["ksqi"]
        if (ks != null && ks < cfg.minKsqi) border.add("Noisy baseline (kurtosis ${fmt(ks, 1)})")
        val rrMax = m["rr_max_s"]
        if (rrMax != null && rrMax > cfg.maxRrS) border.add("Long gap between beats (${fmt(rrMax, 1)} s)")
        val ratio = m["rr_ratio"]
        if (ratio != null && !irregular && ratio > cfg.maxRrRatio) {
            border.add("Uneven beat detection (longest/shortest interval ${fmt(ratio, 1)})")
        }
        val level = if (retake.isNotEmpty()) "retake" else if (border.isNotEmpty()) "borderline" else "good"
        return level to (retake + border)
    }

    /** Detection on the band-passed signal: (R indices, inverted). */
    internal fun detect(y: DoubleArray, fs: Double): Pair<IntArray, Boolean> {
        val n = y.size
        if (n < 5) return IntArray(0) to false
        val m = integratedEnergy(y, fs)
        val peaks = (1 until n - 1).filter { m[it] > m[it - 1] && m[it] >= m[it + 1] }
        val w2 = Dsp.rhu(2.0 * fs)
        val maxima = ArrayList<Double>()
        var s = 0
        while (s < n) {
            val e = min(n, s + w2)
            if (e - s >= w2 / 2) {
                var mx = Double.NEGATIVE_INFINITY
                for (i in s until e) mx = max(mx, m[i])
                maxima.add(mx)
            }
            s += w2
        }
        var spki = if (maxima.isNotEmpty()) Dsp.median(maxima.toDoubleArray()) else m.max()
        var npki = Dsp.median(m)
        var thr = npki + 0.25 * (spki - npki)
        val refr = Dsp.rhu(0.25 * fs)
        val qrs = ArrayList<Int>()
        val rr = ArrayList<Int>()
        var pending = ArrayList<Int>()
        for (p in peaks) {
            if (qrs.isNotEmpty() && rr.isNotEmpty()) {
                val recent = rr.subList(max(0, rr.size - 8), rr.size)
                val rrAvg = recent.sum().toDouble() / recent.size
                if (p - qrs.last() > 1.66 * rrAvg) {
                    var best = -1
                    for (c in pending) {
                        if (c - qrs.last() > refr && m[c] > 0.5 * thr && (best < 0 || m[c] > m[best])) best = c
                    }
                    if (best >= 0) {
                        rr.add(best - qrs.last())
                        qrs.add(best)
                        spki = 0.25 * m[best] + 0.75 * spki
                        val b = best
                        pending = ArrayList(pending.filter { it > b })
                        thr = npki + 0.25 * (spki - npki)
                    }
                }
            }
            if (qrs.isNotEmpty() && p - qrs.last() <= refr) continue
            if (m[p] > thr) {
                if (qrs.isNotEmpty()) rr.add(p - qrs.last())
                qrs.add(p)
                spki = 0.125 * m[p] + 0.875 * spki
                pending = ArrayList()
            } else {
                npki = 0.125 * m[p] + 0.875 * npki
                pending.add(p)
            }
            thr = npki + 0.25 * (spki - npki)
        }
        return refine(y, fs, qrs)
    }

    private fun integratedEnergy(y: DoubleArray, fs: Double): DoubleArray {
        val n = y.size
        val d = DoubleArray(n)
        if (n >= 5) for (i in 2 until n - 2) d[i] = (2.0 * y[i + 1] + y[i + 2] - y[i - 2] - 2.0 * y[i - 1]) / 8.0
        val half = Dsp.rhu(0.150 * fs) / 2
        val cs = DoubleArray(n + 1)
        for (i in 0 until n) cs[i + 1] = cs[i] + d[i] * d[i]
        return DoubleArray(n) {
            val lo = max(0, it - half)
            val hi = min(n, it + half + 1)
            (cs[hi] - cs[lo]) / (hi - lo)
        }
    }

    /** One polarity for the record (inverted when the median negative swing > 1.5 x the positive one), R moved to
     *  that extreme within +/-75 ms, refractory merge, beats within 75 ms of either end dropped. */
    private fun refine(y: DoubleArray, fs: Double, qrs: List<Int>): Pair<IntArray, Boolean> {
        val n = y.size
        val rw = Dsp.rhu(0.075 * fs)
        val refr = Dsp.rhu(0.25 * fs)
        if (qrs.isEmpty()) return IntArray(0) to false
        val pos = DoubleArray(qrs.size)
        val neg = DoubleArray(qrs.size)
        for ((k, p) in qrs.withIndex()) {
            var hi = Double.NEGATIVE_INFINITY
            var lo = Double.POSITIVE_INFINITY
            for (i in max(0, p - rw) until min(n, p + rw + 1)) { hi = max(hi, y[i]); lo = min(lo, y[i]) }
            pos[k] = hi
            neg[k] = -lo
        }
        val inverted = Dsp.median(neg) > 1.5 * Dsp.median(pos)
        val sy = if (inverted) DoubleArray(n) { -y[it] } else y
        val refined = qrs.map { p ->
            val lo = max(0, p - rw)
            var best = lo
            for (i in lo until min(n, p + rw + 1)) if (sy[i] > sy[best]) best = i
            best
        }.sorted()
        val out = ArrayList<Int>()
        for (r in refined) {
            if (out.isNotEmpty() && r - out.last() < refr) {
                if (sy[r] > sy[out.last()]) out[out.size - 1] = r
            } else {
                out.add(r)
            }
        }
        return out.filter { it in rw..(n - 1 - rw) }.toIntArray() to inverted
    }

    internal class Irregularity(val rmssdRatio: Double, val tpr: Double, val shannon: Double, val tpRandom: Boolean)

    /** Dash et al. 2009 on RR intervals in seconds (needs at least 3). */
    internal fun irregularity(rr: DoubleArray): Irregularity {
        val n = rr.size
        val k = n / 16
        val order = rr.indices.sortedBy { rr[it] }
        val keep = order.subList(k, n - k).sorted()
        val tr = DoubleArray(keep.size) { rr[keep[it]] }
        var ss = 0.0
        for (i in 0 until tr.size - 1) { val d = tr[i + 1] - tr[i]; ss += d * d }
        val rmssd = if (tr.size > 1) sqrt(ss / (tr.size - 1)) else 0.0
        val rmssdRatio = rmssd / Dsp.mean(tr)
        var nTp = 0
        for (i in 1 until n - 1) if ((rr[i] - rr[i - 1]) * (rr[i + 1] - rr[i]) < 0) nTp++
        val tpr = nTp.toDouble() / (n - 2)
        val mu = (2.0 * n - 4.0) / 3.0
        val sigma = sqrt((16.0 * n - 29.0) / 90.0)
        val tpRandom = abs(nTp - mu) <= 1.96 * sigma
        val lo = tr.min()
        val hi = tr.max()
        var shannon = 0.0
        if (hi - lo > 0) {
            val counts = IntArray(16)
            for (v in tr) counts[min(15, floor((v - lo) / (hi - lo) * 16.0).toInt())]++
            for (c in counts) if (c > 0) { val p = c.toDouble() / tr.size; shannon -= p * ln(p) }
            shannon /= ln(16.0)
        }
        return Irregularity(rmssdRatio, tpr, shannon, tpRandom)
    }
}

/** Participant-friendly rhythm summary built on [EcgQuality]; never names a rhythm. */
object EcgSummary {
    fun summarise(mv: DoubleArray, fs: Double): RhythmSummary = summarise(mv, fs, EcgQualityConfig())

    fun summarise(mv: DoubleArray, fs: Double, cfg: EcgQualityConfig): RhythmSummary {
        val a = EcgQuality.analyse(mv, fs, cfg)
        val m = a.metrics
        val (level, _) = EcgQuality.grade(m, a.irregular, cfg)
        val hr = m["hr_bpm"]
        val rhythm: String
        val sentences: List<String>
        if (level == "retake" || hr == null || m["rmssd_ratio"] == null) {
            rhythm = "insufficient"
            sentences = listOf(
                "The recording was not clear enough to measure the heart rate and rhythm.",
                "This often happens when the fingers move or do not rest fully on the sensor.",
            )
        } else {
            rhythm = if (a.irregular) "irregular" else "regular"
            val second = if (a.irregular) {
                "The time between beats varied more than usual, so a study doctor will look at this recording closely."
            } else {
                "The beats came at a steady pace."
            }
            sentences = listOf("Your heart rate during the recording was about ${fmt(hr, 0)} beats per minute.", second)
        }
        return RhythmSummary(
            hrBpm = if (rhythm == "insufficient") null else hr,
            rhythm = rhythm,
            inverted = m["inverted"] == 1.0,
            nBeats = m.getValue("n_beats")!!.toInt(),
            rrMinS = a.rrMinS,
            rrMaxS = m["rr_max_s"],
            irregularFlag = a.irregular,
            sentences = sentences + RhythmSummary.CLOSING,
        )
    }
}
