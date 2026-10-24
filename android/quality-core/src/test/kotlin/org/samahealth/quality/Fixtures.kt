package org.samahealth.quality

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.Base64
import java.util.zip.GZIPInputStream
import kotlin.math.abs
import kotlin.math.max
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** The shared fixtures written by `python tools/make_quality_fixtures.py`; the path comes from the test task. */
internal object Fixtures {
    val dir: File = File(
        System.getProperty("quality.fixtures")
            ?: error("set -Dquality.fixtures=<repo>/configs/quality_fixtures"),
    )

    private val json = Json { ignoreUnknownKeys = true }

    fun load(name: String): JsonObject = json.parseToJsonElement(dir.resolve(name).readText()).jsonObject

    fun cases(name: String): List<JsonObject> = load(name)["cases"]!!.jsonArray.map { it.jsonObject }

    fun gunzipB64(s: String): String {
        val raw = Base64.getDecoder().decode(s)
        GZIPInputStream(raw.inputStream()).use { gz ->
            val out = ByteArrayOutputStream()
            gz.copyTo(out)
            return out.toString("US-ASCII")
        }
    }

    fun b64(s: String): ByteArray = Base64.getDecoder().decode(s)
}

internal fun JsonElement?.str(): String? =
    if (this == null || this is JsonNull) null else (this as JsonPrimitive).content

internal fun JsonElement?.dbl(): Double? =
    if (this == null || this is JsonNull) null else (this as JsonPrimitive).content.toDouble()

internal fun JsonElement?.bool(): Boolean? =
    if (this == null || this is JsonNull) null else (this as JsonPrimitive).content.toBooleanStrict()

internal fun JsonArray.strings(): List<String> = map { it.jsonPrimitive.content }

/** The Python reference is the source of truth; the Kotlin numbers must land within [tol] relative. */
internal fun assertClose(want: Double, got: Double, tol: Double, what: String) {
    assertTrue(abs(got - want) <= tol * max(1.0, abs(want)), "$what: expected $want, got $got")
}

/** Every metric of a fixture's `expected.metrics` block, nulls included. */
internal fun assertMetrics(expected: JsonObject, got: Map<String, Double?>, tol: Double, what: String) {
    for ((key, w) in expected) {
        val want = w.dbl()
        val g = got[key]
        if (want == null) {
            assertEquals(null, g, "$what.$key")
        } else {
            assertTrue(g != null, "$what.$key is missing")
            assertClose(want, g!!, tol, "$what.$key")
        }
    }
}
