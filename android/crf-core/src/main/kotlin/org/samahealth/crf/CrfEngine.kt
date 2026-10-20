package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import java.time.OffsetDateTime
import java.time.ZoneId

data class Issue(val q: String, val code: String, val message: String, val screen: String) {
    val key: String get() = "$q:$code"
}

data class Evaluation(
    val visibleScreens: List<String>,
    val visibleQuestions: Map<String, List<String>>,
    val effective: Map<String, JsonElement>,
    val derived: Map<String, JsonElement>,
    val errors: List<Issue>,
    val warnings: List<Issue>,
    val stopped: Issue?,
) {
    fun errorsOn(screen: String): List<Issue> = errors.filter { it.screen == screen }
}

data class Exported(val crf: JsonObject, val identity: JsonObject)

/**
 * Schema-driven CRF engine; semantics are identical to palmppg/core/crf_schema.py and are pinned by the shared
 * golden fixtures (configs/crf_fixtures/golden.json). See that module's docstring for the rules.
 */
class CrfEngine(val schema: JsonObject, settingsOverrides: Map<String, JsonElement> = emptyMap()) {
    val settings: Map<String, JsonElement> =
        LinkedHashMap<String, JsonElement>().apply {
            schema["settings_defaults"]?.jsonObject?.let { putAll(it) }
            putAll(settingsOverrides)
        }
    val schemaVersion: String = str(schema["schema_version"]) ?: "unknown"
    val screens: Map<String, JsonObject> = schema["screens"]!!.jsonArray.associate { s -> str(s.jsonObject["id"])!! to s.jsonObject }
    /** question id -> (screen id, question) */
    val questions: Map<String, Pair<String, JsonObject>>
    private val pidRe = Regex(str(schema["pid_pattern"])!!)

    init {
        val q = LinkedHashMap<String, Pair<String, JsonObject>>()
        for ((sid, s) in screens) for (qe in s["questions"]!!.jsonArray) {
            val qo = qe.jsonObject
            val id = str(qo["id"])!!
            require(id !in q) { "duplicate question id $id" }
            q[id] = sid to qo
        }
        questions = q
    }

    fun flow(): List<String> {
        val plan = str(settings["clip_plan"])
        val flows = schema["flows"]!!.jsonObject
        val f = flows[plan] ?: throw IllegalArgumentException("unknown clip_plan $plan; schema flows: ${flows.keys.sorted()}")
        return f.jsonArray.map { str(it)!! }
    }

    fun question(id: String): JsonObject = questions[id]?.second ?: throw IllegalArgumentException("unknown question $id")

    fun type(q: JsonObject): String = str(q["type"])!!

    fun choices(q: JsonObject): List<Pair<String, String>> {
        val ch = q["choices"] ?: return emptyList()
        val lst = if (ch is JsonPrimitive) schema["choices"]!!.jsonObject[ch.content]!!.jsonArray else ch.jsonArray
        return lst.map { str(it.jsonObject["value"])!! to (str(it.jsonObject["label"]) ?: str(it.jsonObject["value"])!!) }
    }

    fun choiceValues(q: JsonObject): List<String> = choices(q).map { it.first }

    fun resolveDefault(q: JsonObject): JsonElement? {
        val d = q["default"] ?: return null
        val s = str(d)
        if (s != null && s.startsWith("\$settings.")) return settings[s.removePrefix("\$settings.")]
        return d
    }

    fun initialAnswers(): Map<String, JsonElement> =
        questions.values.mapNotNull { (_, q) -> resolveDefault(q)?.takeIf { it !is JsonNull }?.let { str(q["id"])!! to it } }.toMap()

