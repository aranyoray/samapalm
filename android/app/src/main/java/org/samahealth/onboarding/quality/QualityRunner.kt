package org.samahealth.onboarding.quality

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.samahealth.quality.AtcReader
import org.samahealth.quality.EcgCsv
import org.samahealth.quality.EcgQuality
import org.samahealth.quality.EcgSummary
import org.samahealth.quality.EcgTrace
import org.samahealth.quality.FramesCsv
import org.samahealth.quality.Grade
import org.samahealth.quality.KardiaPdf
import org.samahealth.quality.RhythmSummary
import org.samahealth.quality.RoiCsv
import java.io.File

data class VideoResult(val grade: Grade, val durationS: Double)

data class EcgResult(val grade: Grade?, val source: String, val error: String?)

data class ClipGrades(
    val video: Grade?,
    val ecg: Grade?,
    val rhythm: RhythmSummary?,
    val source: String?,
    val ecgFile: String?,
    val notes: List<String>,
    /** What the Kardia device itself printed on the strip, when the ECG came from a Kardia export. */
    val deviceDetermination: String? = null,
    val deviceHrBpm: Int? = null,
    val deviceMainsHz: Int? = null,
    val deviceEnhancedFilter: Boolean? = null,
)

/** {"grade", "reasons", "metrics"} as the clip record stores it. */
fun Grade.toJson(): JsonObject = JsonObject(
    mapOf(
        "grade" to JsonPrimitive(level),
        "reasons" to JsonArray(reasons.map { JsonPrimitive(it) }),
        "metrics" to JsonObject(metrics.mapValues { (_, v) -> if (v == null) JsonNull else JsonPrimitive(v) }),
    ),
)

/**
 * Runs the quality-core scorers over what the recorder wrote under `<externalFilesDir>/<PID>/` (CONTRACTS 3.5)
 * and over files imported from the Kardia app. Nothing here throws on a missing or odd file: every problem comes
 * back as a note or an error string the operator can read.
 */
object QualityRunner {

    fun appFile(context: Context, relPath: String): File = File(context.getExternalFilesDir(null), relPath)

    private fun readOrNull(f: File): String? =
        runCatching { if (f.isFile && f.length() > 0) f.readText() else null }.getOrNull()

    /** An MP4 recorded outside the app: decoded to the same ROI series the in-app recorder logs. */
    suspend fun gradeVideo(
        context: Context,
        file: File,
        expectedSeconds: Double,
        refHrBpm: Double? = null,
        onProgress: (Float) -> Unit = {},
    ): VideoResult = withContext(Dispatchers.IO) {
        val roi = Mp4Roi.read(file, onProgress)
        val grade = org.samahealth.quality.VideoQuality.score(roi, null, expectedSeconds, refHrBpm)
        VideoResult(grade, grade.metrics["duration_s"] ?: 0.0)
    }

    /** A samples CSV, an ATC file or a Kardia PDF, picked by what the file actually is. */
    suspend fun gradeEcg(context: Context, file: File): EcgResult = withContext(Dispatchers.IO) {
        val tr = readEcg(file)
        if (tr.second != null) return@withContext EcgResult(null, tr.first, tr.second)
        val trace = tr.third ?: return@withContext EcgResult(null, tr.first, "no samples in the file")
        EcgResult(EcgQuality.score(trace.mv, trace.fs), tr.first, null)
    }

    /** (source, error, trace). */
    private fun readEcg(file: File): Triple<String, String?, EcgTrace?> {
        if (!file.isFile || file.length() == 0L) return Triple("none", "the file is missing or empty", null)
        val name = file.name.lowercase()
        return try {
            when {
                name.endsWith(".pdf") -> Triple("kardia_pdf", null, KardiaPdf.extract(file.readBytes()))
                name.endsWith(".atc") -> Triple("kardia_atc", null, AtcReader.read(file.readBytes()))
                name.endsWith(".csv") -> {
                    val (mv, fs) = EcgCsv.parseLead1Mv(file.readText())
                    Triple("ble", null, EcgTrace(fs, mv, emptyList()))
                }
                else -> {
                    // the share sheet hands over octet-stream: look at the first bytes instead of the name
                    val head = file.inputStream().use { s -> ByteArray(5).also { s.read(it) } }
                    val magic = String(head, Charsets.ISO_8859_1)
                    when {
                        magic.startsWith("%PDF") -> Triple("kardia_pdf", null, KardiaPdf.extract(file.readBytes()))
                        magic.startsWith("ALIVE") -> Triple("kardia_atc", null, AtcReader.read(file.readBytes()))
                        else -> Triple("unknown", "not a Kardia PDF or ATC file", null)
                    }
                }
            }
        } catch (e: Exception) {
            Triple("unknown", e.message ?: "the file could not be read", null)
        }
    }

    /** Copies a shared Kardia file next to the clip. Returns the path relative to the app's files directory. */
    fun importEcg(context: Context, source: Uri, pid: String, clipId: String): String {
        val name = context.contentResolver.openInputStream(source).use { input ->
            requireNotNull(input) { "the file could not be opened" }
            val head = ByteArray(5)
            val buffered = input.buffered()
            buffered.mark(8)
            buffered.read(head)
            buffered.reset()
            val ext = if (String(head, Charsets.ISO_8859_1).startsWith("%PDF")) "pdf" else "atc"
            val rel = "$pid/${clipId}_kardia.$ext"
            val out = appFile(context, rel)
            out.parentFile?.mkdirs()
            out.outputStream().use { buffered.copyTo(it) }
            rel
        }
        return name
    }

