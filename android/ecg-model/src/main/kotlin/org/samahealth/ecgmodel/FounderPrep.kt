package org.samahealth.ecgmodel

import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * The ECGFounder single-lead preprocessing chain, ported from palmppg/ecg/founder_prep.py so a strip recorded on
 * the phone reaches the model as the same numbers the laptop runner would produce. Pinned sample for sample by
 * configs/founder_fixtures/preprocess.json.
 *
 * Chain: NaN to zero, polyphase resample to 500 Hz (300 Hz uses 5/3), polarity check over the whole strip,
 * 10 s windows, then per window a 50 Hz notch (Q 30), a 4th-order Butterworth 0.67-40 Hz run forward and
 * backward, minus a 0.4 s running median, and a z-score.
 *
 * Source of the chain: https://github.com/PKUDigitalHealth/ECGFounder (MIT), util.filter_bandpass and
 * dataset.py z_score_normalization. The model itself is not here: it runs in ONNX Runtime.
 */
object FounderPrep {

    const val FS_MODEL = 500.0
    const val WIN_S = 10.0
    const val WIN = 5000                      // 10 s at 500 Hz
    const val ZSCORE_EPS = 1e-8
    const val POLARITY_NEG_FRAC = 0.7
    const val POLARITY_MIN_BEATS = 3
    const val MEDIAN_KERNEL = 201             // int(0.4 * 500) + 1

    /**
     * scipy.signal.iirnotch(50, 30, 500). Fixed because the chain always runs at 500 Hz; a test checks these
     * against the coefficients in the fixture file, so a change on the Python side cannot pass unnoticed.
     */
    val NOTCH_B = doubleArrayOf(0.9896361753628921, -1.6012649682336106, 0.9896361753628921)
    val NOTCH_A = doubleArrayOf(1.0, -1.6012649682336106, 0.9792723507257841)

    /** scipy.signal.butter(4, [0.67, 40], "bandpass", fs=500). */
    val BAND_B = doubleArrayOf(
        0.0021067813406203902, 0.0, -0.008427125362481561, 0.0, 0.012640688043722342, 0.0, -0.008427125362481561,
        0.0, 0.0021067813406203902,
    )
    val BAND_A = doubleArrayOf(
        1.0, -6.69982772563499, 19.691253828465822, -33.190544451430235, 35.11756594006398, -23.895107000645453,
        10.212953481905869, -2.5068563003602984, 0.27056222781627265,
    )

    /** Window probabilities for these labels are combined with max, not mean: they can sit in one window only. */
    val MAX_RULE_INDICES = intArrayOf(9, 16, 19, 91, 142)

    /** What [preprocess] did, alongside the model input. */
    class Windows(
        /** (n, 5000) float32-ready windows, flattened per window. */
        val windows: Array<DoubleArray>,
        val startsS: List<Double>,
        val fsIn: Double,
        val resampleUp: Int,
        val resampleDown: Int,
        val durationS: Double,
        val polarityFlipped: Boolean,
        val polarityNegativeFraction: Double,
        val polarityBeats: Int,
        val notes: List<String>,
    ) {
        val n: Int get() = windows.size

        /** The (n, 1, 5000) tensor ONNX Runtime takes, in row-major order. */
        fun toFloatArray(): FloatArray {
            val out = FloatArray(windows.size * WIN)
            for (i in windows.indices) for (j in 0 until WIN) out[i * WIN + j] = windows[i][j].toFloat()
            return out
        }
    }

    /** 500 Hz from [fs] by polyphase resampling; 300 Hz gives 5/3. Returns the signal and the (up, down) used. */
    fun resampleToModel(x: DoubleArray, fs: Double): Pair<DoubleArray, Pair<Int, Int>> {
        val (up, down) = ratio(FS_MODEL / fs)
        if (up == down) return x.copyOf() to (1 to 1)
        return Dsp.resamplePoly(x, up, down) to (up to down)
    }

    /** The smallest fraction with a denominator of at most 1000, as Fraction(...).limit_denominator(1000). */
    internal fun ratio(value: Double): Pair<Int, Int> {
        var bestNum = 1
        var bestDen = 1
        var bestErr = Double.MAX_VALUE
        for (den in 1..1000) {
            val num = (value * den).roundToInt()
            if (num <= 0) continue
            val err = abs(value - num.toDouble() / den)
            if (err < bestErr - 1e-15) {
                bestErr = err
                bestNum = num
                bestDen = den
                if (err == 0.0) break
            }
        }
        val g = gcd(bestNum, bestDen)
        return bestNum / g to bestDen / g
    }

    private fun gcd(a: Int, b: Int): Int = if (b == 0) a else gcd(b, a % b)

