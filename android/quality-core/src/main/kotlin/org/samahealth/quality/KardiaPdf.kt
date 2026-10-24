package org.samahealth.quality

import java.io.ByteArrayOutputStream
import java.util.zip.DataFormatException
import java.util.zip.Inflater
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.sqrt

/** PDF points per millimetre. */
private const val MM = 72.0 / 25.4

// --------------------------------------------------------------------------- object model
private class PdfName(val v: String) { override fun toString() = v }
private class PdfKw(val v: String) { override fun toString() = v }
private data class PdfRef(val num: Int, val gen: Int)

/** A lexer token: kind 'd' delimiter (String), 'n' name (PdfName), 's' string (ByteArray), 'r' regular (ByteArray). */
private class Tok(val kind: Char, val v: Any)

private fun isWs(b: Int) = b == 0 || b == 9 || b == 10 || b == 12 || b == 13 || b == 32
private fun isDelim(b: Int) = b == '('.code || b == ')'.code || b == '<'.code || b == '>'.code ||
    b == '['.code || b == ']'.code || b == '{'.code || b == '}'.code || b == '/'.code || b == '%'.code
private fun isDigit(b: Int) = b >= '0'.code && b <= '9'.code

/** Matches `[+-]?(\d+\.?\d*|\.\d+)` over the whole slice. */
private fun isNumber(b: ByteArray): Boolean {
    if (b.isEmpty()) return false
    var i = 0
    if (b[0] == '+'.code.toByte() || b[0] == '-'.code.toByte()) i = 1
    var d1 = 0
    while (i < b.size && isDigit(b[i].toInt() and 0xFF)) { i++; d1++ }
    if (d1 > 0) {
        if (i < b.size && b[i] == '.'.code.toByte()) {
            i++
            while (i < b.size && isDigit(b[i].toInt() and 0xFF)) i++
        }
        return i == b.size
    }
    if (i < b.size && b[i] == '.'.code.toByte()) {
        i++
        var d2 = 0
        while (i < b.size && isDigit(b[i].toInt() and 0xFF)) { i++; d2++ }
        return d2 > 0 && i == b.size
    }
    return false
}

private fun isInteger(b: ByteArray): Boolean = b.isNotEmpty() && b.all { isDigit(it.toInt() and 0xFF) }

private val ESC = mapOf('n'.code to 10, 'r'.code to 13, 't'.code to 9, 'b'.code to 8, 'f'.code to 12)
private val HASH_RE = Regex("#([0-9A-Fa-f]{2})")

private class Lexer(val data: ByteArray, var pos: Int = 0, val end: Int = data.size) {

    fun next(): Tok? {
        var c: Int
        while (true) {
            while (pos < end && isWs(data[pos].toInt() and 0xFF)) pos++
            if (pos >= end) return null
            c = data[pos].toInt() and 0xFF
            if (c == 0x25) {                                  // % comment
                while (pos < end && data[pos].toInt() != 10 && data[pos].toInt() != 13) pos++
                continue
            }
            break
        }
        if (c == 0x2F) {                                      // /name
            var p = pos + 1
            while (p < end && !isWs(data[p].toInt() and 0xFF) && !isDelim(data[p].toInt() and 0xFF)) p++
            val raw = String(data, pos + 1, p - pos - 1, Charsets.ISO_8859_1)
            pos = p
            val name = HASH_RE.replace(raw) { m -> m.groupValues[1].toInt(16).toChar().toString() }
            return Tok('n', PdfName(name))
        }
        if (c == 0x28) return Tok('s', literal())             // (literal string)
        if (c == 0x3C) {                                      // < or <<
            if (pos + 1 < end && (data[pos + 1].toInt() and 0xFF) == 0x3C) { pos += 2; return Tok('d', "<<") }
            var p = pos + 1
            while (p < end && (data[p].toInt() and 0xFF) != '>'.code) p++
            val sb = StringBuilder()
            for (i in pos + 1 until minOf(p, end)) {
                val ch = data[i].toInt() and 0xFF
                if (!isWs(ch)) sb.append(ch.toChar())
            }
            pos = minOf(end, p + 1)
            if (sb.length % 2 == 1) sb.append('0')
            val out = ByteArray(sb.length / 2)
            for (i in out.indices) {
                val hi = Character.digit(sb[2 * i], 16)
                val lo = Character.digit(sb[2 * i + 1], 16)
                if (hi < 0 || lo < 0) return Tok('s', ByteArray(0))
                out[i] = ((hi shl 4) or lo).toByte()
            }
            return Tok('s', out)
        }
        if (c == 0x3E) {                                      // >> (a lone > is skipped)
            if (pos + 1 < end && (data[pos + 1].toInt() and 0xFF) == 0x3E) { pos += 2; return Tok('d', ">>") }
            pos++
            return next()
        }
        if (c == '['.code || c == ']'.code || c == '{'.code || c == '}'.code) {
            pos++
            return Tok('d', c.toChar().toString())
        }
        if (c == 0x29) { pos++; return next() }               // stray )
        var p = pos
        while (p < end && !isWs(data[p].toInt() and 0xFF) && !isDelim(data[p].toInt() and 0xFF)) p++
        val raw = data.copyOfRange(pos, p)
        pos = p
        return Tok('r', raw)
    }

