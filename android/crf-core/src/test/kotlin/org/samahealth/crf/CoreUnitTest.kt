package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
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
        var t = OffsetDateTime.parse("2026-10-24T10:00:00+05:30")
        val nav = SurveyNavigator(CrfEngine.fromJson(schemaText), clock = { t })
        assertEquals("pid", nav.current)
        assertFalse(nav.next(), "an empty PID screen must not advance")
        nav.set("study_id", JsonPrimitive("SWHT-PP-003-0007"))
        assertTrue(nav.next())
        assertEquals("e_consent", nav.current)
        nav.set("consent", JsonPrimitive("yes"))
        nav.set("dept", JsonPrimitive("ANC (OBG)"))
        assertEquals("pilot", str(nav.answers["stream"]), "stream pre-filled from settings")
        assertTrue(nav.next())
        assertEquals("e_basics", nav.current)
        for ((k, v) in mapOf("age" to 26, "height_cm" to 155, "weight_kg" to 58, "mst_band" to 8)) nav.set(k, JsonPrimitive(v))
        nav.set("sex", JsonPrimitive("F"))
        assertFalse(nav.next(), "a woman of 18-55 must answer the pregnancy question")
        nav.set("pregnant", JsonPrimitive("yes"))
        assertFalse(nav.next(), "weeks pregnant is required once pregnant is yes")
        nav.set("gestational_age_weeks", JsonPrimitive(20))
        t = t.plusMinutes(2)
        assertTrue(nav.next())
        assertEquals("e_conditions", nav.current)
        nav.set("conditions", JsonArray(listOf(JsonPrimitive("thal"))))
        nav.set("transfusion_3m", JsonPrimitive("no"))
        assertFalse(nav.next(), "thalassaemia follow-ups are required")
        nav.set("thal_type", JsonPrimitive("beta_trait")); nav.set("thal_transfusions", JsonPrimitive("none"))
        assertTrue(nav.next())
        assertEquals("e_labs", nav.current)
        assertTrue("mcv_fl" in nav.evaluation().visibleQuestions["e_labs"]!!, "red-cell indices shown for thalassaemia")
        nav.set("pregnant", JsonPrimitive("no"))
        assertTrue("gestational_age_weeks" !in nav.evaluation().effective, "stale weeks dropped when pregnant changes to no")
        assertTrue(nav.back())
        assertEquals("e_conditions", nav.current)
        assertTrue(nav.screenLog.size >= 5 && nav.screenLog.dropLast(1).all { it.leftAt != null })
        val strata = nav.evaluation().derived["strata"] as JsonArray
        assertEquals(listOf("sex:F", "mst:8", "mstgrp:dark", "cond:thal", "haem:thal_trait"), strata.take(5).map { str(it) })
        val ex = nav.export(mapOf("operator" to JsonPrimitive("op1")))
        assertEquals("enrol", str(ex.crf["part"]))
        assertTrue("clip_plan" !in ex.crf && "screen_log" in ex.crf && "consent" !in ex.crf)
        nav.set("consent", JsonPrimitive("no"))
        assertEquals("screen_fail", nav.submissionStatus())
    }

    @Test
    fun scanNavigatorShowsReshootOnlyAfterAFailedClip() {
        val t = OffsetDateTime.parse("2026-10-24T10:00:00+05:30")
        val engine = CrfEngine.fromJson(schemaText, mapOf("part" to JsonPrimitive("scan")))
        val nav = SurveyNavigator(engine, clock = { t })
        assertEquals("left", str(nav.answers["imaged_hand"]), "imaged hand pre-filled from settings")
        assertEquals(listOf("pid", "s_setup", "bp1", "bp2", "clip1", "bp3", "s_review"), nav.visibleScreens())
        fun clip(q: String, kardia: String) = JsonObject(mapOf("started_at" to JsonPrimitive("2026-10-24T10:07:00+05:30"),
            "ended_at" to JsonPrimitive("2026-10-24T10:08:00+05:30"), "quality" to JsonPrimitive(q), "kardia_determination" to JsonPrimitive(kardia)))
        nav.set("clip1", clip("fail", "unreadable"))
        assertTrue("clip1b" in nav.visibleScreens())
        nav.set("clip1b", clip("pass", "af"))
        assertEquals(listOf("rhythm:af"), (nav.evaluation().derived["scan_strata"] as JsonArray).map { str(it) })
        nav.set("clip1", clip("pass", "nsr"))
        assertTrue("clip1b" !in nav.visibleScreens())
        assertEquals(listOf("rhythm:nsr"), (nav.evaluation().derived["scan_strata"] as JsonArray).map { str(it) })
    }

    @Test
    fun derivationsMatchHandComputedValues() {
        assertEquals("none", Derive.anaemiaGrade(12.0, "F", "no", null))
        assertEquals("mild", Derive.anaemiaGrade(11.99, "F", null, null))
        assertEquals("moderate", Derive.anaemiaGrade(10.9, "M", null, null))
        assertEquals("none", Derive.anaemiaGrade(10.5, "F", "yes", 2))
        assertEquals("mild", Derive.anaemiaGrade(10.5, "F", "yes", 3))
        assertEquals("severe", Derive.anaemiaGrade(6.99, "F", "yes", null))
        assertNull(Derive.anaemiaGrade(9.0, "Other", null, null))
        assertEquals(true, Derive.hplcReflex(null, 26.9))
        assertEquals(false, Derive.hplcReflex(80.0, null))
        assertNull(Derive.hplcReflex(null, null))
        assertEquals(listOf("light", "light", "medium", "medium", "dark", "dark"), listOf(1, 4, 5, 6, 7, 10).map { Derive.mstGroup(it) })
    }

    @Test
    fun resumeRestoresScreenAndLog() {
        val t = OffsetDateTime.parse("2026-10-24T10:00:00+05:30")
        val a = SurveyNavigator(CrfEngine.fromJson(schemaText), clock = { t })
        a.set("study_id", JsonPrimitive("SWHT-PP-003-0009"))
        assertTrue(a.next())
        a.set("consent", JsonPrimitive("yes")); a.set("dept", JsonPrimitive("Cardio OPD"))
        assertTrue(a.next())
        val saved = a.screenLogJson()
        val b = SurveyNavigator(a.engine, a.answers, clock = { t })
        assertTrue(b.resume("e_basics", SurveyNavigator.parseLog(saved)))
        assertEquals("e_basics", b.current)
        assertEquals(listOf("pid", "e_consent", "e_basics", "e_basics"), b.screenLog.map { it.screen })
        assertFalse(b.resume("clip1b"), "a screen outside this part's flow cannot be resumed")
    }
}