    fun evaluate(answers: Map<String, JsonElement>, now: OffsetDateTime = OffsetDateTime.now(ZoneId.systemDefault())): Evaluation {
        val effective = LinkedHashMap<String, JsonElement>()
        val visScreens = ArrayList<String>()
        val visQ = LinkedHashMap<String, List<String>>()
        for (sid in flow()) {
            val s = screens[sid]!!
            if (!Conditions.eval(s["show_if"], effective, settings, Derive.derive(effective, settings, now))) continue
            visScreens.add(sid)
            val qs = ArrayList<String>()
            for (qe in s["questions"]!!.jsonArray) {
                val q = qe.jsonObject
                val id = str(q["id"])!!
                if (!Conditions.eval(q["show_if"], effective, settings, Derive.derive(effective, settings, now))) continue
                qs.add(id)
                val v = answers[id]
                if (type(q) !in NO_VALUE_TYPES && answered(v)) effective[id] = v!!
            }
            visQ[sid] = qs
        }
        val der = Derive.derive(effective, settings, now)
        val errors = ArrayList<Issue>()
        val warnings = ArrayList<Issue>()
        var stopped: Issue? = null
        for (sid in visScreens) for (id in visQ[sid]!!) {
            val q = question(id)
            for ((code, msg) in check(q, effective, der, now)) errors.add(Issue(id, code, msg, sid))
            q["stop_if"]?.let {
                if (Conditions.eval(it, effective, settings, der)) {
                    val iss = Issue(id, "stop", str(q["stop_message"]) ?: "stop", sid)
                    errors.add(iss)
                    if (stopped == null) stopped = iss
                }
            }
            q["warn_if"]?.let {
                if (Conditions.eval(it, effective, settings, der)) warnings.add(Issue(id, "warn", str(q["warn_message"]) ?: "", sid))
            }
        }
        return Evaluation(visScreens, visQ, effective, der, errors, warnings, stopped)
    }

    private fun check(q: JsonObject, eff: Map<String, JsonElement>, der: Map<String, JsonElement>, now: OffsetDateTime): List<Pair<String, String>> {
        val t = type(q)
        val id = str(q["id"])!!
        if (t in NO_VALUE_TYPES) return emptyList()
        val v = eff[id]
        val req = bool(q["required"]) == true || (q["required_if"]?.let { Conditions.eval(it, eff, settings, der) } ?: false)
        if (!answered(v)) return if (req) listOf("required" to "required") else emptyList()
        val out = ArrayList<Pair<String, String>>()
        if ((t == "integer" || t == "mst") && !isInt(v)) return listOf("type" to "whole number expected")
        if (t == "decimal" && !isNum(v)) return listOf("type" to "number expected")
        when (t) {
            "integer", "decimal", "mst" -> {
                val x = num(v)!!
                num(q["min"])?.let { if (x < it) out.add("min" to "minimum ${q["min"]}") }
                num(q["max"])?.let { if (x > it) out.add("max" to "maximum ${q["max"]}") }
            }
            "single" -> if (str(v) == null || str(v) !in choiceValues(q)) out.add("choice" to "not one of the listed options")
            "multi" -> {
                val vals = choiceValues(q)
                val arr = v as? JsonArray
                if (arr == null || arr.any { str(it) == null || str(it) !in vals }) {
                    out.add("choice" to "not one of the listed options")
                } else {
                    val excl = q["exclusive"]?.jsonArray?.map { str(it) } ?: emptyList()
                    if (arr.any { str(it) in excl } && arr.size > 1) out.add("exclusive" to "this option cannot be combined with others")
                }
            }
            "pid" -> if (str(v) == null || !pidRe.containsMatchIn(str(v)!!)) out.add("pattern" to "PID format SWHT-PP-003-####")
            "text" -> str(q["pattern"])?.let { p ->
                val s = str(v) ?: (v as JsonPrimitive).content
                if (!Regex(p).matches(s)) out.add("pattern" to "format not recognised")
            }
            "date" -> {
                val d = parseDate(v)
                if (d == null) out.add("date" to "date as YYYY-MM-DD")
                else if (d.isAfter(now.toLocalDate())) out.add("future" to "date is in the future")
            }
            "bp" -> out.addAll(checkBp(v))
            "clip" -> out.addAll(checkClip(v))
        }
        return out
    }

    private fun checkBp(v: JsonElement?): List<Pair<String, String>> {
        val o = v as? JsonObject ?: return listOf("type" to "reading expected")
        for ((k, lim) in BP_LIMITS) {
            val x = o[k]
            if (!isInt(x) || num(x)!! < lim.first || num(x)!! > lim.second) {
                return listOf("bp_range" to "$k must be a whole number in ${lim.first}-${lim.second}")
            }
        }
        if (num(o["sbp"])!! <= num(o["dbp"])!!) return listOf("bp_order" to "SBP must exceed DBP")
        if (parseTs(o["wall_ts"]) == null) return listOf("bp_time" to "reading time missing")
        return emptyList()
    }

