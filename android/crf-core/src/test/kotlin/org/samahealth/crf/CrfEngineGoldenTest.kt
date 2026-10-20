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
        assertTrue(cases.size >= 10)
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
                assertJsonEquals(full["identity"], ex.identity, "$name identity")
            } catch (e: AssertionError) {
                failures.add(e.message ?: name)
            }
        }
        if (failures.isNotEmpty()) fail(failures.joinToString("\n"))
    }

    @Test
    fun identityNeverReachesTheCrf() {
        val engine = CrfEngine.fromJson(schemaText)
        val c = golden["cases"]!!.jsonArray.first { str(it.jsonObject["name"]) == "complete_male_1x60" }.jsonObject
        val ex = engine.export(c["answers"]!!.jsonObject, now = OffsetDateTime.parse(str(c["now"])!!))
        for (k in listOf("name", "phone", "hospital_reg_no")) {
            assertTrue(k !in ex.crf, "$k leaked into the CRF")
            assertTrue(k in ex.identity)
        }
        assertEquals("RKD", str(ex.crf["initials"]))
    }
}