    private fun literal(): ByteArray {
        var p = pos + 1
        var depth = 1
        val out = ByteArrayOutputStream()
        while (p < end) {
            val c = data[p].toInt() and 0xFF
            if (c == 0x5C) {                                  // backslash
                p++
                if (p >= end) break
                val e = data[p].toInt() and 0xFF
                if (ESC.containsKey(e)) {
                    out.write(ESC.getValue(e)); p++
                } else if (e in 0x30..0x37) {
                    var q = p
                    while (q < end && q < p + 3 && (data[q].toInt() and 0xFF) in 0x30..0x37) q++
                    out.write(String(data, p, q - p, Charsets.ISO_8859_1).toInt(8) and 0xFF)
                    p = q
                } else if (e == 13) {
                    p += if (p + 1 < end && (data[p + 1].toInt() and 0xFF) == 10) 2 else 1
                } else if (e == 10) {
                    p++
                } else {
                    out.write(e); p++
                }
                continue
            }
            if (c == 0x28) depth++
            else if (c == 0x29) {
                depth--
                if (depth == 0) { p++; break }
            }
            out.write(c)
            p++
        }
        pos = p
        return out.toByteArray()
    }
}

/** One PDF value; [refs] enables the `n g R` indirect-reference lookahead (off inside content streams). */
private fun value(tok: Tok?, lx: Lexer, refs: Boolean): Any? {
    if (tok == null) return null
    if (tok.kind == 'd') {
        val v = tok.v as String
        if (v == "<<") {
            val out = LinkedHashMap<String, Any?>()
            while (true) {
                val t = lx.next() ?: return out
                if (t.kind == 'd' && t.v == ">>") return out
                if (t.kind == 'n') out[(t.v as PdfName).v] = value(lx.next(), lx, refs)
            }
        }
        if (v == "[") {
            val arr = ArrayList<Any?>()
            while (true) {
                val t = lx.next() ?: return arr
                if (t.kind == 'd' && t.v == "]") return arr
                arr.add(value(t, lx, refs))
            }
        }
        return PdfKw(v)
    }
    if (tok.kind == 'n' || tok.kind == 's') return tok.v
    val raw = tok.v as ByteArray
    val s = String(raw, Charsets.ISO_8859_1)
    if (isNumber(raw)) {
        if (refs && isInteger(raw)) {
            val save = lx.pos
            val t2 = lx.next()
            if (t2 != null && t2.kind == 'r' && isInteger(t2.v as ByteArray)) {
                val t3 = lx.next()
                if (t3 != null && t3.kind == 'r' && String(t3.v as ByteArray, Charsets.ISO_8859_1) == "R") {
                    return PdfRef(s.toInt(), String(t2.v, Charsets.ISO_8859_1).toInt())
                }
            }
            lx.pos = save
        }
        return s.toDouble()
    }
    if (s == "true") return true
    if (s == "false") return false
    if (s == "null") return null
    return PdfKw(s)
}

// --------------------------------------------------------------------------- document
private val OBJ_RE = Regex("""(\d+)\s+(\d+)\s+obj\b""")

