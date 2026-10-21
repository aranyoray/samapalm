package org.swht.palm

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.sin

/**
 * Writes a reference ATC with the production writer so `palmppg/ecg/atc.py` can be pointed at the
 * real bytes. The structural assertions here are the fast check; the cross-language check is
 * `tools/check_atc_roundtrip.py`, which parses the artefact this test leaves behind.
 */
class AtcWriterTest {

    private val fs = 300
    private val seconds = 10

    /** Deterministic pseudo-ECG in device counts: a sharp R wave on a slow baseline. */
    private fun syntheticCounts(): IntArray {
        val n = fs * seconds
        val beatPeriod = fs * 60 / 72
        return IntArray(n) { i ->
            val phase = (i % beatPeriod).toDouble() / beatPeriod
            val r = 9000.0 * exp(-((phase - 0.12) * 40.0) * ((phase - 0.12) * 40.0))
            val t = 1200.0 * exp(-((phase - 0.38) * 12.0) * ((phase - 0.38) * 12.0))
            val baseline = 200.0 * sin(2.0 * PI * i / (fs * 4.0))
            Math.round(r + t + baseline).toInt()
        }
    }

    @Test
    fun writesFileThatMatchesTheDeclaredLayout() {
        val outDir = File("build/atc-roundtrip").apply { mkdirs() }
        val atc = File(outDir, "kardia_test.atc")
        val counts = syntheticCounts()

        AtcWriter.write(
            file = atc,
            samples = counts,
            fsHz = fs,
            startIso = "2026-10-18T12:00:00.000+0530",
            info = mapOf(
                "phone_model" to "unit test",
                "recorder_sw" to "SamaPalmRecorder 1.0",
                "recorder_hw" to "KardiaMobile Card",
            ),
        )

        // header 8 | info 12+264 | fmt 12+8 | ecg 12+2N
        val expected = 8 + (12 + 264) + (12 + 8) + (12 + counts.size * 2)
        assertEquals(expected.toLong(), atc.length())

        val bytes = atc.readBytes()
        assertEquals("ALIVE", String(bytes, 0, 5, Charsets.US_ASCII))
        assertEquals(1, bytes[5].toInt())

        // the sidecar lets the python check compare sample-for-sample
        File(outDir, "expected_counts.csv").bufferedWriter().use { w ->
            w.write("sample_idx,count\n")
            counts.forEachIndexed { i, c -> w.write("$i,$c\n") }
        }
        assertTrue(File(outDir, "expected_counts.csv").length() > 0)
    }
}