    private fun checkClip(v: JsonElement?): List<Pair<String, String>> {
        val o = v as? JsonObject ?: return listOf("type" to "clip record expected")
        val a = parseTs(o["started_at"])
        val b = parseTs(o["ended_at"])
        if (a == null || b == null || str(o["quality"]) !in listOf("pass", "fail")) return listOf("clip_incomplete" to "start, end and quality are needed")
        if (!b.isAfter(a)) return listOf("clip_order" to "end must be after start")
        return emptyList()
    }

    /** (CRF record, identity record). The CRF never contains identity-store answers (name and PID kept apart). */
    fun export(answers: Map<String, JsonElement>, context: Map<String, JsonElement> = emptyMap(), identityName: String? = null,
               now: OffsetDateTime = OffsetDateTime.now(ZoneId.systemDefault())): Exported {
        val ev = evaluate(answers, now)
        val crf = LinkedHashMap<String, JsonElement>()
        val ident = LinkedHashMap<String, JsonElement>()
        for (sid in ev.visibleScreens) for (id in ev.visibleQuestions[sid]!!) {
            val q = question(id)
            val t = type(q)
            val key = str(q["export_key"]) ?: id
            if (t == "computed") {
                val dv = ev.derived[str(q["compute"]) ?: id]
                if (bool(q["export"]) == true && dv != null && dv !is JsonNull) crf[key] = dv
                continue
            }
            if (t == "info" || id !in ev.effective) continue
            var v = ev.effective[id]!!
            if (str(q["store"]) == "identity") { ident[id] = v; continue }
            if (bool(q["export"]) == false) continue
            if (str(q["export_as"]) == "bool_yes_no") v = when (str(v)) { "yes" -> JsonPrimitive(true); "no" -> JsonPrimitive(false); else -> JsonNull }
            crf[key] = v
        }
        val name = identityName ?: str(ident["name"])
        if (!name.isNullOrBlank()) crf["initials"] = JsonPrimitive(Derive.initials(name))
        ident["pid"] = ev.effective["study_id"] ?: JsonNull
        for ((k, v) in context) if (v !is JsonNull) crf[k] = v
        crf["schema_version"] = JsonPrimitive(schemaVersion)
        crf["clip_plan"] = settings["clip_plan"] ?: JsonNull
        return Exported(JsonObject(crf), JsonObject(ident))
    }

    /** Static checks mirrored from Python `lint_schema`. */
    fun lint(): List<String> {
        val problems = ArrayList<String>()
        for ((id, p) in questions) {
            val q = p.second
            val ch = q["choices"]
            if (ch is JsonPrimitive && schema["choices"]!!.jsonObject[ch.content] == null) problems.add("$id: unknown choice list ${ch.content}")
            if (type(q) == "computed" && str(q["compute"]) !in Derive.KNOWN) problems.add("$id: unknown derivation ${q["compute"]}")
        }
        for ((plan, order) in schema["flows"]!!.jsonObject) {
            val before = HashSet<String>()
            for (sidE in order.jsonArray) {
                val sid = str(sidE)!!
                val s = screens[sid] ?: run { problems.add("flow $plan: unknown screen $sid"); null } ?: continue
                for (r in Conditions.refs(s["show_if"])) if (r !in before) problems.add("flow $plan: screen $sid show_if refers to $r")
                val sameScreen = s["questions"]!!.jsonArray.map { str(it.jsonObject["id"])!! }.toSet()
                for (qe in s["questions"]!!.jsonArray) {
                    val q = qe.jsonObject
                    for (r in Conditions.refs(q["show_if"])) if (r !in before) problems.add("flow $plan: ${q["id"]} show_if refers to $r")
                    for (r in Conditions.refs(q["required_if"])) if (r !in before && r !in sameScreen) problems.add("flow $plan: ${q["id"]} required_if refers to $r")
                    before.add(str(q["id"])!!)
                }
            }
        }
        return problems
    }

    companion object {
        val NO_VALUE_TYPES = setOf("computed", "info")
        val BP_LIMITS = linkedMapOf("sbp" to (50 to 300), "dbp" to (20 to 200), "hr" to (20 to 250))

        fun fromJson(text: String, settings: Map<String, JsonElement> = emptyMap()): CrfEngine =
            CrfEngine(CrfJson.parseToJsonElement(text).jsonObject, settings)
    }
}
