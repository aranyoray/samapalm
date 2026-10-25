package org.samahealth.onboarding.recorder

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The parts of the Kardia recovery ladder that are arithmetic rather than GATT: which rung a given
 * stretch of silence should have reached, and which mode to try when the one in use has gone quiet.
 * The rungs themselves (re-send, switch mode, re-subscribe, reconnect) need a real device.
 */
class BleKardiaRecoveryTest {

    @Test
    fun `a live stream never leaves rung zero`() {
        assertEquals(0, BleKardia.rungForSilence(0))
        assertEquals(0, BleKardia.rungForSilence(BleKardia.RUNG_MS - 1))
    }

    @Test
    fun `silence climbs one rung at a time`() {
        assertEquals(1, BleKardia.rungForSilence(BleKardia.RUNG_MS))
        assertEquals(2, BleKardia.rungForSilence(2 * BleKardia.RUNG_MS))
        assertEquals(3, BleKardia.rungForSilence(3 * BleKardia.RUNG_MS))
        // the cheap pokes are all tried before the link is torn down
        assertTrue("reconnect must not come before 9 s", BleKardia.rungForSilence(8_999) < 4)
        assertEquals(4, BleKardia.rungForSilence(4 * BleKardia.RUNG_MS))
    }

    @Test
    fun `the mode toggle alternates and defaults to M2`() {
        assertEquals("M1", BleKardia.otherMode("M2"))
        assertEquals("M2", BleKardia.otherMode("M1"))
        // nothing has been sent yet, so there is nothing to switch away from
        assertEquals("M2", BleKardia.otherMode(null))
    }

    @Test
    fun `the unlock token is the device name, not a constant`() {
        val a = BleKardia.unlockToken("KardiaMobile_1234")
        val b = BleKardia.unlockToken("KardiaMobile_5678")
        assertEquals(17, a.length)
        assertTrue(a.startsWith("K"))
        assertTrue("a nudge must re-derive the token per device", a != b)
        // a re-send has to produce the same token or the device ignores it
        assertEquals(a, BleKardia.unlockToken("KardiaMobile_1234"))
    }
}