/** Objects found by scanning for `n g obj`, with object streams expanded; no xref table is read. */
private class PdfDoc(val data: ByteArray) {
    /** Latin-1 view of [data]: one char per byte, so regex offsets are byte offsets. */
    val text: String = String(data, Charsets.ISO_8859_1)
    val objs = LinkedHashMap<Int, Pair<Any?, ByteArray?>>()
    val warnings = ArrayList<String>()

    init {
        var skipUntil = 0
        for (mt in OBJ_RE.findAll(text)) {
            if (mt.range.first < skipUntil) continue
            val lx = Lexer(data, mt.range.last + 1)
            val v = value(lx.next(), lx, true)
            var raw: ByteArray? = null
            var p = lx.pos
            while (p < data.size && isWs(data[p].toInt() and 0xFF)) p++
            if (text.startsWith("stream", p) && v is Map<*, *>) {
                p += 6
                if (text.startsWith("\r\n", p)) p += 2
                else if (p < data.size && (data[p].toInt() == 10 || data[p].toInt() == 13)) p += 1
                val length = v["Length"]
                var end = -1
                if (length is Double && length >= 0 && length <= data.size - p) {
                    val e = p + length.toInt()
                    var q = e
                    while (q < data.size && isWs(data[q].toInt() and 0xFF)) q++
                    if (text.startsWith("endstream", q)) end = e
                }
                if (end < 0) {
                    var e = text.indexOf("endstream", p)
                    if (e < 0) e = data.size
                    if (e >= 2 && text.regionMatches(e - 2, "\r\n", 0, 2)) e -= 2
                    else if (e > p && (data[e - 1].toInt() == 10 || data[e - 1].toInt() == 13)) e -= 1
                    end = e
                }
                raw = data.copyOfRange(p, end)
                skipUntil = end
            }
            objs[mt.groupValues[1].toInt()] = v to raw
        }
        for ((_, pair) in objs.toList()) {
            val v = pair.first
            val raw = pair.second
            if (v !is Map<*, *> || raw == null || (v["Type"] as? PdfName)?.v != "ObjStm") continue
            val body = decode(v, raw) ?: continue
            val first = ((v["First"] as? Double) ?: 0.0).toInt()
            val count = ((v["N"] as? Double) ?: 0.0).toInt()
            val lx = Lexer(body, 0, minOf(first, body.size))
            val pairs = ArrayList<Pair<Int, Int>>()
            for (i in 0 until count) {
                val a = lx.next() ?: break
                val b = lx.next() ?: break
                val an = (a.v as? ByteArray)?.let { String(it, Charsets.ISO_8859_1).toIntOrNull() }
                val bn = (b.v as? ByteArray)?.let { String(it, Charsets.ISO_8859_1).toIntOrNull() }
                if (an == null || bn == null) break
                pairs.add(an to bn)
            }
            for ((onum, off) in pairs) {
                if (onum in objs) continue
                val lx2 = Lexer(body, first + off)
                objs[onum] = value(lx2.next(), lx2, true) to null
            }
        }
    }

    fun resolve(v0: Any?): Any? {
        var v = v0
        var depth = 0
        while (v is PdfRef && depth < 32) {
            v = objs[v.num]?.first
            depth++
        }
        return v
    }

    /** Raw bytes for a stream, or null when its filter or predictor is unsupported or the data is damaged. */
    fun decode(d: Map<*, *>, raw: ByteArray): ByteArray? {
        val filt = resolve(d["Filter"])
        val names = when (filt) {
            is List<*> -> filt.map { resolve(it).toString() }
            null -> emptyList()
            else -> listOf(filt.toString())
        }
        if (names.isEmpty()) return raw
        if (names != listOf("FlateDecode")) {
            warnings.add("stream filter ${names.joinToString("/")} not supported: stream skipped")
            return null
        }
        var parms = resolve(d["DecodeParms"])
        if (parms is List<*>) parms = if (parms.isNotEmpty()) resolve(parms[0]) else null
        if (parms is Map<*, *>) {
            val pred = resolve(parms["Predictor"]) as? Double ?: 1.0
            if (pred > 1.0) {
                warnings.add("stream predictor not supported: stream skipped")
                return null
            }
        }
        val inf = Inflater()
        inf.setInput(raw)
        val out = ByteArrayOutputStream()
        val buf = ByteArray(1 shl 14)
        try {
            while (!inf.finished()) {
                val n = inf.inflate(buf)
                if (n == 0) { if (inf.needsInput() || inf.needsDictionary()) break }
                out.write(buf, 0, n)
            }
        } catch (e: DataFormatException) {
            warnings.add("damaged compressed stream skipped")
            return null
        } finally {
            inf.end()
        }
        return out.toByteArray()
    }