    /**
     * The clip's own stretch of the BLE ECG record, as sample indices, from `<clip>_sync.json`.
     *
     * The recorder keeps the ECG running before and after the clip so the beats either side of the boundary
     * are whole, but the participant's fingers may not be on the electrodes during that lead. Grading the
     * whole record would therefore count the lead as flat line and mark good clips borderline, so the grade
     * is taken over the clip window and the lead is left for analysis. Returns null when there is no window
     * to apply: an imported Kardia file, a recording from before the lead existed, or a file that will not
     * parse. Nothing here throws; an unreadable sync file just means the whole trace is graded, as before.
     */
    internal fun clipWindow(syncJson: String?, nSamples: Int): IntRange? {
        if (syncJson.isNullOrBlank()) return null
        val w = runCatching {
            Json.parseToJsonElement(syncJson).jsonObject["clip_window"]?.jsonObject
        }.getOrNull() ?: return null
        fun idx(k: String) = runCatching { w[k]?.jsonPrimitive?.doubleOrNull }.getOrNull()
        val from = idx("clip_start_sample_idx")?.toInt() ?: return null
        val to = idx("clip_stop_sample_idx")?.toInt() ?: return null
        val lo = from.coerceIn(0, nSamples)
        val hi = to.coerceIn(lo, nSamples)
        // a window that is empty, or that covers the record anyway, is not worth applying
        if (hi - lo < 1 || (lo == 0 && hi == nSamples)) return null
        return lo until hi
    }

    /**
     * Both grades for one clip of a visit: the palm video from the ROI log, and the ECG from the BLE capture or,
     * when there is none, from a Kardia file imported for this clip. The ECG heart rate becomes the reference
     * rate for the video SNR, so the two signals are checked against each other.
     */
    suspend fun gradeClip(
        context: Context,
        pid: String,
        clipId: String,
        expectedSeconds: Double,
    ): ClipGrades = withContext(Dispatchers.IO) {
        val notes = ArrayList<String>()
        val dir = appFile(context, pid)

        var ecgGrade: Grade? = null
        var rhythm: RhythmSummary? = null
        var source: String? = null
        var ecgRel: String? = null
        var refHr: Double? = null
        var devDet: String? = null
        var devHr: Int? = null
        var devMains: Int? = null
        var devFilter: Boolean? = null

        val ble = File(dir, "${clipId}_ecg_samples.csv")
        val imported = listOf("pdf", "atc").map { File(dir, "${clipId}_kardia.$it") }.firstOrNull { it.isFile }
        val ecgFile = if (ble.isFile && ble.length() > 0) ble else imported
        if (ecgFile == null) {
            notes.add("No ECG for this clip yet. Import the Kardia recording to grade it.")
        } else {
            val (src, err, trace) = readEcg(ecgFile)
            source = src
            ecgRel = "$pid/${ecgFile.name}"
            if (err != null || trace == null) {
                notes.add("The ECG file could not be read: ${err ?: "no samples"}")
            } else {
                // only the in-app BLE capture has a lead to trim; an imported file is whatever Kardia recorded
                val window = if (ecgFile == ble) {
                    clipWindow(readOrNull(File(dir, "${clipId}_sync.json")), trace.mv.size)
                } else null
                val mv = if (window == null) trace.mv else trace.mv.sliceArray(window)
                if (window != null) {
                    notes.add(
                        "ECG graded over the clip window (%.0f s of a %.0f s recording); the lead before and "
                            .format(mv.size / trace.fs, trace.mv.size / trace.fs) +
                            "after the clip is kept in the file but not graded."
                    )
                }
                ecgGrade = EcgQuality.score(mv, trace.fs)
                rhythm = EcgSummary.summarise(mv, trace.fs)
                refHr = ecgGrade.metrics["hr_bpm"]
                // A Kardia export carries the device's own reading on the page. It is the regulated
                // device's word, not ours, so it is carried through rather than recomputed or dropped.
                devDet = trace.determination
                devHr = trace.hrBpm
                devMains = trace.mainsHz
                devFilter = trace.enhancedFilter
                trace.warnings.forEach { notes.add("ECG file: $it") }
            }
        }

        val roiText = readOrNull(File(dir, "${clipId}_roi.csv"))
        var videoGrade: Grade? = null
        if (roiText == null) {
            notes.add("No ROI log: the clip was recorded outside the app, so the video cannot be graded here.")
        } else {
            videoGrade = try {
                val roi = RoiCsv.parse(roiText)
                val frames = readOrNull(File(dir, "${clipId}_frames.csv"))?.let { FramesCsv.parseTimesS(it) }
                org.samahealth.quality.VideoQuality.score(roi, frames, expectedSeconds, refHr)
            } catch (e: Exception) {
                notes.add("The ROI log could not be read: ${e.message}")
                null
            }
        }
        ClipGrades(videoGrade, ecgGrade, rhythm, source, ecgRel, notes, devDet, devHr, devMains, devFilter)
    }
}
