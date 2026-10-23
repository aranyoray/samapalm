package org.samahealth.onboarding.recorder

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The numbers [PalmRecorderActivity] sends to the camera, checked against the OnePlus 12 main sensor's real
 * limits: closest focus 7.69 D (13.0 cm), ISO 100-6400, exposure 105 us to 54 s.
 */
class PalmControlsTest {

    private val isoRange = 100..6400
    private val exposureRange = 105_042L..54_204_790_072L
    private val mainLensMinFocus = 7.6923075f

    @Test
    fun `focus distance is one over metres and the default sits inside the rig band`() {
        assertEquals(100f / 17f, PalmControls.diopters(17f), 1e-4f)
        assertEquals(20f, PalmControls.centimetres(5f), 1e-4f)
        val f = PalmControls.focusFor(PalmControls.DEFAULT_DISTANCE_CM, mainLensMinFocus)
        assertFalse(f.clampedToLens)
        assertTrue(f.appliedDiopters in 5.0f..6.67f)   // 15-20 cm band
    }

    @Test
    fun `a palm closer than the lens can focus is pinned at the limit and flagged`() {
        val f = PalmControls.focusFor(10f, mainLensMinFocus)   // 10 cm = 10 D, lens stops at 7.69 D
        assertTrue(f.clampedToLens)
        assertEquals(mainLensMinFocus, f.appliedDiopters, 1e-5f)
        assertEquals(10f, f.requestedDiopters, 1e-5f)
    }

    @Test
    fun `an unknown lens limit means no clamping`() {
        val f = PalmControls.focusFor(10f, null)
        assertFalse(f.clampedToLens)
        assertEquals(10f, f.appliedDiopters, 1e-5f)
    }

    @Test
    fun `focus is achieved only when the lens reports close to the request`() {
        assertTrue(PalmControls.focusAchieved(5.88f, 5.7f))
        assertFalse(PalmControls.focusAchieved(5.88f, 2.0f))
        assertFalse(PalmControls.focusAchieved(5.88f, null))
        assertFalse(PalmControls.focusAchieved(5.88f, -1f))
    }

    @Test
    fun `an exposure inside the cap is kept exactly`() {
        val e = PalmControls.capExposure(9_998_229L, 130, isoRange, exposureRange)
        assertEquals(9_998_229L, e.exposureNs)
        assertEquals(130, e.iso)
        assertFalse(e.capped)
    }

    @Test
    fun `a long exposure is capped and the lost light moved into sensitivity`() {
        // The 18 Oct dry run: 29.99 ms at ISO 6400 - already at max gain, so the cap must be
        // honest about the brightness it cannot restore.
        val e = PalmControls.capExposure(29_994_687L, 6400, isoRange, exposureRange)
        assertEquals(PalmControls.MAX_EXPOSURE_NS, e.exposureNs)
        assertTrue(e.capped)
        assertTrue(e.isoSaturated)
        assertEquals(6400, e.iso)

        // Same shutter at ISO 400: gain has room, so brightness is preserved exactly.
        val f = PalmControls.capExposure(24_000_000L, 400, isoRange, exposureRange)
        assertEquals(PalmControls.MAX_EXPOSURE_NS, f.exposureNs)
        assertEquals(800, f.iso)
        assertFalse(f.isoSaturated)
    }

    @Test
    fun `correction opens up a dark ROI and closes down a hot one`() {
        val start = PalmControls.Exposure(4_000_000L, 200, capped = false, isoSaturated = false)
        val dark = PalmControls.correctExposure(start, roiLuma = 20f, isoRange, exposureRange)
        assertTrue(dark.exposureNs * dark.iso.toLong() > start.exposureNs * start.iso.toLong())
        assertTrue(dark.exposureNs <= PalmControls.MAX_EXPOSURE_NS)

        val hot = PalmControls.correctExposure(start, roiLuma = 245f, isoRange, exposureRange)
        assertTrue(hot.exposureNs * hot.iso.toLong() < start.exposureNs * start.iso.toLong())
        assertTrue(hot.iso >= isoRange.first)
    }

    @Test
    fun `a black ROI gets a fixed opening rather than a divide by zero`() {
        val start = PalmControls.Exposure(2_000_000L, 100, capped = false, isoSaturated = false)
        val e = PalmControls.correctExposure(start, roiLuma = 0f, isoRange, exposureRange)
        assertEquals(8_000_000L, e.exposureNs)
        assertEquals(100, e.iso)
    }

