package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlin.test.fail

/** The Kotlin priority must reproduce the Python output (configs/crf_fixtures/strata_golden.json) exactly. */
class StrataGoldenTest {
    private val configs = File(System.getProperty("crf.schema")).parentFile
    private val targetsText = configs.resolve("recruitment_targets.json").readText()
    private val golden = CrfJson.parseToJsonElement(File(System.getProperty("crf.golden")).parentFile.resolve("strata_golden.json").readText()).jsonObject
    private val targets = Strata.parseTargets(targetsText)

    private fun counts(o: JsonObject): Map<String, Int> = o.mapValues { (_, v) -> num(v)!!.toInt() }

    private fun reasons(a: JsonArray): List<Reason> = a.map { e ->
        val o = e.jsonObject
        Reason(str(o["key"])!!, str(o["label"])!!, str(o["group"])!!, num(o["n"])!!.toInt(), num(o["target"])!!.toInt(), num(o["contribution"])!!)
    }

    @Test
    fun fixturesMatchTheTargetsFile() {
        assertEquals(str(golden["targets_version"]), targets.version, "regenerate fixtures: python tools/make_strata_fixtures.py")
    }

    @Test
    fun everyPriorityCaseMatches() {
        val cases = golden["cases"]!!.jsonArray
        assertTrue(cases.size >= 12)
        val failures = ArrayList<String>()
        for (ce in cases) {
            val c = ce.jsonObject
            val name = str(c["name"])
            val exp = c["expected"]!!.jsonObject
            val got = Strata.priority(c["keys"]!!.jsonArray.map { str(it)!! }, counts(c["counts"]!!.jsonObject), targets)
            val want = Priority(num(exp["score"])!!, str(exp["level"])!!, reasons(exp["reasons"]!!.jsonArray))
            if (got != want) failures.add("$name: expected $want, got $got")
        }
        if (failures.isNotEmpty()) fail(failures.joinToString("\n"))
    }

    @Test
    fun cellTablesAndMostNeededMatch() {
        for (te in golden["tables"]!!.jsonArray) {
            val t = te.jsonObject
            val name = str(t["name"])
            val cnt = counts(t["counts"]!!.jsonObject)
            val want = t["cell_table"]!!.jsonArray.map { e ->
                val o = e.jsonObject
                CellRow(str(o["group"])!!, str(o["key"])!!, str(o["label"])!!, num(o["n"])!!.toInt(), num(o["target"])!!.toInt(), num(o["fill"])!!)
            }
            assertEquals(want, Strata.cellTable(cnt, targets), "$name cell table")
            val mn = reasons(t["most_needed"]!!.jsonArray)
            assertEquals(mn, Strata.mostNeeded(cnt, targets, num(t["k"])!!.toInt()), "$name most needed")
        }
    }

    @Test
    fun handComputedPriority() {
        // sex:F 250/1000 -> deficit 0.75; sex_mst:F:7 (weight 0.7) 0/100 -> 0.7; mst:7 200/200 -> 0
        val p = Strata.priority(listOf("sex:F", "mst:7", "sex_mst:F:7"), mapOf("sex:F" to 250, "mst:7" to 200), targets)
        assertEquals("high", p.level)
        assertEquals(0.75, p.score, 1e-12)
        assertEquals(listOf("sex:F", "sex_mst:F:7", "mst:7"), p.reasons.map { it.key })
        assertEquals(listOf(0.75, 0.7, 0.0), p.reasons.map { it.contribution })
        assertEquals("none", Strata.priority(listOf("mstgrp:dark"), emptyMap(), targets).level)
        // 1/3 filled -> contribution 0.6666... reported as 0.667
        assertEquals(0.667, Strata.priority(listOf("haem:thal_trait"), mapOf("haem:thal_trait" to 50), targets).reasons.single().contribution)
    }

    @Test
    fun invalidTargetsAreRejectedWithClearErrors() {
        val dup = """{"levels":{"high":0.5,"medium":0.2},"groups":[{"id":"a","label":"A","weight":1,"cells":[
            {"key":"sex:F","label":"F","target":10},{"key":"sex:F","label":"F2","target":0}]},
            {"id":"b","label":"B","weight":1.5,"cells":[{"key":"sex:M","label":"M","target":5}]}]}"""
        val e = assertFailsWith<TargetsException> { Strata.parseTargets(dup) }
        val msg = e.message ?: ""
        assertTrue("duplicate cell key sex:F" in msg, msg)
        assertTrue("target must be a whole number > 0" in msg, msg)
        assertTrue("group b: weight must be a number in [0, 1]" in msg, msg)
        assertFailsWith<TargetsException> { Strata.parseTargets("""{"levels":{"high":0.2,"medium":0.5},"groups":[]}""") }
    }
}
