package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import java.io.File
import java.time.OffsetDateTime
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/** The Kotlin engine must reproduce the Python engine's output on every shared golden case. */
class CrfEngineGoldenTest {
    private val schemaText = File(System.getProperty("crf.schema")).readText()
    private val golden = CrfJson.parseToJsonElement(File(System.getProperty("crf.golden")).readText()).jsonObject

    private fun assertJsonEquals(expected: JsonElement?, actual: JsonElement?, where: String) {
        if (!valueEquals(expected ?: JsonNull, actual ?: JsonNull)) fail("$where: expected $expected, got $actual")
    }

    @Test
    fun schemaVersionMatchesFixtures() {
        val engine = CrfEngine.fromJson(schemaText)
        assertEquals(str(golden["schema_version"]), engine.schemaVersion, "regenerate fixtures: python tools/make_crf_fixtures.py")
        assertEquals(emptyList(), engine.lint())
    }

    @Test
    fun everyGoldenCaseMatches() {
        val cases = golden["cases"]!!.jsonArray
        assertTrue(cases.size >= 24)
        val failures = ArrayList<String>()
        for (ce in cases) {
            val c = ce.jsonObject
            val name = str(c["name"])!!
            try {
                val engine = CrfEngine.fromJson(schemaText, c["settings"]!!.jsonObject)
                val now = OffsetDateTime.parse(str(c["now"])!!)
                val answers = c["answers"]!!.jsonObject
                val ev = engine.evaluate(answers, now)
                val full = c["full"]!!.jsonObject
                assertEquals(full["visible_screens"]!!.jsonArray.map { str(it) }, ev.visibleScreens, "$name visible screens")
                val vq = full["visible_questions"]!!.jsonObject.mapValues { (_, v) -> v.jsonArray.map { str(it)!! } }
                assertEquals(vq, ev.visibleQuestions, "$name visible questions")
                assertEquals(full["errors"]!!.jsonArray.map { str(it) }, ev.errors.map { it.key }.sorted(), "$name errors")
                assertEquals(full["warnings"]!!.jsonArray.map { str(it) }, ev.warnings.map { it.key }.sorted(), "$name warnings")
                assertEquals(str(full["stopped"]), ev.stopped?.q, "$name stopped")
                val derived = ev.derived.filterKeys { it != "rest_elapsed" }
                assertJsonEquals(full["derived"], JsonObject(derived), "$name derived")
                val ctx = mapOf("operator" to JsonPrimitive("op1"), "unit_id" to JsonPrimitive("unit_01"), "app_ver" to JsonPrimitive("test"))
                val ex = engine.export(answers, ctx, now = now)
                assertJsonEquals(full["export"], ex.crf, "$name export")
                assertJsonEquals(full["initial"], JsonObject(engine.initialAnswers()), "$name initial answers")
            } catch (e: AssertionError) {
                failures.add(e.message ?: name)
            }
        }
        if (failures.isNotEmpty()) fail(failures.joinToString("\n"))
    }

    @Test
    fun partAndClipPlanPickTheFlowAndTheExportKeys() {
        val enrol = CrfEngine.fromJson(schemaText, mapOf("clip_plan" to JsonPrimitive("2x30")))
        assertEquals("enrol", enrol.flowKey())
        val scan = CrfEngine.fromJson(schemaText, mapOf("part" to JsonPrimitive("scan"), "clip_plan" to JsonPrimitive("2x30")))
        assertEquals("scan_2x30", scan.flowKey())
        assertEquals(listOf("pid", "s_setup", "bp1", "clip1", "clip1b", "bp2", "clip2", "clip2b", "bp3", "s_review"), scan.flow())
        val c = golden["cases"]!!.jsonArray.first { str(it.jsonObject["name"]) == "complete_male_1x60" }.jsonObject
        val ex = CrfEngine.fromJson(schemaText, c["settings"]!!.jsonObject).export(c["answers"]!!.jsonObject, now = OffsetDateTime.parse(str(c["now"])!!))
        assertEquals("scan", str(ex.crf["part"]))
        assertEquals("1x60", str(ex.crf["clip_plan"]))
        for (k in listOf("name", "phone", "hospital_reg_no", "initials")) assertTrue(k !in ex.crf, "$k in the CRF")
        val bad = CrfEngine.fromJson(schemaText, mapOf("part" to JsonPrimitive("triage")))
        try { bad.flow(); fail("unknown part must raise") } catch (e: IllegalArgumentException) { assertTrue("triage_1x60" in (e.message ?: "")) }
    }

    @Test
    fun lintCatchesConditionOrderAndFlowKeys() {
        val root = CrfJson.parseToJsonElement(schemaText).jsonObject
        val choices = root["choices"]!!.jsonObject
        val reversed = JsonArray(choices["conditions"]!!.jsonArray.reversed())
        val flows = root["flows"]!!.jsonObject
        val broken = JsonObject(root + mapOf(
            "choices" to JsonObject(choices + ("conditions" to reversed)),
            "flows" to JsonObject(flows + ("triage" to flows["enrol"]!!) + ("scan_1x60" to JsonArray(flows["scan_1x60"]!!.jsonArray + JsonPrimitive("e_labs")))),
        ))
        val problems = CrfEngine(broken).lint()
        assertTrue(problems.any { it.startsWith("choices conditions must be") }, problems.toString())
        assertTrue("flow triage: not a part or part_clipplan key" in problems, problems.toString())
        assertTrue("screen e_labs is used by both parts" in problems, problems.toString())
    }
}
