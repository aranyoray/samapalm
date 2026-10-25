package org.samahealth.onboarding.recorder

import kotlin.math.abs
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.roundToLong

/**
 * The camera-control arithmetic for a palm PPG clip, kept free of Android types so it runs under
 * plain JUnit. [PalmRecorderActivity] owns the camera; this object owns the numbers it sends to it.
 *
 * Everything here exists because an automatic control, left running, writes a signal into the
 * clip that lives in the same band as the pulse and cannot be separated from it afterwards
 * (protocol section 5). The rules therefore favour *fixed and logged* over *sharp and
 * convenient*: a palm that is slightly soft but never refocuses is a usable clip; a palm that is
 * tack sharp half the time is not.
 */
object PalmControls {

    /**
     * Rig distances the operator can pick from, in centimetres. 17 cm is the default: the
     * harmonic midpoint of the 15-20 cm band the rig is designed for, which is where a single
     * fixed focus plane serves both ends best. 13 cm is the OnePlus 12 main lens's closest focus
     * and is offered only so the limit is visible, not as a working position.
     */
    val DISTANCE_PRESETS_CM = floatArrayOf(13f, 15f, 17f, 20f, 25f)
    const val DEFAULT_DISTANCE_CM = 17f

    /**
     * Longest exposure allowed during capture. Beyond this, ordinary hand tremor at palm
     * distance smears across more than a pixel per frame and the AE's preference for a long
     * shutter at low gain starts costing signal rather than saving it. Brightness lost to the cap
     * is bought back with sensitivity in [capExposure].
     */
    const val MAX_EXPOSURE_NS = 12_000_000L

    /**
     * Mains frequency at the study site. Fluorescent tubes and most LED drivers ripple at twice this, so a
     * shutter that lasts a whole number of half-cycles collects the same light every frame and the flicker
     * cancels. India is 50 Hz; a 60 Hz site changes this one line.
     */
    const val MAINS_HZ = 50.0

    /** One mains half-cycle: the shortest flicker-free shutter, 10 ms at 50 Hz. */
    val FLICKER_STEP_NS: Long = Math.round(1e9 / (2.0 * MAINS_HZ))

    /** Target ROI luma after the settle, in 8-bit sRGB code values. Mid-grey with headroom. */
    const val TARGET_ROI_LUMA = 140f
    const val MIN_ROI_LUMA = 40f
    const val MAX_ROI_LUMA = 215f
    /** Fraction of ROI pixels at or above [CLIP_LEVEL] beyond which the exposure is too hot. */
    const val MAX_CLIP_FRACTION = 0.02f
    const val CLIP_LEVEL = 250

    /** Frames per second below which the clip is not a 30 fps clip, whatever was requested. */
    const val MIN_FPS = 29f

    // ---- focus -----------------------------------------------------------------------------

    /** Camera2 focus distance is in diopters: 1 / metres. */
    fun diopters(distanceCm: Float): Float = 100f / distanceCm

    fun centimetres(diopters: Float): Float = if (diopters <= 0f) Float.POSITIVE_INFINITY else 100f / diopters

    data class Focus(val requestedDiopters: Float, val appliedDiopters: Float, val clampedToLens: Boolean)

    /**
     * The focus distance to send, clamped to what the lens can reach. `minimumFocusDistance` is
     * Camera2's `LENS_INFO_MINIMUM_FOCUS_DISTANCE`: the *largest* diopter value the lens
     * accepts, i.e. its closest focus. A request beyond it is pinned there and flagged, so a
     * palm held closer than the lens can focus is reported rather than silently refocused.
     */
    fun focusFor(distanceCm: Float, minimumFocusDistance: Float?): Focus {
        val requested = diopters(distanceCm)
        val limit = minimumFocusDistance?.takeIf { it > 0f } ?: Float.POSITIVE_INFINITY
        val applied = requested.coerceIn(0f, limit)
        return Focus(requested, applied, applied != requested)
    }

    /** Whether the lens reported a focus distance close enough to the one requested. */
    fun focusAchieved(requestedDiopters: Float, reportedDiopters: Float?, toleranceDiopters: Float = 0.5f): Boolean =
        reportedDiopters != null && reportedDiopters >= 0f && abs(reportedDiopters - requestedDiopters) <= toleranceDiopters

    // ---- exposure --------------------------------------------------------------------------

    data class Exposure(val exposureNs: Long, val iso: Int, val capped: Boolean, val isoSaturated: Boolean)

    /**
     * The nearest whole number of mains half-cycles to [wantedNs], or [wantedNs] when none fits the range.
     *
     * Under manual exposure Camera2's antibanding control does nothing at all, so this is the only thing
     * standing between a tube-lit room and a 100 Hz ripple running through the ROI trace. Whether to take it
     * is the caller's decision, because snapping changes how much light the shutter lets in.
     */
    fun flickerFreeExposure(wantedNs: Long, minNs: Long, maxNs: Long): Long {
        if (FLICKER_STEP_NS < minNs || FLICKER_STEP_NS > maxNs) return wantedNs
        val k = maxOf(1L, Math.round(wantedNs.toDouble() / FLICKER_STEP_NS))
        val snapped = minOf(k * FLICKER_STEP_NS, (maxNs / FLICKER_STEP_NS) * FLICKER_STEP_NS)
        return if (snapped in minNs..maxNs) snapped else wantedNs
    }

