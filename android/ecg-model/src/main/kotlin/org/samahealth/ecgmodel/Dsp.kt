package org.samahealth.ecgmodel

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * The scipy operations the ECGFounder chain uses, written to follow them step for step so the phone feeds the
 * model the same numbers the laptop does. Pinned by configs/founder_fixtures/preprocess.json.
 */
object Dsp {

    /** Modified Bessel function of the first kind, order 0: the Kaiser window's weight function. */
    fun besselI0(x: Double): Double {
        // series sum (x^2/4)^k / (k!)^2, which converges quickly for the |x| <= 5 the Kaiser beta needs
        var term = 1.0
        var sum = 1.0
        val q = x * x / 4.0
        var k = 1
        while (k < 60) {
            term *= q / (k.toDouble() * k.toDouble())
            sum += term
            if (term < 1e-18 * sum) break
            k++
        }
        return sum
    }

    /** numpy.kaiser(n, beta). */
    fun kaiser(n: Int, beta: Double): DoubleArray {
        if (n == 1) return doubleArrayOf(1.0)
        val m = (n - 1).toDouble()
        val den = besselI0(beta)
        return DoubleArray(n) {
            val r = 2.0 * it / m - 1.0
            besselI0(beta * sqrt(max(0.0, 1.0 - r * r))) / den
        }
    }

    /**
     * scipy.signal.firwin(numtaps, cutoff, window=('kaiser', beta)) for a low pass with pass_zero: the windowed
     * sinc, scaled so the response at DC is exactly 1. [cutoff] is in units of the Nyquist rate.
     */
    fun firwinLowpass(numtaps: Int, cutoff: Double, beta: Double = 5.0): DoubleArray {
        val alpha = 0.5 * (numtaps - 1)
        val win = kaiser(numtaps, beta)
        val h = DoubleArray(numtaps)
        for (i in 0 until numtaps) {
            val m = i - alpha
            h[i] = cutoff * sinc(cutoff * m) * win[i]
        }
        var s = 0.0
        for (v in h) s += v
        for (i in h.indices) h[i] /= s
        return h
    }

    /** numpy.sinc: sin(pi x) / (pi x), 1 at 0. */
    fun sinc(x: Double): Double {
        if (x == 0.0) return 1.0
        val px = PI * x
        return sin(px) / px
    }

    /** scipy.signal.upfirdn output length. */
    fun upfirdnLen(lenH: Int, lenX: Int, up: Int, down: Int): Int = (((lenX - 1) * up + lenH) - 1) / down + 1

    /**
     * scipy.signal.resample_poly(x, up, down) with the default Kaiser(5.0) design: insert [up] - 1 zeros,
     * convolve with the designed filter, keep every [down]th sample, and trim so the output sits at the centre.
     */
    fun resamplePoly(x: DoubleArray, up0: Int, down0: Int): DoubleArray {
        var up = up0
        var down = down0
        val g = gcd(up, down)
        up /= g
        down /= g
        if (up == 1 && down == 1) return x.copyOf()
        val nIn = x.size
        val nOutL = nIn.toLong() * up
        val nOut = (nOutL / down + if (nOutL % down != 0L) 1 else 0).toInt()
        val maxRate = max(up, down)
        val halfLen = 10 * maxRate
        val base = firwinLowpass(2 * halfLen + 1, 1.0 / maxRate)
        for (i in base.indices) base[i] *= up

        val nPrePad = down - halfLen % down
        var nPostPad = 0
        val nPreRemove = (halfLen + nPrePad) / down
        while (upfirdnLen(base.size + nPrePad + nPostPad, nIn, up, down) < nOut + nPreRemove) nPostPad++
        val h = DoubleArray(nPrePad + base.size + nPostPad)
        System.arraycopy(base, 0, h, nPrePad, base.size)

        // the upsampled signal is mostly zeros, so step the filter over the samples that are actually there
        val fullLen = (nIn - 1) * up + h.size
        val full = DoubleArray(fullLen)
        for (i in 0 until nIn) {
            val xi = x[i]
            if (xi == 0.0) continue
            val off = i * up
            for (k in h.indices) full[off + k] += xi * h[k]
        }
        val out = DoubleArray(nOut)
        for (j in 0 until nOut) {
            val idx = (nPreRemove + j) * down
            out[j] = if (idx < fullLen) full[idx] else 0.0
        }
        return out
    }