    fun streamOf(ref: Any?): Pair<Map<*, *>, ByteArray>? {
        if (ref !is PdfRef) return null
        val (v, raw) = objs[ref.num] ?: return null
        if (v !is Map<*, *> || raw == null) return null
        val body = decode(v, raw) ?: return null
        return v to body
    }

    /** Page dictionaries with their inherited resources, in tree order. */
    fun pages(): List<Pair<Map<*, *>, Any?>> {
        val out = ArrayList<Pair<Map<*, *>, Any?>>()
        var cat: Map<*, *>? = null
        for (num in objs.keys.sorted()) {
            val v = objs[num]?.first
            if (v is Map<*, *> && (v["Type"] as? PdfName)?.v == "Catalog") cat = v
        }
        val seen = HashSet<Int>()
        fun walk(nodeRef: Any?, inherited: Any?) {
            val node = resolve(nodeRef)
            if (nodeRef is PdfRef) {
                if (!seen.add(nodeRef.num)) return
            }
            if (node !is Map<*, *>) return
            val res = if (node.containsKey("Resources")) resolve(node["Resources"]) else inherited
            val kids = resolve(node["Kids"])
            if (kids is List<*>) {
                for (k in kids) walk(k, res)
            } else if ((node["Type"] as? PdfName)?.v == "Page" || node.containsKey("Contents")) {
                out.add(node to res)
            }
        }
        if (cat != null) walk(cat["Pages"], null)
        if (out.isEmpty()) {
            for (num in objs.keys.sorted()) {
                val v = objs[num]?.first
                if (v is Map<*, *> && (v["Type"] as? PdfName)?.v == "Page") out.add(v to resolve(v["Resources"]))
            }
        }
        return out
    }
}

// --------------------------------------------------------------------------- content streams
private data class Pt(val x: Double, val y: Double)

private fun mul(m: DoubleArray, n: DoubleArray) = doubleArrayOf(
    m[0] * n[0] + m[1] * n[2], m[0] * n[1] + m[1] * n[3],
    m[2] * n[0] + m[3] * n[2], m[2] * n[1] + m[3] * n[3],
    m[4] * n[0] + m[5] * n[2] + n[4], m[4] * n[1] + m[5] * n[3] + n[5],
)

/** True when a stroke colour is dark (luminance <= 0.5), null when the space is unknown. */
private fun lum(vals: List<Double>): Boolean? = when (vals.size) {
    1 -> vals[0] <= 0.5
    3 -> 0.299 * vals[0] + 0.587 * vals[1] + 0.114 * vals[2] <= 0.5
    4 -> {
        val (c, m, y, k) = vals
        0.299 * (1 - c) * (1 - k) + 0.587 * (1 - m) * (1 - k) + 0.114 * (1 - y) * (1 - k) <= 0.5
    }
    else -> null
}

private val ID_RE = Regex("""\sID[\s]""")
private val EI_RE = Regex("""\sEI(?=[\s/<\[]|$)""")

/** Runs content streams: keeps stroked dark subpaths in device space and the text of each BT..ET block. */
private class Painter(val doc: PdfDoc) {
    val paths = ArrayList<Triple<Int, List<Pt>, Double>>()
    val text = ArrayList<MutableList<String>>()