    /**
     * [flickerFreeExposure], taken only when the sensitivity left can absorb the change. A flicker-free
     * shutter is worth a gain change; it is not worth a blown-out ROI, which is what forcing 10 ms on a
     * scene that wants 2 ms would give once ISO hits its floor.
     */
    private fun snapIfAffordable(
        wantedNs: Long, light: Double, minNs: Long, maxNs: Long, isoRange: IntRange,
    ): Long {
        val snapped = flickerFreeExposure(wantedNs, minNs, maxNs)
        if (snapped == wantedNs) return wantedNs
        return if ((light / snapped).roundToInt() >= isoRange.first) snapped else wantedNs
    }

    /**
     * Pins the exposure the AE settled on, never longer than [MAX_EXPOSURE_NS] and, where the gain can pay
     * for it, a whole number of mains half-cycles so tube lighting does not beat against the frame rate.
     * Light given up by shortening the shutter is restored by raising sensitivity in the same ratio, so the
     * scene brightness is unchanged; if the sensor cannot go high enough the result is flagged and the clip
     * will be darker than the settle, which the pre-flight then reports.
     */
    fun capExposure(settledExposureNs: Long, settledIso: Int, isoRange: IntRange, exposureRange: LongRange,
                    maxExposureNs: Long = MAX_EXPOSURE_NS): Exposure {
        val exp = settledExposureNs.coerceIn(exposureRange.first, exposureRange.last)
        val ceiling = minOf(maxExposureNs, exposureRange.last)
        val light = exp.toDouble() * settledIso
        val use = snapIfAffordable(minOf(exp, ceiling), light, exposureRange.first, ceiling, isoRange)
        val wantedIso = (light / use).roundToInt()
        val iso = wantedIso.coerceIn(isoRange.first, isoRange.last)
        return Exposure(use, iso, capped = exp > ceiling, isoSaturated = iso < wantedIso)
    }

    /**
     * One proportional correction of a manual exposure so the ROI lands on [TARGET_ROI_LUMA].
     * The ROI luma is sRGB-encoded, so it is linearised first; sensor response is linear in
     * exposure x gain, so the correction factor is applied there. Shutter is adjusted first,
     * within the cap; whatever remains goes to sensitivity.
     */
    fun correctExposure(current: Exposure, roiLuma: Float, isoRange: IntRange, exposureRange: LongRange,
                        maxExposureNs: Long = MAX_EXPOSURE_NS, targetLuma: Float = TARGET_ROI_LUMA): Exposure {
        if (roiLuma <= 0.5f) {
            // Black ROI: no proportional estimate is possible. Open up by a fixed 4x and let the
            // next measurement decide.
            return scale(current, 4.0, isoRange, exposureRange, maxExposureNs)
        }
        val factor = srgbToLinear(targetLuma / 255f) / srgbToLinear((roiLuma / 255f).coerceIn(0f, 1f))
        return scale(current, factor.toDouble(), isoRange, exposureRange, maxExposureNs)
    }

    private fun scale(current: Exposure, factor: Double, isoRange: IntRange, exposureRange: LongRange, maxExposureNs: Long): Exposure {
        val f = factor.coerceIn(0.05, 20.0)
        val expCeiling = minOf(maxExposureNs, exposureRange.last)
        val wantedNs = current.exposureNs * f
        val light = wantedNs * current.iso
        val rounded = wantedNs.roundToLong().coerceIn(exposureRange.first, expCeiling)
        val exp = snapIfAffordable(rounded, light, exposureRange.first, expCeiling, isoRange)
        // Whatever the shutter could not absorb goes to gain.
        val remaining = wantedNs / exp
        val wantedIso = (current.iso * remaining).roundToInt()
        val iso = wantedIso.coerceIn(isoRange.first, isoRange.last)
        return Exposure(exp, iso, capped = wantedNs > expCeiling, isoSaturated = iso < wantedIso)
    }

    // ---- tone curve ------------------------------------------------------------------------

    /**
     * The sRGB opto-electronic transfer function sampled at [points] control points, as the
     * interleaved (in, out) array Camera2's `TONEMAP_CURVE` takes. The ingest inverts sRGB when
     * it linearises the decoded video (`palmppg.ingest.phone.srgb_to_linear`); sending this curve
     * makes that inversion exact instead of approximate, where the vendor's default curve
     * (`TONEMAP_MODE_FAST`) is whatever the ISP tuned and is not recoverable afterwards.
     */
    fun srgbCurve(points: Int = 64): FloatArray {
        require(points >= 2)
        val out = FloatArray(points * 2)
        for (i in 0 until points) {
            val x = i.toFloat() / (points - 1)
            out[2 * i] = x
            out[2 * i + 1] = linearToSrgb(x)
        }
        return out
    }

