package org.samahealth.onboarding.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.CrfJson
import org.samahealth.crf.num
import org.samahealth.crf.str
import org.samahealth.quality.Grade
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.VisitEntity
import org.samahealth.onboarding.ecg.FounderOnnx
import org.samahealth.onboarding.quality.QualityRunner
import org.samahealth.onboarding.quality.toJson
import java.io.File

/** One clip of one visit, as the Quality tab lists it. */
data class ClipRow(
    val visitUuid: String,
    val pid: String,
    val clipId: String,
    val startedAt: String?,
    val videoGrade: String?,
    val ecgGrade: String?,
    val durationS: Double?,
    val interrupted: Boolean,
    val record: JsonObject,
)

private val CLIP_IDS = listOf("clip1", "clip1b", "clip2", "clip2b")

private fun gradeWords(level: String?): String = when (level) {
    "good" -> "Good"
    "borderline" -> "Borderline"
    "retake" -> "Retake"
    null -> "not graded"
    else -> level
}

/** Pulls the clip records out of this phone's scan visits, newest first. */
private suspend fun clipRows(c: org.samahealth.onboarding.AppContainer): List<ClipRow> =
    withContext(Dispatchers.IO) {
        val out = ArrayList<ClipRow>()
        for (v in c.repo.allVisits()) {
            if (v.part != VisitEntity.PART_SCAN) continue
            val answers = runCatching { CrfJson.parseToJsonElement(v.answersJson).jsonObject }.getOrNull() ?: continue
            for (id in CLIP_IDS) {
                val rec = answers[id] as? JsonObject ?: continue
                out.add(
                    ClipRow(
                        visitUuid = v.visitUuid, pid = v.pid ?: "(no PID)", clipId = id,
                        startedAt = str(rec["started_at"]),
                        videoGrade = str(rec["video_grade"]), ecgGrade = str(rec["ecg_grade"]),
                        durationS = num(rec["phone_duration_s"]),
                        interrupted = (rec["phone_interrupted"]?.toString() == "true"),
                        record = rec,
                    ),
                )
            }
        }
        out.sortedByDescending { it.startedAt ?: "" }
    }

/**
 * The quality of what this phone has recorded: every clip with its two grades, and a way to check a file that was
 * recorded outside the app. Grades here are signal-quality checks, not a reading of the trace.
 */