    /** util.filter_bandpass: 50 Hz notch, Butterworth 0.67-40 Hz, both forward and backward, minus the median. */
    fun filterBandpass(x: DoubleArray): DoubleArray {
        val notched = Dsp.filtfilt(NOTCH_B, NOTCH_A, x)
        val banded = Dsp.filtfilt(BAND_B, BAND_A, notched)
        val baseline = Dsp.medfilt(banded, MEDIAN_KERNEL)
        return DoubleArray(banded.size) { banded[it] - baseline[it] }
    }

    /** dataset.py z_score_normalization: (x - mean) / (std + 1e-8). */
    fun zScore(x: DoubleArray): DoubleArray {
        val mu = Dsp.mean(x)
        val sd = Dsp.std(x)
        return DoubleArray(x.size) { (x[it] - mu) / (sd + ZSCORE_EPS) }
    }

    /**
     * Is the dominant deflection negative in most beats (an inverted lead I, for example reversed fingers on the
     * Kardia)? Returns (flip, negative fraction, beats found).
     */
    fun polarityCheck(x500: DoubleArray, fs: Double = FS_MODEL): Triple<Boolean, Double, Int> {
        if (x500.size < (2 * fs).toInt()) return Triple(false, Double.NaN, 0)
        val y = filterBandpass(x500)
        val a = DoubleArray(y.size) { abs(y[it]) }
        val top = Dsp.percentile(a, 99.0)
        if (!top.isFinite() || top <= 0.0) return Triple(false, Double.NaN, 0)
        val peaks = Dsp.findPeaks(a, 0.5 * top, (0.3 * fs).toInt())
        if (peaks.size < POLARITY_MIN_BEATS) return Triple(false, Double.NaN, peaks.size)
        var neg = 0
        for (p in peaks) if (y[p] < 0) neg++
        val frac = neg.toDouble() / peaks.size
        return Triple(frac >= POLARITY_NEG_FRAC, frac, peaks.size)
    }

    /**
     * A single-lead strip in millivolts at [fs] to the model's 10 s windows. [filtered] follows training
     * (dataset.py); false is the ptbxl_eval.py path of z-score only. A tail shorter than 10 s is dropped.
     */
    fun preprocess(
        xIn: DoubleArray,
        fs: Double,
        filtered: Boolean = true,
        stepS: Double = WIN_S,
        polarityAuto: Boolean = true,
    ): Windows {
        val x = DoubleArray(xIn.size) { if (xIn[it].isFinite()) xIn[it] else 0.0 }
        val (y0, ud) = resampleToModel(x, fs)
        var y = y0
        val (flip, neg, beats) = if (polarityAuto) polarityCheck(y) else Triple(false, Double.NaN, 0)
        if (flip) y = DoubleArray(y.size) { -y[it] }
        val step = (stepS * FS_MODEL).roundToInt()
        require(step > 0) { "stepS must be positive" }
        val notes = ArrayList<String>()
        val starts = ArrayList<Int>()
        if (y.size >= WIN) {
            var s = 0
            while (s <= y.size - WIN) { starts.add(s); s += step }
        }
        if (starts.isEmpty()) {
            notes.add("strip shorter than ${WIN_S.toInt()} s (${"%.1f".format(y.size / FS_MODEL)} s): no window")
        }
        val windows = Array(starts.size) { i ->
            val raw = y.copyOfRange(starts[i], starts[i] + WIN)
            zScore(if (filtered) filterBandpass(raw) else raw)
        }
        return Windows(
            windows = windows,
            startsS = starts.map { it / FS_MODEL },
            fsIn = fs, resampleUp = ud.first, resampleDown = ud.second,
            durationS = x.size / fs,
            polarityFlipped = flip, polarityNegativeFraction = neg, polarityBeats = beats, notes = notes,
        )
    }

    /**
     * (n_windows, 150) to (150,): max over windows for the ectopy and pause labels, mean for every other, the
     * rule fixed before any study data was seen.
     */
    fun combineWindows(windowProbs: Array<DoubleArray>): DoubleArray {
        if (windowProbs.isEmpty()) return DoubleArray(0)
        val k = windowProbs[0].size
        val out = DoubleArray(k)
        for (j in 0 until k) {
            var s = 0.0
            for (w in windowProbs) s += w[j]
            out[j] = s / windowProbs.size
        }
        for (j in MAX_RULE_INDICES) {
            if (j >= k) continue
            var m = Double.NEGATIVE_INFINITY
            for (w in windowProbs) m = maxOf(m, w[j])
            out[j] = m
        }
        return out
    }

    fun combineRule(index: Int): String = if (index in MAX_RULE_INDICES) "max" else "mean"
}