    fun run(content: ByteArray, resources: Any?, ctm0: DoubleArray, page: Int, depth: Int = 0) {
        if (depth > 8) return
        while (text.size <= page) text.add(ArrayList())
        val view = String(content, Charsets.ISO_8859_1)
        val lx = Lexer(content)
        var ctm = ctm0
        var ops = ArrayList<Any?>()
        var lw = 1.0
        var dark = true
        val stack = ArrayList<Triple<DoubleArray, Double, Boolean>>()
        var subs = ArrayList<ArrayList<Pt>>()
        var cur: ArrayList<Pt>? = null
        var bt: MutableList<String>? = null

        fun pt(x: Double, y: Double) = Pt(ctm[0] * x + ctm[2] * y + ctm[4], ctm[1] * x + ctm[3] * y + ctm[5])

        fun nums(k: Int): List<Double>? {
            if (ops.size < k) return null
            val tail = ops.subList(ops.size - k, ops.size)
            return if (tail.all { it is Double }) tail.map { it as Double } else null
        }

        while (true) {
            val tok = lx.next() ?: break
            val op: String
            if (tok.kind == 'r') {
                val raw = tok.v as ByteArray
                val s = String(raw, Charsets.ISO_8859_1)
                if (isNumber(raw) || s == "true" || s == "false" || s == "null") {
                    ops.add(value(tok, lx, false)); continue
                }
                op = s
            } else {
                ops.add(value(tok, lx, false)); continue
            }
            when {
                op == "BI" -> {                               // inline image: skip its binary data
                    val mt = ID_RE.find(view, lx.pos)
                    if (mt != null) {
                        val me = EI_RE.find(view, mt.range.last + 1)
                        lx.pos = if (me != null) me.range.last + 1 else content.size
                    }
                }
                op == "q" -> stack.add(Triple(ctm, lw, dark))
                op == "Q" -> if (stack.isNotEmpty()) {
                    val (c, l, d) = stack.removeAt(stack.size - 1)
                    ctm = c; lw = l; dark = d
                }
                op == "cm" -> nums(6)?.let { ctm = mul(it.toDoubleArray(), ctm) }
                op == "w" -> nums(1)?.let { lw = it[0] }
                op == "G" || op == "RG" || op == "K" ->
                    nums(if (op == "G") 1 else if (op == "RG") 3 else 4)?.let { dark = lum(it) == true }
                op == "CS" -> dark = true
                op == "SC" || op == "SCN" -> if (ops.isNotEmpty() && ops.all { it is Double }) {
                    val lu = lum(ops.map { it as Double })
                    dark = lu ?: true
                }
                op == "m" -> nums(2)?.let {
                    cur = arrayListOf(pt(it[0], it[1]))
                    subs.add(cur!!)
                }
                op == "l" || op == "c" || op == "v" || op == "y" -> {
                    val k = when (op) { "l" -> 2; "c" -> 6; else -> 4 }
                    nums(k)?.let {
                        val x: Double
                        val y: Double
                        if (op == "l") { x = it[0]; y = it[1] }
                        else if (op == "v" || op == "y") { x = it[2]; y = it[3] }
                        else { x = it[4]; y = it[5] }
                        if (cur == null) { cur = ArrayList(); subs.add(cur!!) }
                        cur!!.add(pt(x, y))
                    }
                }
                op == "re" -> nums(4)?.let {
                    val (x, y, w, h) = it
                    subs.add(arrayListOf(pt(x, y), pt(x + w, y), pt(x + w, y + h), pt(x, y + h), pt(x, y)))
                    cur = null
                }
                op == "h" -> {
                    val c = cur
                    if (c != null && c.size > 1 && c.last() != c.first()) c.add(c.first())
                    cur = null
                }
                op in PAINT -> {
                    val c = cur
                    if (op in CLOSE_FIRST && c != null && c.size > 1 && c.last() != c.first()) c.add(c.first())
                    if (op in STROKE && dark) {
                        val scale = sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
                        for (sp in subs) if (sp.size >= 2) paths.add(Triple(page, sp, lw * scale))
                    }
                    subs = ArrayList()
                    cur = null
                }
                op == "BT" -> bt = ArrayList()
                op == "ET" -> {
                    val line = bt?.joinToString("")?.trim()
                    if (!line.isNullOrEmpty()) text[page].add(line)
                    bt = null
                }
                op == "Tj" || op == "'" || op == "\"" ->
                    if (bt != null && ops.isNotEmpty() && ops.last() is ByteArray) {
                        bt!!.add(String(ops.last() as ByteArray, Charsets.ISO_8859_1))
                    }
                op == "TJ" -> if (bt != null && ops.isNotEmpty() && ops.last() is List<*>) {
                    for (el in ops.last() as List<*>) {
                        if (el is ByteArray) bt!!.add(String(el, Charsets.ISO_8859_1))
                        else if (el is Double && el < -200) bt!!.add(" ")
                    }
                }
                op == "Do" -> if (ops.isNotEmpty() && ops.last() is PdfName) {
                    form((ops.last() as PdfName).v, resources, ctm, page, depth)
                }
            }
            ops = ArrayList()
        }
    }