@Composable
fun QualityScreen(onOpenVisit: (String) -> Unit) {
    val c = LocalContext.current.container
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<ClipRow>>(emptyList()) }
    var detail by remember { mutableStateOf<ClipRow?>(null) }
    var busy by remember { mutableStateOf<String?>(null) }
    var progress by remember { mutableFloatStateOf(0f) }
    var adhoc by remember { mutableStateOf<String?>(null) }

    suspend fun reload() { rows = clipRows(c) }
    LaunchedEffect(Unit) { reload() }

    val pickVideo = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            busy = "Reading the video…"
            progress = 0f
            adhoc = try {
                val tmp = File(ctx.cacheDir, "check.mp4")
                withContext(Dispatchers.IO) {
                    ctx.contentResolver.openInputStream(uri).use { i -> tmp.outputStream().use { o -> i?.copyTo(o) } }
                }
                val r = QualityRunner.gradeVideo(ctx, tmp, 60.0) { progress = it }
                "Video: ${gradeWords(r.grade.level)} (${"%.1f".format(r.durationS)} s)\n" +
                    r.grade.reasons.joinToString("\n").ifEmpty { "No problems found." }
            } catch (e: Exception) {
                "The video could not be read: ${e.message}"
            }
            busy = null
        }
    }
    val pickEcg = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            busy = "Reading the ECG…"
            adhoc = try {
                val tmp = File(ctx.cacheDir, "check.ecg")
                withContext(Dispatchers.IO) {
                    ctx.contentResolver.openInputStream(uri).use { i -> tmp.outputStream().use { o -> i?.copyTo(o) } }
                }
                val r = QualityRunner.gradeEcg(ctx, tmp)
                if (r.grade == null) "The ECG could not be read: ${r.error}"
                else "ECG (${r.source}): ${gradeWords(r.grade.level)}\n" +
                    r.grade.reasons.joinToString("\n").ifEmpty { "No problems found." }
            } catch (e: Exception) {
                "The ECG could not be read: ${e.message}"
            }
            busy = null
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Quality", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { scope.launch { reload() } }) { Text("Refresh") }
        }
        Text("Automatic signal checks on what this phone recorded. The operator decides whether to retake.",
            style = MaterialTheme.typography.bodySmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { pickVideo.launch(arrayOf("video/*")) }) { Text("Check a video") }
            OutlinedButton(onClick = {
                pickEcg.launch(arrayOf("application/pdf", "application/octet-stream", "*/*"))
            }) { Text("Check an ECG file") }
        }
        busy?.let {
            Column { Text(it, style = MaterialTheme.typography.bodySmall); LinearProgressIndicator(Modifier.fillMaxWidth()) }
        }

        if (rows.isEmpty()) {
            Text("No clips on this phone yet.", style = MaterialTheme.typography.bodyMedium)
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(rows, key = { it.visitUuid + it.clipId }) { row ->
                Card(Modifier.fillMaxWidth().clickable { detail = row }) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("${row.pid} · ${row.clipId}", style = MaterialTheme.typography.titleMedium)
                        Text("Video ${gradeWords(row.videoGrade)} · ECG ${gradeWords(row.ecgGrade)}",
                            style = MaterialTheme.typography.bodyMedium)
                        val dur = row.durationS?.let { "%.1f s".format(it) } ?: "length unknown"
                        Text("$dur${if (row.interrupted) " · stopped early" else ""} · " +
                            (row.startedAt?.take(16)?.replace('T', ' ') ?: "no start time"),
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }

    adhoc?.let { text ->
        AlertDialog(
            onDismissRequest = { adhoc = null },
            title = { Text("File check") },
            text = { Text(text) },
            confirmButton = { TextButton(onClick = { adhoc = null }) { Text("Close") } },
        )
    }

    detail?.let { row ->
        ClipDetailDialog(
            row = row,
            modelAvailable = FounderOnnx.isAvailable(ctx),
            onDismiss = { detail = null },
            onOpenVisit = { detail = null; onOpenVisit(row.visitUuid) },
            onPreRead = {
                scope.launch {
                    busy = "Running the research model…"
                    detail = null
                    adhoc = preRead(ctx, row)
                    busy = null
                }
            },
            onReanalyse = {
                scope.launch {
                    busy = "Re-analysing ${row.clipId}…"
                    val seconds = if (c.prefs.clipPlan == "2x30") 30.0 else 60.0
                    val g = QualityRunner.gradeClip(ctx, row.pid, row.clipId, seconds)
                    busy = null
                    adhoc = buildString {
                        appendLine("Video: ${gradeWords(g.video?.level)}")
                        g.video?.reasons?.forEach { appendLine("  $it") }
                        appendLine("ECG: ${gradeWords(g.ecg?.level)}")
                        g.ecg?.reasons?.forEach { appendLine("  $it") }
                        EcgReadout.lines(
                            metrics = g.ecg?.toJson()?.get("metrics") as? JsonObject,
                            level = g.ecg?.level,
                            deviceDetermination = g.deviceDetermination,
                            deviceHrBpm = g.deviceHrBpm,
                        ).forEach { appendLine("  $it") }
                        g.notes.forEach { appendLine(it) }
                    }
                    detail = null
                }
            },
        )
    }
}

/**
 * The research model's reading of the clip's ECG. It is shown to the study team only, never to a participant,
 * and never without the line saying what it is (design section 9).
 */
private suspend fun preRead(ctx: android.content.Context, row: ClipRow): String {
    val path = str(row.record["ecg_file"]) ?: return "This clip has no ECG file to run the model on."
    val file = File(path)
    if (!file.isFile) return "The ECG file for this clip is missing: $path"
    val loaded = withContext(Dispatchers.IO) {
        runCatching {
            val t = readTrace(file)
            // The recorder runs the ECG past both ends of the clip (D-040), and the lead can be flat while
            // the participant settles onto the electrodes. The ectopy and pause labels combine as max over
            // windows, so one flat lead-in window could spike a label the clip itself never showed. Read the
            // clip's own stretch, the same window the quality grade uses.
            val window = if (file.name == "${row.clipId}_ecg_samples.csv") {
                val sync = File(file.parentFile, "${row.clipId}_sync.json").takeIf { it.isFile }?.readText()
                QualityRunner.clipWindow(sync, t.first.size)
            } else null
            Triple(if (window == null) t.first else t.first.sliceArray(window), t.second, window != null)
        }.getOrNull()
    } ?: return "The ECG file could not be read."
    val (mv, fs, windowed) = loaded
    val r = FounderOnnx.run(ctx, mv, fs)
        ?: return "The research model is not installed on this phone."
    if (r.nWindows == 0) return "The strip is shorter than 10 seconds, so the model has nothing to read."
    return buildString {
        appendLine("Research pre-read for the study clinician. Not a result for the participant, and not a")
        appendLine("reading of this recording on its own: a clinician reads every strip.")
        appendLine()
        if (windowed) {
            appendLine("Read over the clip window only; the ECG before and after the clip was left out.")
            appendLine()
        }
        appendLine("${r.nWindows} window(s)${if (r.polarityFlipped) ", strip was inverted and flipped" else ""}")
        appendLine()
        for (l in r.labels.take(6)) {
            appendLine("${"%.2f".format(l.prob)}  ${l.name.lowercase()}  (${l.rule} over windows)")
        }
    }
}

/** (samples in mV, sample rate) from whichever ECG file the clip record points at. */
private fun readTrace(file: File): Pair<DoubleArray, Double> {
    val name = file.name.lowercase()
    return when {
        name.endsWith(".pdf") -> org.samahealth.quality.KardiaPdf.extract(file.readBytes()).let { it.mv to it.fs }
        name.endsWith(".atc") -> org.samahealth.quality.AtcReader.read(file.readBytes()).let { it.mv to it.fs }
        else -> org.samahealth.quality.EcgCsv.parseLead1Mv(file.readText())
    }
}

@Composable
private fun ClipDetailDialog(
    row: ClipRow,
    modelAvailable: Boolean,
    onDismiss: () -> Unit,
    onOpenVisit: () -> Unit,
    onPreRead: () -> Unit,
    onReanalyse: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("${row.pid} · ${row.clipId}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Video: ${gradeWords(row.videoGrade)}", style = MaterialTheme.typography.titleSmall)
                for (r in reasonsOf(row.record, "video_reasons")) Text("· $r", style = MaterialTheme.typography.bodySmall)
                Text("ECG: ${gradeWords(row.ecgGrade)}", style = MaterialTheme.typography.titleSmall)
                for (r in reasonsOf(row.record, "ecg_reasons")) Text("· $r", style = MaterialTheme.typography.bodySmall)
                for (line in EcgReadout.lines(
                    metrics = row.record["ecg_metrics"] as? JsonObject,
                    level = row.ecgGrade,
                    rhythmSentences = row.record["rhythm_sentences"],
                    deviceDetermination = str(row.record["ecg_device_determination"]),
                    deviceHrBpm = num(row.record["ecg_device_hr"])?.toInt(),
                )) Text(line, style = MaterialTheme.typography.bodySmall)
                str(row.record["ecg_source"])?.let { Text("ECG from: $it", style = MaterialTheme.typography.bodySmall) }
                if (row.interrupted) Text("The recording stopped before the full clip length.",
                    style = MaterialTheme.typography.bodySmall)
                if (modelAvailable && row.ecgGrade != null) {
                    TextButton(onClick = onPreRead) { Text("Research pre-read (study clinician)") }
                }
            }
        },
        confirmButton = { TextButton(onClick = onReanalyse) { Text("Re-analyse") } },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onOpenVisit) { Text("Open visit") }
                TextButton(onClick = onDismiss) { Text("Close") }
            }
        },
    )
}

private fun reasonsOf(rec: JsonObject, key: String): List<String> =
    (rec[key] as? kotlinx.serialization.json.JsonArray)?.mapNotNull { str(it) } ?: emptyList()
