package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import java.io.File
import java.time.OffsetDateTime
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class CoreUnitTest {
    private val schemaText = File(System.getProperty("crf.schema")).readText()

    @Test
    fun pidBlocksNeverOverlapAndSkipUsed() {
        val a = PidAllocator()
        assertEquals("SWHT-PP-003-0001", a.next(1, 999, emptyList()))
        assertEquals("SWHT-PP-003-0003", a.next(1, 999, listOf("SWHT-PP-003-0001", "SWHT-PP-003-0002", "OTHER")))
        assertEquals("SWHT-PP-003-1000", a.next(1000, 1999, listOf("SWHT-PP-003-0001")))
        assertNull(a.next(5, 6, listOf("SWHT-PP-003-0005", "SWHT-PP-003-0006")))
        assertTrue(a.inBlock("SWHT-PP-003-1500", 1000, 1999))
        assertFalse(a.inBlock("SWHT-PP-003-15000", 1000, 1999))
        assertNull(a.parse("SWHT-PP-003-12a4"))
    }

    @Test
    fun valueEqualityFollowsPython() {
        assertTrue(valueEquals(JsonPrimitive(7), JsonPrimitive(7.0)))
        assertFalse(valueEquals(JsonPrimitive("7"), JsonPrimitive(7)))
        assertFalse(valueEquals(JsonPrimitive(true), JsonPrimitive(1)))
        assertTrue(answered(JsonArray(listOf(JsonPrimitive("x")))))
        assertFalse(answered(JsonPrimitive("  ")))
        assertEquals(24.8, Derive.round1(24.80272))
        assertEquals(0.2, Derive.round1(0.25))   // half-even on the exact binary value, like Python round()
    }

    @Test
    fun navigatorBlocksOnErrorsFollowsBranchesAndLogsScreens() {
        var t = OffsetDateTime.parse("2026-10-20T10:00:00+05:30")
        val nav = SurveyNavigator(CrfEngine.fromJson(schemaText), clock = { t })
        assertEquals("enrolment", nav.current)
        assertFalse(nav.next(), "empty enrolment must not advance")
        nav.set("study_id", JsonPrimitive("SWHT-PP-003-0007"))
        nav.set("consent", JsonPrimitive("yes"))
        nav.set("dept", JsonPrimitive("ANC (OBG)"))
        assertTrue(nav.next())
        assertEquals("identity", nav.current)
        nav.set("name", JsonPrimitive("Mita Roy"))
        assertTrue(nav.next())
        nav.set("bp1", SurveyNavigator.bp(118, 76, 88, "2026-10-20T10:01:00+05:30"))
        assertTrue(nav.next())
        assertEquals("demographics", nav.current)
        for ((k, v) in mapOf("age" to 26, "height_cm" to 155, "weight_kg" to 58)) nav.set(k, JsonPrimitive(v))
        nav.set("sex", JsonPrimitive("F")); nav.set("pregnant", JsonPrimitive("yes"))
        nav.set("handedness", JsonPrimitive("right")); nav.set("cuff_size", JsonPrimitive("adult"))
        t = t.plusMinutes(2)
        assertTrue(nav.next())
        assertEquals("pregnancy", nav.current, "pregnant women see the antenatal screen next")
        nav.set("pregnant", JsonPrimitive("no"))
        assertTrue("pregnancy" !in nav.visibleScreens())
        assertTrue(nav.back())
        assertEquals("demographics", nav.current)
        assertTrue(nav.screenLog.size >= 5 && nav.screenLog.dropLast(1).all { it.leftAt != null })
        nav.set("consent", JsonPrimitive("no"))
        assertEquals("screen_fail", nav.submissionStatus())
    }

    @Test
    fun resumeRestoresScreenAndLog() {
        val t = OffsetDateTime.parse("2026-10-20T10:00:00+05:30")
        val a = SurveyNavigator(CrfEngine.fromJson(schemaText), clock = { t })
        a.set("study_id", JsonPrimitive("SWHT-PP-003-0009")); a.set("consent", JsonPrimitive("yes")); a.set("dept", JsonPrimitive("Cardio OPD"))
        assertTrue(a.next())
        val saved = a.screenLogJson()
        val b = SurveyNavigator(a.engine, a.answers, clock = { t })
        assertTrue(b.resume("identity", SurveyNavigator.parseLog(saved)))
        assertEquals("identity", b.current)
        assertEquals(listOf("enrolment", "identity", "identity"), b.screenLog.map { it.screen })
        assertFalse(b.resume("pregnancy"), "a hidden screen cannot be resumed")
    }
}
