package org.samahealth.onboarding.quality

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The ECG runs before and after the clip, so the quality grade has to be taken over the clip's own stretch
 * of it. These are the ways `<clip>_sync.json` can fail to give one, each of which must fall back to grading
 * the whole trace rather than throwing or grading nothing.
 */
class ClipWindowTest {

    private fun sync(start: Any?, stop: Any?): String {
        val fields = listOfNotNull(
            start?.let { "\"clip_start_sample_idx\": $it" },
            stop?.let { "\"clip_stop_sample_idx\": $it" },
        ).joinToString(", ")
        return """{"reference_clock": "x", "clip_window": {$fields}}"""
    }

    @Test
    fun `a 60 s clip inside an 80 s record grades only the clip`() {
        // 300 Hz: 10 s lead-in, 60 s clip, 10 s lead-out
        val w = QualityRunner.clipWindow(sync(3_000, 21_000), 24_000)
        assertEquals(3_000 until 21_000, w)
        assertEquals(18_000, w!!.count())
    }

    @Test
    fun `no sync file, no window, so the whole trace is graded`() {
        assertNull(QualityRunner.clipWindow(null, 24_000))
        assertNull(QualityRunner.clipWindow("", 24_000))
    }

    @Test
    fun `a sync file without a clip window is not an error`() {
        assertNull(QualityRunner.clipWindow("""{"reference_clock": "x"}""", 24_000))
        assertNull(QualityRunner.clipWindow(sync(null, null), 24_000))
        assertNull(QualityRunner.clipWindow(sync(3_000, null), 24_000))
    }

    @Test
    fun `malformed json falls back instead of throwing`() {
        assertNull(QualityRunner.clipWindow("not json at all", 24_000))
        assertNull(QualityRunner.clipWindow("""{"clip_window": 7}""", 24_000))
        assertNull(QualityRunner.clipWindow(sync("\"later\"", "\"sooner\""), 24_000))
    }

    @Test
    fun `a window the record does not contain is clamped`() {
        // the stream started after the encoder, so the clip begins before sample 0
        assertEquals(0 until 18_000, QualityRunner.clipWindow(sync(-3_000, 18_000), 24_000))
        // the stream stalled and died before the clip ended
        assertEquals(3_000 until 24_000, QualityRunner.clipWindow(sync(3_000, 90_000), 24_000))
    }

    @Test
    fun `a window that adds nothing is not applied`() {
        // covers the whole record: grading it is the same work, so leave the trace alone
        assertNull(QualityRunner.clipWindow(sync(0, 24_000), 24_000))
        // empty or inverted: there is no clip to grade, so fall back rather than score zero samples
        assertNull(QualityRunner.clipWindow(sync(5_000, 5_000), 24_000))
        assertNull(QualityRunner.clipWindow(sync(9_000, 2_000), 24_000))
    }
}
