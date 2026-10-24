package org.samahealth.onboarding.quality

import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** BT.601 limited range and the centred ROI, against values worked out by hand. */
class YuvTest {

    private fun close(want: Double, got: Double, tol: Double = 0.6) =
        assertTrue(abs(got - want) <= tol, "expected ~$want, got $got")

    @Test
    fun limitedRangeBlackAndWhiteMapToTheFullRange() {
        // Y 16 is black and Y 235 is white in limited range; chroma 128 is neutral
        close(0.0, Yuv.r(16, 128, 128))
        close(0.0, Yuv.g(16, 128, 128))
        close(0.0, Yuv.b(16, 128, 128))
        close(255.0, Yuv.r(235, 128, 128))
        close(255.0, Yuv.g(235, 128, 128))
        close(255.0, Yuv.b(235, 128, 128))
    }

    @Test
    fun chromaPushesTheExpectedChannel() {
        // V above neutral is the red difference, U above neutral the blue difference
        val mid = Yuv.r(126, 128, 128)
        assertTrue(Yuv.r(126, 128, 200) > mid, "V above neutral must raise red")
        assertTrue(Yuv.b(126, 200, 128) > Yuv.b(126, 128, 128), "U above neutral must raise blue")
        assertTrue(Yuv.g(126, 200, 200) < Yuv.g(126, 128, 128), "both differences lower green")
    }

    @Test
    fun everyChannelStaysInsideAByte() {
        for (y in 0..255 step 17) {
            for (u in 0..255 step 51) {
                for (v in 0..255 step 51) {
                    for (x in listOf(Yuv.r(y, u, v), Yuv.g(y, u, v), Yuv.b(y, u, v))) {
                        assertTrue(x in 0.0..255.0, "channel out of range: $x at ($y,$u,$v)")
                    }
                }
            }
        }
    }

    @Test
    fun theRoiIsTheCentredFractionOfTheFrame() {
        // 40 % of 640x360, centred: 256 x 144 starting at (192, 108)
        val r = Yuv.roiRect(640, 360, 0.40f)
        assertEquals(listOf(192, 108, 448, 252), r.toList())
        assertEquals(256, r[2] - r[0])
        assertEquals(144, r[3] - r[1])
    }

    @Test
    fun theRoiIsNeverEmptyEvenOnATinyFrame() {
        for ((w, h) in listOf(2 to 2, 1 to 1, 16 to 9, 1920 to 1080)) {
            val r = Yuv.roiRect(w, h, 0.40f)
            assertTrue(r[2] > r[0] && r[3] > r[1], "empty ROI for ${w}x$h: ${r.toList()}")
            assertTrue(r[0] >= 0 && r[1] >= 0 && r[2] <= w && r[3] <= h, "ROI outside ${w}x$h")
        }
    }

    @Test
    fun frameStatsAverageTheRoiAndCountClippedPixels() {
        val st = FrameStats()
        st.add(16, 128, 128, 0)                 // black
        st.add(235, 128, 128, 1)                // limited-range white, still below the clip level
        st.add(250, 128, 128, 2)                // clipped
        assertEquals(3, st.n)
        assertEquals(1, st.clipped, "only 250 reaches the clip level ${Yuv.CLIP_LEVEL}")
        assertEquals((16 + 235 + 250) / 3.0, st.sy / st.n, 1e-9)
        val grid = st.grid()
        assertEquals(16.0, grid[0], 1e-9)
        assertEquals(0.0, grid[8], 1e-9)        // no pixel fell in that cell
    }
}