    private fun gcd(a: Int, b: Int): Int = if (b == 0) a else gcd(b, a % b)

    /** scipy.signal.lfilter for a monic `a` (a[0] == 1), transposed direct form II, with initial state [zi]. */
    fun lfilter(b: DoubleArray, a: DoubleArray, x: DoubleArray, zi: DoubleArray? = null): DoubleArray {
        val n = max(a.size, b.size)
        val bb = b.copyOf(n)
        val aa = a.copyOf(n)
        val z = DoubleArray(n - 1)
        if (zi != null) System.arraycopy(zi, 0, z, 0, minOf(zi.size, z.size))
        val y = DoubleArray(x.size)
        for (i in x.indices) {
            val xi = x[i]
            val yi = bb[0] * xi + z[0]
            for (k in 0 until n - 2) z[k] = bb[k + 1] * xi + z[k + 1] - aa[k + 1] * yi
            z[n - 2] = bb[n - 1] * xi - aa[n - 1] * yi
            y[i] = yi
        }
        return y
    }

    /**
     * scipy.signal.lfilter_zi: the steady-state state for unit step input, found by solving
     * (I - A^T) zi = b[1:] - a[1:] b[0] with A the companion matrix of `a`.
     */
    fun lfilterZi(b: DoubleArray, a: DoubleArray): DoubleArray {
        val n = max(a.size, b.size)
        val bb = b.copyOf(n)
        val aa = a.copyOf(n)
        val m = n - 1
        // companion(a).T has -a[1:]/a[0] down its first column and the identity above the diagonal
        val mat = Array(m) { DoubleArray(m) }
        for (i in 0 until m) {
            mat[i][i] += 1.0
            mat[i][0] -= -aa[i + 1] / aa[0]
            if (i + 1 < m) mat[i][i + 1] -= 1.0
        }
        val rhs = DoubleArray(m) { bb[it + 1] - aa[it + 1] * bb[0] }
        return solve(mat, rhs)
    }

    /** Gaussian elimination with partial pivoting. */
    fun solve(aIn: Array<DoubleArray>, bIn: DoubleArray): DoubleArray {
        val n = bIn.size
        val a = Array(n) { aIn[it].copyOf() }
        val b = bIn.copyOf()
        for (col in 0 until n) {
            var piv = col
            for (r in col + 1 until n) if (abs(a[r][col]) > abs(a[piv][col])) piv = r
            if (piv != col) {
                val t = a[col]; a[col] = a[piv]; a[piv] = t
                val tb = b[col]; b[col] = b[piv]; b[piv] = tb
            }
            val d = a[col][col]
            require(abs(d) > 1e-300) { "singular matrix in lfilter_zi" }
            for (r in col + 1 until n) {
                val f = a[r][col] / d
                if (f == 0.0) continue
                for (c in col until n) a[r][c] -= f * a[col][c]
                b[r] -= f * b[col]
            }
        }
        val x = DoubleArray(n)
        for (r in n - 1 downTo 0) {
            var s = b[r]
            for (c in r + 1 until n) s -= a[r][c] * x[c]
            x[r] = s / a[r][r]
        }
        return x
    }

    /** scipy.signal._arraytools.odd_ext: reflect about the end points. */
    fun oddExt(x: DoubleArray, n: Int): DoubleArray {
        if (n < 1) return x.copyOf()
        require(x.size > n) { "odd_ext needs more than $n samples, got ${x.size}" }
        val out = DoubleArray(x.size + 2 * n)
        for (i in 0 until n) out[i] = 2.0 * x[0] - x[n - i]
        System.arraycopy(x, 0, out, n, x.size)
        val last = x.size - 1
        for (i in 0 until n) out[n + x.size + i] = 2.0 * x[last] - x[last - 1 - i]
        return out
    }

