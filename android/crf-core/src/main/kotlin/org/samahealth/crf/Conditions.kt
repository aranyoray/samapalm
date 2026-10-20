package org.samahealth.crf

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

class ConditionError(msg: String) : IllegalArgumentException(msg)

/**
 * Condition language of configs/crf_schema.json (Python `eval_condition`):
 * {"all": [...]}, {"any": [...]}, {"not": c}, or a leaf {"q"|"setting"|"derived": key, ["field"], op}.
 * Ops: eq, ne, in, not_in, lt, lte, gt, gte, between, contains, answered.
 */
object Conditions {
    fun eval(cond: JsonElement?, answers: Map<String, JsonElement>, settings: Map<String, JsonElement>,
             derived: Map<String, JsonElement>? = null): Boolean {
        if (cond == null || cond is JsonNull) return true
        val c = cond.jsonObject
        c["all"]?.let { arr -> return arr.jsonArray.all { eval(it, answers, settings, derived) } }
        c["any"]?.let { arr -> return arr.jsonArray.any { eval(it, answers, settings, derived) } }
        c["not"]?.let { return !eval(it, answers, settings, derived) }
        var v: JsonElement? = when {
            "q" in c -> answers[str(c["q"])]
            "setting" in c -> settings[str(c["setting"])]
            "derived" in c -> derived?.get(str(c["derived"]))
            else -> throw ConditionError("condition without a subject: $c")
        }
        if ("field" in c) v = (v as? JsonObject)?.get(str(c["field"]))
        c["eq"]?.let { eq ->
            val b = (eq as? JsonPrimitive)?.takeIf { !it.isString }?.booleanOrNull
            return if (b != null) bool(v) == b else answered(v) && valueEquals(v, eq)
        }
        c["ne"]?.let { return !valueEquals(v ?: JsonNull, it) }
        c["in"]?.let { lst -> return answered(v) && lst.jsonArray.any { valueEquals(v, it) } }
        c["not_in"]?.let { lst -> return answered(v) && lst.jsonArray.none { valueEquals(v, it) } }
        c["contains"]?.let { x -> return v is JsonArray && v.any { valueEquals(it, x) } }
        c["answered"]?.let { return answered(v) == (bool(it) ?: false) }
        val ops = listOf<Pair<String, (Double, Double) -> Boolean>>(
            "lt" to { a, b -> a < b }, "lte" to { a, b -> a <= b }, "gt" to { a, b -> a > b }, "gte" to { a, b -> a >= b })
        for ((op, fn) in ops) {
            c[op]?.let { lim -> return isNum(v) && fn(num(v)!!, num(lim)!!) }
        }
        c["between"]?.let { b ->
            val lo = num(b.jsonArray[0])!!
            val hi = num(b.jsonArray[1])!!
            return isNum(v) && num(v)!! in lo..hi
        }
        throw ConditionError("unknown condition operator: $c")
    }

    /** Question ids a condition refers to (for the schema lint). */
    fun refs(cond: JsonElement?): List<String> {
        if (cond == null || cond is JsonNull) return emptyList()
        val c = cond.jsonObject
        c["all"]?.let { return it.jsonArray.flatMap { x -> refs(x) } }
        c["any"]?.let { return it.jsonArray.flatMap { x -> refs(x) } }
        c["not"]?.let { return refs(it) }
        return listOfNotNull(str(c["q"]))
    }
}
