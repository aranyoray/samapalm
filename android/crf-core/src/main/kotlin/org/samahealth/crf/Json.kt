package org.samahealth.crf

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeParseException

/** JSON helpers shared by the engine; semantics follow palmppg/core/crf_schema.py (Python's json types). */
val CrfJson: Json = Json { ignoreUnknownKeys = true; encodeDefaults = true; explicitNulls = true }

private val INT_RE = Regex("^-?\\d+$")
private val DATE_RE = Regex("^\\d{4}-\\d{2}-\\d{2}$")

/** Python `answered`: None/blank string/empty list or dict are unanswered. */
fun answered(v: JsonElement?): Boolean = when (v) {
    null, JsonNull -> false
    is JsonPrimitive -> if (v.isString) v.content.isNotBlank() else true
    is JsonArray -> v.isNotEmpty()
    is JsonObject -> v.isNotEmpty()
}

/** A JSON number that is not a boolean (Python `_is_num`). */
fun isNum(v: JsonElement?): Boolean =
    v is JsonPrimitive && !v.isString && v.booleanOrNull == null && v.doubleOrNull?.isNaN() == false

/** A JSON integer literal (Python `isinstance(v, int) and not bool`). */
fun isInt(v: JsonElement?): Boolean = isNum(v) && INT_RE.matches((v as JsonPrimitive).content)

fun num(v: JsonElement?): Double? = if (isNum(v)) (v as JsonPrimitive).doubleOrNull else null

fun str(v: JsonElement?): String? = if (v is JsonPrimitive && v.isString) v.content else null

fun bool(v: JsonElement?): Boolean? = if (v is JsonPrimitive && !v.isString) v.booleanOrNull else null

fun obj(v: JsonElement?): JsonObject? = v as? JsonObject

/** Python `==` on JSON values: numbers compare numerically (7 == 7.0), everything else structurally. */
fun valueEquals(a: JsonElement?, b: JsonElement?): Boolean {
    if (isNum(a) && isNum(b)) return num(a) == num(b)
    val an = a ?: JsonNull
    val bn = b ?: JsonNull
    if (an is JsonPrimitive && bn is JsonPrimitive) {
        if (an is JsonNull || bn is JsonNull) return an is JsonNull && bn is JsonNull
        return an.isString == bn.isString && an.content == bn.content
    }
    if (an is JsonArray && bn is JsonArray) return an.size == bn.size && an.indices.all { valueEquals(an[it], bn[it]) }
    if (an is JsonObject && bn is JsonObject) return an.keys == bn.keys && an.keys.all { valueEquals(an[it], bn[it]) }
    return false
}

/** ISO 8601 timestamp with offset; naive values are read as UTC (Python `parse_ts`). */
fun parseTs(v: JsonElement?): OffsetDateTime? {
    val s = str(v)?.replace("Z", "+00:00") ?: return null
    if (s.isEmpty()) return null
    return try {
        OffsetDateTime.parse(s)
    } catch (e: DateTimeParseException) {
        try {
            LocalDateTime.parse(s).atOffset(ZoneOffset.UTC)
        } catch (e2: DateTimeParseException) {
            null
        }
    }
}

fun parseDate(v: JsonElement?): LocalDate? {
    val s = str(v) ?: return null
    if (!DATE_RE.matches(s)) return null
    return try { LocalDate.parse(s) } catch (e: DateTimeParseException) { null }
}

fun jsonOf(v: Any?): JsonElement = when (v) {
    null -> JsonNull
    is JsonElement -> v
    is String -> JsonPrimitive(v)
    is Boolean -> JsonPrimitive(v)
    is Int -> JsonPrimitive(v)
    is Long -> JsonPrimitive(v)
    is Double -> JsonPrimitive(v)
    is Number -> JsonPrimitive(v)
    is List<*> -> JsonArray(v.map { jsonOf(it) })
    is Map<*, *> -> JsonObject(v.entries.associate { (k, x) -> k.toString() to jsonOf(x) })
    else -> JsonPrimitive(v.toString())
}