    private fun form(name: String, resources: Any?, ctm: DoubleArray, page: Int, depth: Int) {
        val res = doc.resolve(resources)
        val xo = if (res is Map<*, *>) doc.resolve(res["XObject"]) else null
        val ref = if (xo is Map<*, *>) xo[name] else null
        val st = doc.streamOf(ref) ?: return
        if ((st.first["Subtype"] as? PdfName)?.v != "Form") return
        val mat = doc.resolve(st.first["Matrix"])
        val m = if (mat is List<*> && mat.size == 6 && mat.all { it is Double }) {
            DoubleArray(6) { mat[it] as Double }
        } else {
            doubleArrayOf(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        }
        val fres = if (st.first.containsKey("Resources")) doc.resolve(st.first["Resources"]) else res
        run(st.second, fres, mul(m, ctm), page, depth + 1)
    }

    companion object {
        val STROKE = setOf("S", "s", "B", "B*", "b", "b*")
        val PAINT = STROKE + setOf("f", "F", "f*", "n")
        val CLOSE_FIRST = setOf("s", "b", "b*")
    }
}

// --------------------------------------------------------------------------- trace recovery
/**
 * Median x step of a polyline that looks like a sampled trace (>= 20 points, x strictly rising in near-equal steps
 * of 0.05-1 pt; exact repeats allowed), else null.
 */
private fun traceStep(pts: List<Pt>): Double? {
    if (pts.size < 20) return null
    val steps = DoubleArray(pts.size - 1) { pts[it + 1].x - pts[it].x }
    val nz = steps.filter { abs(it) > 1e-6 }
    if (nz.size < 0.9 * steps.size || nz.any { it <= 0 }) return null
    val med = Dsp.median(nz.toDoubleArray())
    if (med < 0.05 || med > 1.0 || nz.any { abs(it - med) > 0.2 * med }) return null
    return med
}

/** Height (pt) of a calibration pulse: 4-8 axis-aligned points, base -> up -> plateau -> base. */
private fun calHeight(pts: List<Pt>): Double? {
    if (pts.size < 4 || pts.size > 8) return null
    for (i in 0 until pts.size - 1) {
        val dx = pts[i + 1].x - pts[i].x
        val dy = pts[i + 1].y - pts[i].y
        if (dx < -0.01 || (abs(dx) > 0.01 && abs(dy) > 0.01)) return null
    }
    val base = pts[0].y
    if (abs(pts.last().y - base) > 0.5) return null
    val top = pts.maxOf { it.y }
    val height = top - base
    val width = pts.last().x - pts[0].x
    val plateau = pts.filter { abs(it.y - top) < 0.01 }.map { it.x }
    if (height < 2 * MM || height > 40 * MM || width > 25 * MM ||
        plateau.isEmpty() || (plateau.max() - plateau.min()) < 1 * MM
    ) return null
    return height
}

private class PageFields(
    var determination: String? = null,
    var hrBpm: Int? = null,
    var enhancedFilter: Boolean? = null,
    var mainsHz: Int? = null,
    var speed: Double? = null,
    var gain: Double? = null,
    var durationS: Double? = null,
)

private fun pageTextFields(text: String): PageFields {
    val f = PageFields()
    Regex("""Kardia Determination:\s*([^\n]*)""").find(text)?.let { m ->
        var det = m.groupValues[1].trim()
        if (det.isEmpty()) {
            val rest = text.substring(m.range.last + 1).trimStart()
            det = if (rest.isNotEmpty()) rest.substringBefore("\n").trim() else ""
        }
        f.determination = det.ifEmpty { null }
    }
    Regex("""Heart Rate:\s*(\d{2,3})\s*BPM""", RegexOption.IGNORE_CASE).find(text)?.let {
        f.hrBpm = it.groupValues[1].toInt()
    }
    Regex("""Mains Frequency:\s*(50|60)\s*Hz""").find(text)?.let { f.mainsHz = it.groupValues[1].toInt() }
    if (text.contains("Enhanced Filter")) f.enhancedFilter = true
    else if (text.contains("Original Filter")) f.enhancedFilter = false
    Regex("""(\d+(?:\.\d+)?)\s*mm/s""").find(text)?.let { f.speed = it.groupValues[1].toDouble() }
    Regex("""(\d+(?:\.\d+)?)\s*mm/mV""").find(text)?.let { f.gain = it.groupValues[1].toDouble() }
    Regex("""Duration:\s*(\d+)\s*s\b""").find(text)?.let { f.durationS = it.groupValues[1].toDouble() }
    return f
}

/**
 * Kardia PDF export -> lead-I ECG in millivolts at 300 Hz, read from the vector trace (no rasterising).
 *
 * Keeps stroked dark polylines that look like a sampled trace, drops the calibration pulse, beat ticks, grid and
 * baselines, groups the trace into strips per page (8 mm y gap), orders them top to bottom and page by page, maps
 * each point to a sample index from its x position, converts to mV against the strip's baseline with the measured
 * calibration pulse (else the printed scale, else 10 mm/mV) and concatenates. A 6-lead export keeps the top strip
 * (lead I) of each page. Everything assumed is listed in the trace's warnings. Python twin:
 * palmppg.quality.onsite.read_kardia_pdf, pinned by configs/quality_fixtures/kardia_pdf.json.
 */
object KardiaPdf {