    @Test
    fun `the sRGB curve is monotonic with exact endpoints and round-trips`() {
        val c = PalmControls.srgbCurve(64)
        assertEquals(128, c.size)
        assertEquals(0f, c[0], 0f); assertEquals(0f, c[1], 1e-6f)
        assertEquals(1f, c[126], 1e-6f); assertEquals(1f, c[127], 1e-6f)
        for (i in 1 until 64) {
            assertTrue(c[2 * i] > c[2 * (i - 1)])
            assertTrue(c[2 * i + 1] >= c[2 * (i - 1) + 1])
        }
        for (x in floatArrayOf(0f, 0.001f, 0.1f, 0.5f, 0.9f, 1f)) {
            assertEquals(x, PalmControls.srgbToLinear(PalmControls.linearToSrgb(x)), 1e-5f)
        }
        // 18% grey encodes to about 118/255 in sRGB.
        assertEquals(118f, PalmControls.linearToSrgb(0.18f) * 255f, 1.5f)
    }

    @Test
    fun `mean colour converts from mean YUV with the full-range BT601 matrix`() {
        val grey = PalmControls.yuvMeanToRgb(128f, 128f, 128f)
        assertEquals(128f, grey[0], 1e-3f); assertEquals(128f, grey[1], 1e-3f); assertEquals(128f, grey[2], 1e-3f)
        val red = PalmControls.yuvMeanToRgb(76.245f, 84.972f, 255f)   // pure red in JFIF YCbCr
        assertEquals(255f, red[0], 1f); assertEquals(0f, red[1], 1.5f); assertEquals(0f, red[2], 1f)
        // Skin under a warm torch: red leads green leads blue.
        val skin = PalmControls.yuvMeanToRgb(150f, 110f, 160f)
        assertTrue(skin[0] > skin[1] && skin[1] > skin[2])
    }

    private fun reading(
        luma: Float? = 140f, clip: Float? = 0f, fps: Float? = 30f, exposureNs: Long = 8_000_000L, iso: Int = 200,
        focusReq: Float = 5.88f, focusRep: Float? = 5.9f, torch: Boolean = true, lit: Boolean? = true, perfusion: Double? = 0.4,
    ) = PalmControls.Reading(luma, clip, fps, exposureNs, iso, focusReq, focusRep, torch, lit, perfusion)

    @Test
    fun `a well set up clip passes pre-flight`() {
        val v = PalmControls.preflight(reading())
        assertTrue(v.ok)
        assertNull(v.exposureCorrection)
        assertEquals("pre-flight ok", v.line)
    }

    @Test
    fun `the dark ROI that every real clip so far had is named and gets a correction`() {
        val v = PalmControls.preflight(reading(luma = 11f, perfusion = 0.0))
        assertFalse(v.ok)
        assertTrue(v.warnings.any { it.startsWith("ROI dark") })
        assertNotNull(v.exposureCorrection)
        assertTrue(v.exposureCorrection!! > 1.0)
        // A dark ROI with no pulse must not also be blamed on perfusion: one cause, one message.
        assertFalse(v.warnings.any { it.contains("perfusion") })
    }

    @Test
    fun `a dark ROI with the torch off says to turn it on`() {
        val v = PalmControls.preflight(reading(luma = 11f, torch = false, lit = null))
        assertTrue(v.warnings.single { it.startsWith("ROI dark") }.contains("turn the torch on"))
    }

    @Test
    fun `clipping, slow frames, missed focus and an unlit torch are each reported`() {
        val v = PalmControls.preflight(reading(luma = 230f, clip = 0.1f, fps = 24f, exposureNs = 30_000_000L,
            focusRep = 1.0f, lit = false))
        assertFalse(v.ok)
        assertEquals(5, v.warnings.size)
        assertTrue(v.exposureCorrection!! < 1.0)
    }

    @Test
    fun `no analysis frames is reported as unchecked framing rather than passed`() {
        val v = PalmControls.preflight(reading(luma = null, clip = null, perfusion = null))
        assertFalse(v.ok)
        assertTrue(v.warnings.single().contains("framing unchecked"))
    }
}
