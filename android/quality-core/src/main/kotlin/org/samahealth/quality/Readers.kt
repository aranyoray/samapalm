package org.samahealth.quality

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32

private fun headerIndex(line: String): Map<String, Int> =
    line.trim().split(",").withIndex().associate { (i, h) -> h.trim() to i }

private val GRID_COLS = (0..2).flatMap { r -> (0..2).map { c -> "g$r$c" } }

/** `<clip>_roi.csv` as written by PalmRecorderActivity (CONTRACTS 3.5). */
object RoiCsv {
    /** Rows sorted by t_ref_ns, t in seconds from the first row; rows that do not parse or are not finite are skipped. */
    fun parse(text: String): RoiSeries {
        val lines = text.lines()
        require(lines.isNotEmpty() && lines[0].isNotBlank()) { "roi.csv is empty" }
        val idx = headerIndex(lines[0])
        val need = listOf("t_ref_ns", "y_mean", "r_mean", "g_mean", "b_mean", "clip_frac")
        val missing = need.filter { it !in idx }
        require(missing.isEmpty()) { "roi.csv: missing columns $missing" }
        val hasGrid = GRID_COLS.all { it in idx }
        val cols = need.drop(1) + (if (hasGrid) GRID_COLS else emptyList())
        val rows = ArrayList<Pair<Long, DoubleArray>>()
        for (line in lines.drop(1)) {
            if (line.isBlank()) continue
            val parts = line.split(",")
            val t = parts.getOrNull(idx.getValue("t_ref_ns"))?.trim()?.toLongOrNull() ?: continue
            val vals = DoubleArray(cols.size)
            var ok = true
            for ((k, c) in cols.withIndex()) {
                val v = parts.getOrNull(idx.getValue(c))?.trim()?.toDoubleOrNull()
                if (v == null || !v.isFinite()) { ok = false; break }
                vals[k] = v
            }
            if (ok) rows.add(t to vals)
        }
        val sorted = rows.sortedBy { it.first }
        val n = sorted.size
        val t0 = if (n > 0) sorted[0].first else 0L
        fun col(k: Int) = DoubleArray(n) { sorted[it].second[k] }
        return RoiSeries(
            tS = DoubleArray(n) { (sorted[it].first - t0).toDouble() / 1e9 },
            r = col(1), g = col(2), b = col(3), y = col(0), clipFrac = col(4),
            grid = if (hasGrid) Array(9) { col(5 + it) } else null,
        )
    }
}

/** `<clip>_frames.csv` (CONTRACTS 3.5). */
object FramesCsv {
    /** sensor_ts_ns -> seconds from the first frame, sorted. */
    fun parseTimesS(text: String): DoubleArray {
        val lines = text.lines()
        if (lines.isEmpty() || lines[0].isBlank()) return DoubleArray(0)
        val idx = headerIndex(lines[0])
        val col = idx["sensor_ts_ns"] ?: throw IllegalArgumentException("frames.csv: missing column sensor_ts_ns")
        val ts = lines.drop(1).mapNotNull { it.split(",").getOrNull(col)?.trim()?.toLongOrNull() }.sorted()
        if (ts.isEmpty()) return DoubleArray(0)
        return DoubleArray(ts.size) { (ts[it] - ts[0]).toDouble() / 1e9 }
    }
}

/** `<clip>_ecg_samples.csv` written from the BLE capture. */
object EcgCsv {
    /** (lead1_mv, fs); fs = (n - 1) / span of t_ref_ns, or 300 Hz when the timestamps are missing. */
    fun parseLead1Mv(text: String): Pair<DoubleArray, Double> {
        val lines = text.lines()
        require(lines.isNotEmpty() && lines[0].isNotBlank()) { "ecg_samples.csv is empty" }
        val idx = headerIndex(lines[0])
        val mvCol = idx["lead1_mv"] ?: throw IllegalArgumentException("ecg_samples.csv: missing column lead1_mv")
        val tCol = idx["t_ref_ns"]
        val mv = ArrayList<Double>()
        val ts = ArrayList<Long>()
        for (line in lines.drop(1)) {
            if (line.isBlank()) continue
            val parts = line.split(",")
            val v = parts.getOrNull(mvCol)?.trim()?.toDoubleOrNull() ?: continue
            val t = if (tCol != null) parts.getOrNull(tCol)?.trim()?.toLongOrNull() ?: continue else null
            if (!v.isFinite()) continue
            mv.add(v)
            if (t != null) ts.add(t)
        }
        var fs = 300.0
        if (ts.size >= 2 && ts.last() > ts.first()) fs = (ts.size - 1) * 1e9 / (ts.last() - ts.first()).toDouble()
        return mv.toDoubleArray() to fs
    }
}