    /** @throws IllegalArgumentException when the bytes are not a PDF or hold no recognisable trace. */
    fun extract(pdfBytes: ByteArray): EcgTrace {
        require(pdfBytes.size >= 4 && String(pdfBytes, 0, 4, Charsets.ISO_8859_1) == "%PDF") { "not a PDF file" }
        val doc = PdfDoc(pdfBytes)
        val painter = Painter(doc)
        for ((i, pr) in doc.pages().withIndex()) {
            val (page, res) = pr
            val c = page["Contents"]
            val rv = doc.resolve(c)
            val refs: List<Any?> = if (rv is List<*>) rv else if (c is PdfRef) listOf(c) else emptyList()
            val body = ByteArrayOutputStream()
            for (ref in refs) {
                val st = doc.streamOf(ref) ?: continue
                body.write(st.second)
                body.write('\n'.code)
            }
            painter.run(body.toByteArray(), res, doubleArrayOf(1.0, 0.0, 0.0, 1.0, 0.0, 0.0), i)
        }
        val warnings = ArrayList(doc.warnings)
        val text = painter.text.joinToString("\n") { it.joinToString("\n") }
        val f = pageTextFields(text)
        return assemble(painter.paths, text, f, warnings)
    }

    private fun assemble(
        paths: List<Triple<Int, List<Pt>, Double>>,
        text: String,
        f: PageFields,
        warnings: ArrayList<String>,
    ): EcgTrace {
        val cands = ArrayList<Triple<Int, List<Pt>, Double>>()
        val cals = ArrayList<Double>()
        val hlines = ArrayList<DoubleArray>()          // page, y, x0, x1
        for ((page, pts, _) in paths) {
            val step = traceStep(pts)
            if (step != null) { cands.add(Triple(page, pts, step)); continue }
            val h = calHeight(pts)
            if (h != null) { cals.add(h); continue }
            if (pts.size == 2 && abs(pts[0].y - pts[1].y) < 0.01 && abs(pts[1].x - pts[0].x) > 100) {
                hlines.add(doubleArrayOf(page.toDouble(), pts[0].y, minOf(pts[0].x, pts[1].x), maxOf(pts[0].x, pts[1].x)))
            }
        }
        require(cands.isNotEmpty()) { "no ECG trace found in the PDF" }
        val allSteps = ArrayList<Double>()
        for ((_, pts, _) in cands) {
            for (i in 0 until pts.size - 1) {
                val s = pts[i + 1].x - pts[i].x
                if (abs(s) > 1e-6) allSteps.add(s)
            }
        }
        val dx = Dsp.median(allSteps.toDoubleArray())

        val strips = ArrayList<Pair<Int, List<List<Pt>>>>()
        val multiLead = Regex("""\baV[RLF]\b""").containsMatchIn(text)
        var warnMulti = false
        for (page in cands.map { it.first }.distinct().sorted()) {
            val here = cands.filter { it.first == page }
                .map { Dsp.median(DoubleArray(it.second.size) { k -> it.second[k].y }) to it.second }
                .sortedByDescending { it.first }
            var groups = ArrayList<MutableList<List<Pt>>>()
            var last: Double? = null
            for ((yc, pts) in here) {
                if (last == null || last!! - yc > 8 * MM) groups.add(ArrayList())
                groups.last().add(pts)
                last = yc
            }
            if (multiLead || groups.size == 6) {
                groups = ArrayList(groups.take(1))
                warnMulti = true
            }
            for (g in groups) strips.add(page to g)
        }
        if (warnMulti) warnings.add("multi-lead layout: lead I taken from the top strip of each page")

        val gain = f.gain
        val ptPerMv: Double
        if (cals.isNotEmpty()) {
            ptPerMv = Dsp.median(cals.toDoubleArray())
            if (gain != null && abs(ptPerMv - gain * MM) > 0.1 * gain * MM) {
                warnings.add("calibration pulse (${fmt(ptPerMv / MM, 1)} mm) differs from the printed " +
                    "scale (${fmt(gain, 1)} mm/mV): pulse used")
            }
        } else if (gain != null) {
            ptPerMv = gain * MM
            warnings.add("no calibration pulse: printed scale ${fmt(gain, 1)} mm/mV used")
        } else {
            ptPerMv = 10.0 * MM
            warnings.add("no calibration pulse or printed scale: 10 mm/mV assumed")
        }
        var speed = f.speed
        if (speed == null) {
            speed = 25.0
            warnings.add("paper speed not printed: 25 mm/s assumed")
        }
        val fsMeas = speed * MM / dx
        val fs: Double
        if (abs(fsMeas - 300.0) <= 0.02 * 300.0) {
            fs = 300.0
        } else {
            fs = fsMeas
            warnings.add("sample spacing gives ${fmt(fsMeas, 1)} Hz, not the Kardia 300 Hz: measured rate used")
        }

        val out = ArrayList<Double>()
        var gaps = 0
        var noBase = 0
        for ((page, group) in strips) {
            val pts = group.flatten().sortedBy { it.x }
            val x0 = pts[0].x
            val vals = LinkedHashMap<Int, Double>()
            for (p in pts) {
                val k = floor((p.x - x0) / dx + 0.5).toInt()
                if (k !in vals) vals[k] = p.y
            }
            val kmax = vals.keys.max()
            val ys = DoubleArray(kmax + 1)
            val known = vals.keys.sorted()
            for (i in 0 until known.size - 1) {
                val a = known[i]
                val b = known[i + 1]
                ys[a] = vals.getValue(a)
                for (k in a + 1 until b) {
                    gaps++
                    ys[k] = vals.getValue(a) + (vals.getValue(b) - vals.getValue(a)) * (k - a) / (b - a).toDouble()
                }
            }
            ys[kmax] = vals.getValue(kmax)
            val ymed = Dsp.median(ys)
            val xsLo = x0
            val xsHi = pts.last().x
            val near = hlines.filter {
                it[0].toInt() == page && it[2] <= xsHi && it[3] >= xsLo && abs(it[1] - ymed) <= 10 * MM
            }
            val zero: Double
            if (near.isNotEmpty()) {
                zero = near.minWith(compareBy({ abs(it[1] - ymed) }, { it[1] }))[1]
            } else {
                zero = ymed
                noBase++
            }
            for (v in ys) out.add((v - zero) / ptPerMv)
        }
        if (gaps > 0) warnings.add("$gaps missing sample(s) interpolated")
        if (noBase > 0) warnings.add("no baseline found for $noBase strip(s): strip median used as 0 mV")
        val dur = f.durationS
        if (dur != null && abs(out.size / fs - dur) > 1.0) {
            warnings.add("recovered ${fmt(out.size / fs, 1)} s but the page says ${fmt(dur, 0)} s")
        }
        return EcgTrace(
            fs = fs,
            mv = out.toDoubleArray(),
            warnings = warnings,
            determination = f.determination,
            hrBpm = f.hrBpm,
            enhancedFilter = f.enhancedFilter,
            mainsHz = f.mainsHz,
        )
    }
}