    fun linearToSrgb(x: Float): Float {
        val v = x.coerceIn(0f, 1f)
        return if (v <= 0.0031308f) 12.92f * v else (1.055f * v.toDouble().pow(1.0 / 2.4) - 0.055).toFloat()
    }

    fun srgbToLinear(y: Float): Float {
        val v = y.coerceIn(0f, 1f)
        return if (v <= 0.04045f) v / 12.92f else ((v + 0.055) / 1.055).pow(2.4).toFloat()
    }

    // ---- colour ----------------------------------------------------------------------------

    /**
     * Means are linear in the pixels they average, so the ROI's mean colour can be converted
     * exactly from the mean Y, U, V. Android's `YUV_420_888` from the camera is full-range BT.601
     * (the JFIF convention, which is also what `ImageProxy.toBitmap` assumes).
     */
    fun yuvMeanToRgb(y: Float, u: Float, v: Float): FloatArray {
        val cb = u - 128f
        val cr = v - 128f
        return floatArrayOf(
            (y + 1.402f * cr).coerceIn(0f, 255f),
            (y - 0.344136f * cb - 0.714136f * cr).coerceIn(0f, 255f),
            (y + 1.772f * cb).coerceIn(0f, 255f),
        )
    }

    // ---- pre-flight ------------------------------------------------------------------------

    data class Reading(
        val roiLuma: Float?,          // mean Y over the ROI, 0-255; null when no analysis frames arrived
        val clipFraction: Float?,     // fraction of ROI pixels >= CLIP_LEVEL
        val fps: Float?,
        val exposureNs: Long,
        val iso: Int,
        val focusRequestedDiopters: Float,
        val focusReportedDiopters: Float?,
        val torchRequested: Boolean,
        val torchLit: Boolean?,       // from FLASH_STATE; null when the HAL does not report it
        val perfusionPct: Double?,    // PulseMeter's AC/DC %, when the live meter ran
    )

    data class Verdict(val ok: Boolean, val warnings: List<String>, val exposureCorrection: Double?) {
        val line: String get() = if (ok) "pre-flight ok" else "pre-flight: " + warnings.joinToString("; ")
    }

    /**
     * Judges the settled state before the clip starts. Nothing here blocks the operator; the
     * verdict is shown, logged into `clip1_meta.json`, and — where a correction is arithmetic —
     * applied once. The ROI being dark is the one that has actually happened on this rig: every
     * clip recorded before this check existed had a near-black ROI, and the app said nothing.
     */
    fun preflight(r: Reading): Verdict {
        val w = mutableListOf<String>()
        var correction: Double? = null

        val luma = r.roiLuma
        if (luma == null) {
            w += "no ROI frames — live readout unavailable, framing unchecked"
        } else {
            if (luma < MIN_ROI_LUMA) {
                w += "ROI dark (Y=${luma.roundToInt()}): palm not over the box or too little light" +
                    if (!r.torchRequested) " — turn the torch on" else ""
                correction = (srgbToLinear(TARGET_ROI_LUMA / 255f) / srgbToLinear((luma / 255f).coerceAtLeast(0.002f))).toDouble()
            } else if (luma > MAX_ROI_LUMA || (r.clipFraction ?: 0f) > MAX_CLIP_FRACTION) {
                w += "ROI too bright (Y=${luma.roundToInt()}, clipped ${((r.clipFraction ?: 0f) * 100).roundToInt()}%): move back or reduce light"
                correction = (srgbToLinear(TARGET_ROI_LUMA / 255f) / srgbToLinear(luma / 255f)).toDouble()
            }
        }
        if (r.exposureNs > MAX_EXPOSURE_NS) {
            w += "exposure ${r.exposureNs / 1_000_000} ms exceeds the ${MAX_EXPOSURE_NS / 1_000_000} ms motion-blur cap"
        }
        if (r.fps != null && r.fps < MIN_FPS) {
            w += "camera delivering %.1f fps, below 30".format(r.fps)
        }
        if (!focusAchieved(r.focusRequestedDiopters, r.focusReportedDiopters)) {
            w += "lens reports %.2f D, requested %.2f D — focus did not land".format(
                r.focusReportedDiopters ?: -1f, r.focusRequestedDiopters)
        }
        if (r.torchRequested && r.torchLit == false) {
            w += "torch requested but the flash is not lit"
        }
        if (r.perfusionPct != null && luma != null && luma >= MIN_ROI_LUMA && r.perfusionPct < 0.05) {
            w += "no pulse in the live trace (perfusion %.2f%%) — palm may be too far or moving".format(r.perfusionPct)
        }
        return Verdict(w.isEmpty(), w, correction)
    }
}
