package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import java.math.BigDecimal
import java.math.RoundingMode

data class Cell(val key: String, val label: String, val target: Int)

data class Group(val id: String, val label: String, val weight: Double, val cells: List<Cell>)

data class Targets(val version: String, val note: String, val high: Double, val medium: Double, val groups: List<Group>)

data class Reason(val key: String, val label: String, val group: String, val n: Int, val target: Int, val contribution: Double)

/** level: none | met | high | medium | low */
data class Priority(val score: Double, val level: String, val reasons: List<Reason>)

data class CellRow(val group: String, val key: String, val label: String, val n: Int, val target: Int, val fill: Double)

class TargetsException(msg: String) : IllegalArgumentException(msg)

/**
 * Recruitment targets and the live priority of a candidate (design section 3); identical to palmppg/core/strata.py
 * and pinned by configs/crf_fixtures/strata_golden.json. See that module's docstring for the rule.
 */
object Strata {
    const val MAX_REASONS = 3

    /** Parse and validate configs/recruitment_targets.json (or the server's copy); throws listing every problem. */
    fun parseTargets(json: String): Targets {
        val root = CrfJson.parseToJsonElement(json).jsonObject
        val problems = ArrayList<String>()
        val levels = root["levels"] as? JsonObject
        val high = num(levels?.get("high"))
        val medium = num(levels?.get("medium"))
        if (high == null || medium == null) problems.add("levels must give numbers for high and medium")
        else if (!(0.0 <= medium && medium <= high && high <= 1.0)) problems.add("levels must satisfy 0 <= medium <= high <= 1")
        val groupsJson = root["groups"] as? JsonArray
        if (groupsJson == null || groupsJson.isEmpty()) throw TargetsException((problems + "groups must be a non-empty list").joinToString("; "))
        val keys = HashSet<String>()
        val ids = HashSet<String>()
        val groups = ArrayList<Group>()
        for ((i, ge) in groupsJson.withIndex()) {
            val g = ge as? JsonObject
            val gid = str(g?.get("id"))
            val where = "group ${gid?.takeIf { it.isNotEmpty() } ?: i}"
            if (gid.isNullOrEmpty()) problems.add("$where: id missing") else if (!ids.add(gid)) problems.add("$where: duplicate group id")
            if (g == null) continue
            val w = num(g["weight"])
            if (w == null || w < 0.0 || w > 1.0) problems.add("$where: weight must be a number in [0, 1], got ${g["weight"]}")
            val cellsJson = g["cells"] as? JsonArray
            if (cellsJson == null || cellsJson.isEmpty()) { problems.add("$where: cells must be a non-empty list"); continue }
            val cells = ArrayList<Cell>()
            for (ce in cellsJson) {
                val c = ce as? JsonObject
                val key = str(c?.get("key"))
                if (key.isNullOrEmpty()) { problems.add("$where: cell without a key"); continue }
                if (!keys.add(key)) problems.add("$where: duplicate cell key $key")
                val t = c!!["target"]
                if (!isInt(t) || num(t)!! <= 0) { problems.add("$where: cell $key: target must be a whole number > 0, got $t"); continue }
                cells.add(Cell(key, str(c["label"]) ?: key, num(t)!!.toInt()))
            }
            groups.add(Group(gid ?: "", str(g["label"]) ?: (gid ?: ""), w ?: 0.0, cells))
        }
        if (problems.isNotEmpty()) throw TargetsException(problems.joinToString("; "))
        return Targets(str(root["version"]) ?: "", str(root["note"]) ?: "", high!!, medium!!, groups)
    }

    private class Row(val group: Group, val cell: Cell, val n: Int) {
        val deficit: Double = maxOf(0.0, 1.0 - n.toDouble() / cell.target.toDouble())
        val contribution: Double = group.weight * deficit
        fun reason() = Reason(cell.key, cell.label, group.id, n, cell.target, round3(contribution))
    }

    /** Python round(x, 3): half-even on the exact binary value. */
    fun round3(x: Double): Double = BigDecimal(x).setScale(3, RoundingMode.HALF_EVEN).toDouble()

    private fun rows(counts: Map<String, Int>, targets: Targets): List<Row> =
        targets.groups.flatMap { g -> g.cells.map { c -> Row(g, c, counts[c.key] ?: 0) } }

    private fun ranked(rows: List<Row>): List<Row> = rows.sortedWith(compareByDescending<Row> { it.contribution }.thenBy { it.key() })

    private fun Row.key() = cell.key

    fun priority(keys: List<String>, counts: Map<String, Int>, targets: Targets): Priority {
        val ks = keys.toSet()
        val matched = rows(counts, targets).filter { it.cell.key in ks }
        if (matched.isEmpty()) return Priority(0.0, "none", emptyList())
        val score = matched.maxOf { it.contribution }
        val level = when {
            matched.all { it.deficit == 0.0 } -> "met"
            score >= targets.high -> "high"
            score >= targets.medium -> "medium"
            else -> "low"
        }
        return Priority(score, level, ranked(matched).take(MAX_REASONS).map { it.reason() })
    }

    /** Dashboard rows in file order; fill = min(1, n / target). */
    fun cellTable(counts: Map<String, Int>, targets: Targets): List<CellRow> =
        rows(counts, targets).map { r -> CellRow(r.group.id, r.cell.key, r.cell.label, r.n, r.cell.target, minOf(1.0, r.n.toDouble() / r.cell.target.toDouble())) }

    /** The k cells a new participant would help most; full and weight-0 cells are left out. */
    fun mostNeeded(counts: Map<String, Int>, targets: Targets, k: Int = 5): List<Reason> =
        ranked(rows(counts, targets).filter { it.contribution > 0.0 }).take(k).map { it.reason() }
}
