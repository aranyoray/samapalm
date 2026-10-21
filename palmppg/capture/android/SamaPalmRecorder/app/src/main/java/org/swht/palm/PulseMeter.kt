package org.swht.palm

import kotlin.math.abs
import kotlin.math.exp

/**
 * Turns the palm ROI mean into something an operator can act on: a detrended pulse waveform, a
 * beat rate, and a perfusion index.
 *
 * The raw ROI mean is almost all DC — skin brightness under the torch — with the pulse riding on
 * it at well under one percent. Plotting it raw shows a flat line that drifts, which tells the
 * operator nothing. So the DC is tracked with a slow exponential average and subtracted, the
 * remainder is lightly smoothed to kill per-pixel noise, and peaks are picked off that.
 *
 * This is a positioning aid, deliberately cheap and deliberately not the measurement: it runs on
 * a subsampled preview-resolution stream, not the recorded clip. [perfusionPct] is the number
 * worth watching — if it is near zero there is no pulse reaching the camera and the clip will be
 * worthless no matter how long it runs.
 */
class PulseMeter {

    companion object {
        private const val DC_TAU_S = 1.0        // slow enough to leave the pulse alone
        private const val AC_TAU_S = 0.04       // fast enough to keep the systolic upstroke
        private const val REFRACTORY_S = 0.30   // 200 bpm ceiling
        private const val STALE_S = 3.0         // no beat for this long and the rate is not real
        private const val MIN_BPM = 30.0
        private const val MAX_BPM = 200.0
    }

    @Volatile var bpm = 0.0; private set
    /** Peak-to-peak AC as a percentage of DC. Sub-0.1 % means effectively no pulse. */
    @Volatile var perfusionPct = 0.0; private set
    @Volatile var beats = 0L; private set

    private var dc = Double.NaN
    private var acSmooth = 0.0
    private var lastTNs = 0L
    private var envelope = 0.0

    // candidate-peak state
    private var inPeak = false
    private var peakVal = 0.0
    private var peakTNs = 0L
    private var lastBeatNs = 0L
    private var ibiSmooth = 0.0

    private var acMin = 0.0
    private var acMax = 0.0
    private var rangeDecay = 0.0

    /** True when the sample just pushed completed a beat, so the caller can mark the trace. */
    @Volatile var lastSampleWasPeak = false; private set

    fun reset() {
        dc = Double.NaN
        acSmooth = 0.0; envelope = 0.0; inPeak = false
        lastBeatNs = 0L; ibiSmooth = 0.0; bpm = 0.0; perfusionPct = 0.0; beats = 0
        acMin = 0.0; acMax = 0.0
    }

    /**
     * Feeds one ROI mean and returns the detrended value to plot.
     * @param tNs sample time on the reference clock.
     */
    fun push(tNs: Long, value: Double): Float {
        lastSampleWasPeak = false
        val dt = if (lastTNs == 0L) 1.0 / 30.0 else (tNs - lastTNs) / 1e9
        lastTNs = tNs
        if (dt <= 0.0 || dt > 1.0) {       // first sample, or a gap: restart the filters
            dc = if (dc.isNaN()) value else dc
            return 0f
        }
        if (dc.isNaN()) { dc = value; return 0f }

        dc += (1.0 - exp(-dt / DC_TAU_S)) * (value - dc)
        val ac = value - dc
        acSmooth += (1.0 - exp(-dt / AC_TAU_S)) * (ac - acSmooth)

        // running AC range, decayed so the operator sees recovery after a hand move
        val decay = exp(-dt / 4.0)
        acMax = maxOf(acSmooth, acMax * decay)
        acMin = minOf(acSmooth, acMin * decay)
        rangeDecay = acMax - acMin
        perfusionPct = if (dc > 1e-6) 100.0 * rangeDecay / dc else 0.0

        envelope = maxOf(abs(acSmooth), envelope * decay)
        val thresh = 0.45 * envelope

        if (!inPeak && acSmooth > thresh) {
            inPeak = true; peakVal = acSmooth; peakTNs = tNs
        } else if (inPeak) {
            if (acSmooth > peakVal) { peakVal = acSmooth; peakTNs = tNs }
            if (acSmooth < thresh * 0.5) {
                inPeak = false
                val sinceLast = (peakTNs - lastBeatNs) / 1e9
                if (lastBeatNs == 0L) {
                    lastBeatNs = peakTNs
                } else if (sinceLast > REFRACTORY_S) {
                    val inst = 60.0 / sinceLast
                    if (inst in MIN_BPM..MAX_BPM) {
                        ibiSmooth = if (ibiSmooth == 0.0) sinceLast
                        else 0.75 * ibiSmooth + 0.25 * sinceLast
                        bpm = 60.0 / ibiSmooth
                        beats++
                        lastSampleWasPeak = true
                    }
                    lastBeatNs = peakTNs
                }
            }
        }

        if (lastBeatNs > 0L && (tNs - lastBeatNs) / 1e9 > STALE_S) bpm = 0.0
        return acSmooth.toFloat()
    }
}