/**
 * AliveCor ATC v1 reader, a tolerant port of palmppg/ecg/atc.py (CONTRACTS 3.6): bad CRCs, unknown blocks and a
 * missing fmt block become warnings (defaults 300 Hz, 500 nV/LSB). mV = int16 x resolution / 1e6, rounded to float32
 * as the Python parser stores it, so both sides read the same numbers.
 */
object AtcReader {
    private const val DEFAULT_FS = 300.0
    private const val DEFAULT_RES_NV = 500

    fun read(bytes: ByteArray): EcgTrace {
        val magic = "ALIVE".toByteArray(Charsets.US_ASCII)
        require(bytes.size >= 8 && bytes.copyOfRange(0, 5).contentEquals(magic)) {
            "not an ATC file (${bytes.size} bytes)"
        }
        val problems = ArrayList<String>()
        val bb = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        var pos = 8
        var fmt: IntArray? = null
        var raw = ShortArray(0)
        var ecgSeen = false
        while (pos + 8 <= bytes.size) {
            val length = bb.getInt(pos).toLong() and 0xFFFFFFFFL
            val id = String(bytes, pos + 4, 4, Charsets.ISO_8859_1)
            val start = pos + 8
            val end = start + length
            if (end + 4 > bytes.size) {
                problems.add("truncated block '${id.trim()}' at offset $pos: declares $length B but only " +
                    "${bytes.size - start} B remain")
                break
            }
            val e = end.toInt()
            val crc = CRC32().apply { update(bytes, pos + 4, 4); update(bytes, start, e - start) }.value
            val stored = bb.getInt(e).toLong() and 0xFFFFFFFFL
            if (crc != stored) {
                problems.add("crc mismatch in block '${id.trim()}' at offset $pos " +
                    "(stored 0x${"%08x".format(stored)}, computed 0x${"%08x".format(crc)})")
            }
            when (id) {
                "fmt " -> {
                    if (e - start >= 8) {
                        fmt = intArrayOf(
                            bytes[start].toInt() and 0xFF,
                            bb.getShort(start + 1).toInt() and 0xFFFF,
                            bb.getShort(start + 3).toInt() and 0xFFFF,
                        )
                    } else problems.add("fmt block too short (${e - start} B)")
                }
                "ecg " -> {
                    ecgSeen = true
                    val usable = (e - start) - (e - start) % 2
                    if (usable != e - start) problems.add("ecg block has an odd byte count; last byte ignored")
                    raw = ShortArray(usable / 2) { bb.getShort(start + 2 * it) }
                }
            }
            pos = e + 4
        }
        if (pos != bytes.size) problems.add("${bytes.size - pos} trailing byte(s) after the last complete block")
        if (!ecgSeen) problems.add("no ecg block found")
        val f = fmt
        val fs: Double
        val resNv: Int
        if (f == null) {
            problems.add("no fmt block: assuming fs=$DEFAULT_FS Hz, resolution=$DEFAULT_RES_NV nV/LSB")
            fs = DEFAULT_FS
            resNv = DEFAULT_RES_NV
        } else {
            fs = if (f[1] > 0) f[1].toDouble() else DEFAULT_FS
            resNv = if (f[2] > 0) f[2] else DEFAULT_RES_NV
            if (f[1] <= 0 || f[2] <= 0) problems.add("fmt block has a zero frequency or resolution; defaults applied")
        }
        val scale = resNv / 1e6
        val mv = DoubleArray(raw.size) { (raw[it].toDouble() * scale).toFloat().toDouble() }
        return EcgTrace(fs, mv, problems)
    }
}