    /** scipy.signal.filtfilt with the defaults: odd padding of 3 max(len(a), len(b)) and the step-response state. */
    fun filtfilt(b: DoubleArray, a: DoubleArray, x: DoubleArray): DoubleArray {
        val padlen = 3 * max(a.size, b.size)
        if (x.size <= padlen) return x.copyOf()
        val ext = oddExt(x, padlen)
        val zi = lfilterZi(b, a)
        var y = lfilter(b, a, ext, DoubleArray(zi.size) { zi[it] * ext[0] })
        y = y.reversedArray()
        y = lfilter(b, a, y, DoubleArray(zi.size) { zi[it] * y[0] })
        y = y.reversedArray()
        return y.copyOfRange(padlen, padlen + x.size)
    }

    /** scipy.signal.medfilt: odd kernel, zeros outside the signal. */
    fun medfilt(x: DoubleArray, kernel: Int): DoubleArray {
        require(kernel % 2 == 1) { "the median kernel must be odd" }
        val half = kernel / 2
        val out = DoubleArray(x.size)
        val buf = DoubleArray(kernel)
        for (i in x.indices) {
            for (k in 0 until kernel) {
                val j = i - half + k
                buf[k] = if (j in x.indices) x[j] else 0.0
            }
            val c = buf.copyOf()
            c.sort()
            out[i] = c[half]
        }
        return out
    }

    fun mean(x: DoubleArray): Double {
        var s = 0.0
        for (v in x) s += v
        return s / x.size
    }

    /** Population standard deviation, as numpy's default. */
    fun std(x: DoubleArray): Double {
        val mu = mean(x)
        var s = 0.0
        for (v in x) s += (v - mu) * (v - mu)
        return sqrt(s / x.size)
    }

    /** numpy.percentile with linear interpolation. */
    fun percentile(x: DoubleArray, q: Double): Double {
        val a = x.copyOf()
        a.sort()
        val pos = q / 100.0 * (a.size - 1)
        val lo = pos.toInt()
        val hi = minOf(lo + 1, a.size - 1)
        return a[lo] + (a[hi] - a[lo]) * (pos - lo)
    }

    /**
     * scipy.signal.find_peaks(x, height=, distance=): local maxima above [height], then the smallest peaks are
     * removed until every pair is at least [distance] samples apart.
     */
    fun findPeaks(x: DoubleArray, height: Double, distance: Int): IntArray {
        val peaks = ArrayList<Int>()
        var i = 1
        while (i < x.size - 1) {
            if (x[i] > x[i - 1]) {
                // a run of equal samples counts once, at the middle of the plateau
                var j = i
                while (j < x.size - 1 && x[j + 1] == x[i]) j++
                if (j < x.size - 1 && x[j] > x[j + 1] && x[i] >= height) peaks.add((i + j) / 2)
                i = j + 1
            } else {
                i++
            }
        }
        if (distance <= 1 || peaks.isEmpty()) return peaks.toIntArray()
        val order = peaks.indices.sortedByDescending { x[peaks[it]] }
        val keep = BooleanArray(peaks.size) { true }
        for (idx in order) {
            if (!keep[idx]) continue
            var k = idx - 1
            while (k >= 0 && peaks[idx] - peaks[k] < distance) { keep[k] = false; k-- }
            k = idx + 1
            while (k < peaks.size && peaks[k] - peaks[idx] < distance) { keep[k] = false; k++ }
        }
        return peaks.indices.filter { keep[it] }.map { peaks[it] }.toIntArray()
    }

    fun ceilInt(x: Double): Int = ceil(x).toInt()

    @Suppress("unused")
    private fun unusedCos() = cos(0.0)
}
