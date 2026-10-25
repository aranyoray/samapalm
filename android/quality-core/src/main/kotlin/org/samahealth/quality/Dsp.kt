package org.samahealth.quality

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/** Numerics shared by the scorers, written to follow palmppg/quality/onsite.py operation for operation. */
internal object Dsp {
    /** Round half up for non-negative values (sample counts). */
    fun rhu(x: Double): Int = floor(x + 0.5).toInt()

    fun mean(x: DoubleArray): Double {
        var s = 0.0
        for (v in x) s += v
        return s / x.size
    }

    fun median(x: DoubleArray): Double {
        if (x.isEmpty()) return Double.NaN
        val a = x.copyOf().also { it.sort() }
        val m = a.size / 2
        return if (a.size % 2 == 1) a[m] else (a[m - 1] + a[m]) / 2.0
    }

    /** Linear-interpolation quantile (numpy's default). */
    fun quantile(x: DoubleArray, q: Double): Double {
        val a = x.copyOf().also { it.sort() }
        val pos = q * (a.size - 1)
        val lo = floor(pos).toInt()
        val hi = min(lo + 1, a.size - 1)
        return a[lo] + (a[hi] - a[lo]) * (pos - lo)
    }

    fun nfft(n: Int): Int {
        var p = 1
        val target = max(8 * n, 4096)
        while (p < target) p *= 2
        return p
    }

    /** Mean-removed, symmetric-Hann-windowed, zero-padded one-sided power spectrum: (f in Hz, power). */
    fun periodogram(x: DoubleArray, fs: Double): Pair<DoubleArray, DoubleArray> {
        val n = x.size
        val mu = mean(x)
        val nf = nfft(n)
        val re = DoubleArray(nf)
        val im = DoubleArray(nf)
        var wss = 0.0
        for (i in 0 until n) {
            val w = if (n > 1) 0.5 - 0.5 * cos(2.0 * PI * i / (n - 1)) else 1.0
            re[i] = (x[i] - mu) * w
            wss += w * w
        }
        fft(re, im)
        val half = nf / 2 + 1
        val f = DoubleArray(half) { it * (fs / nf) }
        val den = max(wss, 1e-12)
        val p = DoubleArray(half) { (re[it] * re[it] + im[it] * im[it]) / den }
        return f to p
    }

    /** In-place iterative radix-2 complex FFT (size a power of two). */
    fun fft(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) { j = j xor bit; bit = bit shr 1 }
            j = j or bit
            if (i < j) {
                val tr = re[i]; re[i] = re[j]; re[j] = tr
                val ti = im[i]; im[i] = im[j]; im[j] = ti
            }
        }
        var len = 2
        while (len <= n) {
            val ang = -2.0 * PI / len
            val halfLen = len / 2
            val wr = DoubleArray(halfLen) { cos(ang * it) }
            val wi = DoubleArray(halfLen) { sin(ang * it) }
            var s = 0
            while (s < n) {
                for (k in 0 until halfLen) {
                    val a = s + k
                    val b = a + halfLen
                    val xr = re[b] * wr[k] - im[b] * wi[k]
                    val xi = re[b] * wi[k] + im[b] * wr[k]
                    re[b] = re[a] - xr; im[b] = im[a] - xi
                    re[a] += xr; im[a] += xi
                }
                s += len
            }
            len = len shl 1
        }
    }

    /** Strongest bin of [p] within [lo, hi] Hz with parabolic refinement, or null when the band has no power. */
    fun spectralPeak(f: DoubleArray, p: DoubleArray, lo: Double, hi: Double, df: Double): Double? {
        var k = -1
        var any = false
        for (i in f.indices) {
            if (f[i] >= lo && f[i] <= hi) {
                if (p[i] > 0) any = true
                if (k < 0 || p[i] > p[k]) k = i
            }
        }
        if (k < 0 || !any) return null
        var fpk = f[k]
        if (k > 0 && k < f.size - 1) {
            val y0 = p[k - 1]; val y1 = p[k]; val y2 = p[k + 1]
            val den = y0 - 2.0 * y1 + y2
            if (den < 0) fpk = fpk + 0.5 * (y0 - y2) / den * df
        }
        return fpk
    }

    /** Second-order Butterworth low- or high-pass (RBJ bilinear form, a0 = 1): b0, b1, b2, a1, a2. */
    fun biquadCoeffs(lowPass: Boolean, f0: Double, fs: Double): DoubleArray {
        val w0 = 2.0 * PI * f0 / fs
        val c = cos(w0)
        val s = sin(w0)
        val alpha = s / (2.0 * (1.0 / sqrt(2.0)))
        val b0: Double
        val b1: Double
        if (lowPass) { b0 = (1.0 - c) / 2.0; b1 = 1.0 - c } else { b0 = (1.0 + c) / 2.0; b1 = -(1.0 + c) }
        val a0 = 1.0 + alpha
        return doubleArrayOf(b0 / a0, b1 / a0, b0 / a0, (-2.0 * c) / a0, (1.0 - alpha) / a0)
    }

    /** Second-order notch (RBJ cookbook), a0 = 1. Narrow at q = 30: 50 Hz goes, 40 Hz and the QRS stay. */
    fun notchCoeffs(f0: Double, q: Double, fs: Double): DoubleArray {
        val w0 = 2.0 * PI * f0 / fs
        val c = cos(w0)
        val s = sin(w0)
        val alpha = s / (2.0 * q)
        val a0 = 1.0 + alpha
        return doubleArrayOf(1.0 / a0, (-2.0 * c) / a0, 1.0 / a0, (-2.0 * c) / a0, (1.0 - alpha) / a0)
    }

    fun biquad(x: DoubleArray, co: DoubleArray): DoubleArray {
        val b0 = co[0]; val b1 = co[1]; val b2 = co[2]; val a1 = co[3]; val a2 = co[4]
        var z1 = 0.0
        var z2 = 0.0
        val out = DoubleArray(x.size)
        for (i in x.indices) {
            val xi = x[i]
            val yi = b0 * xi + z1
            z1 = b1 * xi - a1 * yi + z2
            z2 = b2 * xi - a2 * yi
            out[i] = yi
        }
        return out
    }

    /**
     * Zero-phase mains notch then band-pass: median removed, odd extension of 2 s, notch then HP then LP
     * biquad, forward then backward.
     *
     * The 40 Hz low-pass alone leaves mains pickup about 11 dB down, which is still enough to bother the beat
     * detector in a room lit by tubes; the notch takes it out without touching the QRS. Skipped when the
     * sample rate cannot carry it.
     */
    fun ecgBandpass(
        mv: DoubleArray, fs: Double, lo: Double = 0.5, hi: Double = 40.0,
        mainsHz: Double = 50.0, mainsQ: Double = 30.0,
    ): DoubleArray {
        val n = mv.size
        if (n == 0) return DoubleArray(0)
        val med = median(mv)
        val x = DoubleArray(n) { mv[it] - med }
        val sections = ArrayList<DoubleArray>(3)
        if (mainsHz > 0.0 && mainsHz < 0.45 * fs) sections.add(notchCoeffs(mainsHz, mainsQ, fs))
        sections.add(biquadCoeffs(false, lo, fs))
        sections.add(biquadCoeffs(true, min(hi, 0.45 * fs), fs))
        val pad = min(n - 1, rhu(2.0 * fs))
        var y = DoubleArray(n + 2 * pad)
        for (i in 0 until pad) y[i] = 2.0 * x[0] - x[pad - i]
        for (i in 0 until n) y[pad + i] = x[i]
        for (i in 0 until pad) y[pad + n + i] = 2.0 * x[n - 1] - x[n - 2 - i]
        for (co in sections) y = biquad(y, co)
        y.reverse()
        for (co in sections) y = biquad(y, co)
        y.reverse()
        return y.copyOfRange(pad, pad + n)
    }
}
