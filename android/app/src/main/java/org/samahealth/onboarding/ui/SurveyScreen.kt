package org.samahealth.onboarding.ui

import android.app.Activity
import android.view.WindowManager
import android.app.Application
import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import org.samahealth.crf.CrfEngine
import org.samahealth.crf.SurveyNavigator
import org.samahealth.crf.bool
import org.samahealth.crf.num
import org.samahealth.crf.str
import org.samahealth.crf.valueEquals
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.material3.AssistChip
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.CrfJson
import org.samahealth.crf.Priority
import org.samahealth.crf.Strata
import org.samahealth.onboarding.container
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.samahealth.onboarding.quality.QualityRunner
import org.samahealth.onboarding.data.VisitEntity
import org.samahealth.onboarding.quality.toJson
import org.samahealth.onboarding.ecg.ParticipantSummary
import org.samahealth.onboarding.recorder.PalmRecorderActivity
import java.time.LocalDate

/** Monk Skin Tone scale reference colours (skintone.google). On-screen colour is a guide only; the band comes from the printed card. */
private val MST_COLOURS = listOf(0xFFF6EDE4, 0xFFF3E7DB, 0xFFF7EAD0, 0xFFEADABA, 0xFFD7BD96, 0xFFA07E56, 0xFF825C43, 0xFF604134, 0xFF3A312A, 0xFF292420)

@Composable
fun SurveyScreen(visitUuid: String, onExit: () -> Unit, onOpenQuality: () -> Unit = {}) {
    val app = LocalContext.current.applicationContext as Application
    val vm: SurveyViewModel = viewModel(key = visitUuid) { SurveyViewModel(app, visitUuid) }
    val ui by vm.ui.collectAsState()
    val done by vm.done.collectAsState()
    LaunchedEffect(done) { if (done) onExit() }
    val s = ui ?: run { Text("Loading...", Modifier.padding(24.dp)); return }
    val readOnly = s.status != "draft"

    // the scan part runs the camera and the Kardia: the screen must not lock part way through a clip
    val ctx = LocalContext.current
    DisposableEffect(s.part) {
        val window = (ctx as? android.app.Activity)?.window
        if (s.part == "scan") window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        onDispose { window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
    }

    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(s.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                TextButton(onClick = onExit) { Text("Close") }
            }
            Text("Screen ${s.index} of ${s.total}" + if (readOnly) " · ${s.status} (read-only)" else "", style = MaterialTheme.typography.bodySmall)
        }
        HorizontalDivider()
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            s.stopped?.let { stop ->
                Banner(stop.message, MaterialTheme.colorScheme.errorContainer)
                if (!readOnly) Button(onClick = vm::submit) { Text("Save as screen failure") }
            }
            s.message?.let { Banner(it, MaterialTheme.colorScheme.tertiaryContainer) }
            // On-device mode only: jump past BP and setup straight to the palm clip, for trying the
            // recorder out. The preregistered scan brackets the clip with BP1/BP2/BP3, so this is not a
            // route a study visit can take: submission still needs every required answer.
            if (!readOnly && ctx.container.prefs.localOnly && s.part == VisitEntity.PART_SCAN &&
                !s.screenId.startsWith("clip")
            ) {
                OutlinedButton(onClick = vm::skipToClip) { Text("Skip to the palm clip (testing)") }
            }
            if (readOnly) {
                Banner("Submitted on this tablet. Re-open only to correct an error; the server keeps every change in its audit log.",
                    MaterialTheme.colorScheme.secondaryContainer)
                OutlinedButton(onClick = vm::reopen) { Text("Re-open for correction") }
            }
            for (q in s.questions) {
                QuestionField(q, s.showErrors, readOnly, vm, s.restSeconds, s.pid, visitUuid, onOpenQuality, s.part)
            }
            if (s.screenId.endsWith("review")) ReviewSummary(s, vm)
        }
        HorizontalDivider()
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = vm::back, enabled = !s.isFirst) { Text("Back") }
            if (s.status == "draft" && s.index == 1) TextButton(onClick = vm::discardDraft) { Text("Discard draft") }
            Spacer(Modifier.weight(1f))
            if (!readOnly) {
                if (s.isLast) Button(onClick = vm::submit, enabled = s.submissionStatus == "submitted") { Text("Submit") }
                else Button(onClick = vm::next) { Text("Next") }
            }
        }
    }
}

@Composable
private fun Banner(text: String, colour: Color) {
    Card(colors = CardDefaults.cardColors(containerColor = colour), modifier = Modifier.fillMaxWidth()) {
        Text(text, Modifier.padding(12.dp))
    }
}

/** Where this participant counts towards recruitment, shown on the enrol review before submitting. */
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun PriorityBadge(strata: List<String>) {
    val c = LocalContext.current.container
    var priority by remember(strata) { mutableStateOf<Priority?>(null) }
    LaunchedEffect(strata) {
        if (strata.isEmpty()) return@LaunchedEffect
        priority = withContext(Dispatchers.IO) {
            runCatching {
                val targets = Strata.parseTargets(c.targetsText)
                val counts = HashMap<String, Int>()
                val client = c.client()
                val session = c.prefs.session
                if (client != null && session != null) {
                    runCatching { client.strataCounts(session.accessToken, c.prefs.defaultStream) }
                        .getOrNull()?.let { counts.putAll(it) }
                }
                for (v in c.repo.unsyncedEnrolments()) {
                    val crf = v.crfJson ?: continue
                    val keys = runCatching {
                        (CrfJson.parseToJsonElement(crf).jsonObject["strata"] as? JsonArray)?.mapNotNull { str(it) }
                    }.getOrNull() ?: continue
                    for (k in keys) counts[k] = (counts[k] ?: 0) + 1
                }
                Strata.priority(strata, counts, targets)
            }.getOrNull()
        }
    }
    Text("Recruitment", style = MaterialTheme.typography.titleMedium)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        for (k in strata) {
            AssistChip(onClick = {}, label = { Text(k, style = MaterialTheme.typography.bodySmall) })
        }
    }
    val p = priority
    if (p == null) {
        Text("Working out where this participant counts…", style = MaterialTheme.typography.bodySmall)
    } else {
        val words = when (p.level) {
            "high" -> "High priority"
            "medium" -> "Medium priority"
            "low" -> "Low priority"
            "met" -> "These cells are already full"
            else -> "No recruitment cell matches"
        }
        val colour = when (p.level) {
            "high" -> MaterialTheme.colorScheme.primary
            "medium" -> MaterialTheme.colorScheme.tertiary
            else -> MaterialTheme.colorScheme.onSurface
        }
        Text(words, color = colour, style = MaterialTheme.typography.titleMedium)
        for (r in p.reasons) Text("· ${r.label}: ${r.n} of ${r.target}", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ReviewSummary(s: SurveyUi, vm: SurveyViewModel) {
    if (s.part == "enrol") {
        val strata = s.questions.firstOrNull { it.id == "strata" }?.derived as? JsonArray
        PriorityBadge(strata?.mapNotNull { str(it) } ?: emptyList())
    }
    Text("Screens", style = MaterialTheme.typography.titleMedium)
    for ((id, title) in s.screenTitles) {
        val n = s.errorCountByScreen[id] ?: 0
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text((if (n == 0) "OK  " else "$n to fix  ") + title, modifier = Modifier.weight(1f),
                color = if (n == 0) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error)
            if (id != s.screenId && s.status == "draft") TextButton(onClick = { vm.goTo(id) }) { Text("Edit") }
        }
    }
    if (s.warnings.isNotEmpty()) {
        Text("Flags", style = MaterialTheme.typography.titleMedium)
        for (w in s.warnings) Text("• ${w.message}")
    }
}

@Composable
private fun QuestionField(q: QuestionUi, showErrors: Boolean, readOnly: Boolean, vm: SurveyViewModel, restSeconds: Int, pid: String?, visitUuid: String, onOpenQuality: () -> Unit, part: String) {
    val err = if (showErrors) q.errors.firstOrNull()?.message else null
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        if (q.type != "info") {
            Text(q.label + if (q.required) " *" else "", fontWeight = FontWeight.Medium)
        }
        q.help?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        val set: (JsonElement?) -> Unit = { v -> vm.set(q.id, v) }
        when (q.type) {
            "info" -> Banner(q.label, MaterialTheme.colorScheme.surfaceVariant)
            "text" -> TextInput(q, readOnly, KeyboardType.Text, parse = { t -> if (t.isBlank()) null else JsonPrimitive(t) }, set = set)
            "pid" -> {
                TextInput(q, readOnly, KeyboardType.Ascii, parse = { t -> if (t.isBlank()) null else JsonPrimitive(t.trim().uppercase()) }, set = set)
                if (!readOnly && part != VisitEntity.PART_SCAN) {
                    OutlinedButton(onClick = vm::nextPid) { Text("Next PID from this tablet's block") }
                }
                // Scan first, PID later: the participant may be enrolled on another phone, or on paper only,
                // and the recording should not wait for the number. Submitting still needs it.
                if (!readOnly && part == VisitEntity.PART_SCAN && q.value == null) {
                    OutlinedButton(onClick = vm::skipPidForNow) { Text("Carry on without a PID") }
                }
            }
            "integer" -> TextInput(q, readOnly, KeyboardType.Number, parse = ::parseInt, set = set)
            "decimal" -> TextInput(q, readOnly, KeyboardType.Decimal, parse = ::parseDecimal, set = set)
            "date" -> {
                TextInput(q, readOnly, KeyboardType.Ascii, placeholder = "YYYY-MM-DD", parse = { t -> if (t.isBlank()) null else JsonPrimitive(t.trim()) }, set = set)
                if (!readOnly) TextButton(onClick = { set(JsonPrimitive(LocalDate.now().toString())) }) { Text("Today") }
            }
            "single" -> SingleChoice(q, vm.engine, readOnly, set)
            "multi" -> MultiChoice(q, vm.engine, readOnly, set)
            "mst" -> MstPicker(q, readOnly, set)
            "bp" -> BpInput(q, readOnly, set)
            "clip" -> ClipInput(q, readOnly, pid, visitUuid, vm.engine, set, onOpenQuality)
            "computed" -> Text(formatDerived(q.id, q.derived, restSeconds), style = MaterialTheme.typography.bodyLarge)
        }
        q.warning?.let { Text(it, color = MaterialTheme.colorScheme.tertiary, style = MaterialTheme.typography.bodySmall) }
        err?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
    }
}

private fun parseInt(t: String): JsonElement? = when {
    t.isBlank() -> null
    t.trim().toIntOrNull() != null -> JsonPrimitive(t.trim().toInt())
    else -> JsonPrimitive(t)                     // kept as text so the engine reports "whole number expected"
}

private fun parseDecimal(t: String): JsonElement? = when {
    t.isBlank() -> null
    t.trim().toDoubleOrNull() != null -> JsonPrimitive(t.trim().toDouble())
    else -> JsonPrimitive(t)
}

private fun displayText(v: JsonElement?): String = when (v) {
    null, JsonNull -> ""
    is JsonPrimitive -> v.content.let { if (!v.isString && it.endsWith(".0")) it.dropLast(2) else it }
    else -> v.toString()
}

/**
 * Text box bound to one answer. The typed text is kept locally (so "168." can be typed on the way to "168.5"), and is
 * replaced from the answer only when the answer changed from outside (for example the "Next PID" or "Today" buttons),
 * i.e. when the current text would not parse to the current answer.
 */
@Composable
private fun TextInput(q: QuestionUi, readOnly: Boolean, kb: KeyboardType, placeholder: String? = null,
                      parse: (String) -> JsonElement?, set: (JsonElement?) -> Unit) {
    var text by remember(q.id) { mutableStateOf(displayText(q.value)) }
    LaunchedEffect(q.value) {
        if (!valueEquals(parse(text) ?: JsonNull, q.value ?: JsonNull)) text = displayText(q.value)
    }
    OutlinedTextField(
        value = text,
        onValueChange = { text = it; set(parse(it)) },
        enabled = !readOnly,
        singleLine = true,
        placeholder = if (placeholder != null) { { Text(placeholder) } } else null,
        keyboardOptions = KeyboardOptions(keyboardType = kb),
        isError = q.errors.isNotEmpty() && text.isNotEmpty(),
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun SingleChoice(q: QuestionUi, engine: CrfEngine, readOnly: Boolean, set: (JsonElement?) -> Unit) {
    val cur = str(q.value)
    Column {
        for ((value, label) in engine.choices(q.q)) {
            Row(Modifier.fillMaxWidth().clickable(enabled = !readOnly) { set(JsonPrimitive(value)) }, verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = cur == value, onClick = { set(JsonPrimitive(value)) }, enabled = !readOnly)
                Text(label)
            }
        }
    }
}

@Composable
private fun MultiChoice(q: QuestionUi, engine: CrfEngine, readOnly: Boolean, set: (JsonElement?) -> Unit) {
    val cur = (q.value as? JsonArray)?.mapNotNull { str(it) } ?: emptyList()
    val exclusive = q.q["exclusive"]?.jsonArray?.mapNotNull { str(it) } ?: emptyList()
    fun toggle(value: String) {
        val next = when {
            value in cur -> cur - value
            value in exclusive -> listOf(value)                 // "none" clears the others
            else -> cur.filter { it !in exclusive } + value      // a real option clears "none"
        }
        set(if (next.isEmpty()) null else JsonArray(next.map { JsonPrimitive(it) }))
    }
    Column {
        for ((value, label) in engine.choices(q.q)) {
            Row(Modifier.fillMaxWidth().clickable(enabled = !readOnly) { toggle(value) }, verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = value in cur, onCheckedChange = { toggle(value) }, enabled = !readOnly)
                Text(label)
            }
        }
    }
}

@Composable
private fun MstPicker(q: QuestionUi, readOnly: Boolean, set: (JsonElement?) -> Unit) {
    val cur = num(q.value)?.toInt()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (row in listOf(1..5, 6..10)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (band in row) {
                    val selected = cur == band
                    Box(
                        Modifier.size(56.dp)
                            .background(Color(MST_COLOURS[band - 1]), RoundedCornerShape(8.dp))
                            .border(if (selected) 4.dp else 1.dp, if (selected) MaterialTheme.colorScheme.primary else Color.Gray, RoundedCornerShape(8.dp))
                            .clickable(enabled = !readOnly) { set(JsonPrimitive(band)) },
                        contentAlignment = Alignment.Center,
                    ) { Text("$band", color = if (band >= 6) Color.White else Color.Black, fontWeight = FontWeight.Bold) }
                }
            }
        }
        Text(if (cur == null) "No band selected" else "Selected: MST $cur", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun BpInput(q: QuestionUi, readOnly: Boolean, set: (JsonElement?) -> Unit) {
    val o = q.value as? JsonObject
    var sbp by remember(q.id) { mutableStateOf(displayText(o?.get("sbp"))) }
    var dbp by remember(q.id) { mutableStateOf(displayText(o?.get("dbp"))) }
    var hr by remember(q.id) { mutableStateOf(displayText(o?.get("hr"))) }
    fun push() {
        val s = sbp.trim().toIntOrNull(); val d = dbp.trim().toIntOrNull(); val h = hr.trim().toIntOrNull()
        if (s == null && d == null && h == null) { set(null); return }
        // the reading time is stamped when the reading is first complete and kept on later edits
        val ts = str(o?.get("wall_ts")) ?: if (s != null && d != null && h != null) SurveyNavigator.nowIso().content else null
        val map = LinkedHashMap<String, JsonElement>()
        map["sbp"] = s?.let { JsonPrimitive(it) } ?: JsonPrimitive(sbp)
        map["dbp"] = d?.let { JsonPrimitive(it) } ?: JsonPrimitive(dbp)
        map["hr"] = h?.let { JsonPrimitive(it) } ?: JsonPrimitive(hr)
        if (ts != null) map["wall_ts"] = JsonPrimitive(ts)
        set(JsonObject(map))
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for ((label, value, setter) in listOf(Triple("SBP", sbp) { v: String -> sbp = v }, Triple("DBP", dbp) { v: String -> dbp = v },
                                               Triple("HR", hr) { v: String -> hr = v })) {
            OutlinedTextField(value = value, onValueChange = { setter(it); push() }, label = { Text(label) }, enabled = !readOnly, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f))
        }
    }
    str(o?.get("wall_ts"))?.let { Text("Recorded at ${it.substring(11, 19)}", style = MaterialTheme.typography.bodySmall) }
}

@Composable
private fun ClipInput(
    q: QuestionUi,
    readOnly: Boolean,
    pid: String?,
    visitUuid: String,
    engine: CrfEngine,
    set: (JsonElement?) -> Unit,
    onOpenQuality: () -> Unit,
) {
    val ctx = LocalContext.current
    val c = ctx.container
    val scope = rememberCoroutineScope()
    val o = (q.value as? JsonObject) ?: JsonObject(emptyMap())
    val latest = rememberUpdatedState(o)
    fun put(k: String, v: JsonElement) = set(JsonObject(latest.value + (k to v)))
    var grading by remember(q.id) { mutableStateOf(false) }
    var notes by remember(q.id) { mutableStateOf<List<String>>(emptyList()) }
    val clipSeconds = if (c.prefs.clipPlan == "2x30") 30.0 else 60.0

    /** Runs both grades for this clip and folds them into the clip record. */
    fun grade(reason: String) {
        val id = pid ?: return
        scope.launch {
            grading = true
            val g = try {
                QualityRunner.gradeClip(ctx, id, q.id, clipSeconds)
            } catch (e: Exception) {
                notes = listOf("The quality check could not run: ${e.message}")
                grading = false
                return@launch
            }
            var next: Map<String, JsonElement> = latest.value
            g.video?.let {
                next = next + ("video_grade" to JsonPrimitive(it.level)) +
                    ("video_reasons" to JsonArray(it.reasons.map { r -> JsonPrimitive(r) })) +
                    ("video_metrics" to (it.toJson()["metrics"] ?: JsonObject(emptyMap())))
            }
            g.ecg?.let {
                next = next + ("ecg_grade" to JsonPrimitive(it.level)) +
                    ("ecg_reasons" to JsonArray(it.reasons.map { r -> JsonPrimitive(r) })) +
                    ("ecg_metrics" to (it.toJson()["metrics"] ?: JsonObject(emptyMap())))
            }
            g.source?.let { next = next + ("ecg_source" to JsonPrimitive(it)) }
            g.ecgFile?.let { next = next + ("ecg_file" to JsonPrimitive(QualityRunner.appFile(ctx, it).absolutePath)) }
            g.rhythm?.let { r ->
                next = next + ("rhythm_sentences" to JsonArray(r.sentences.map { sline -> JsonPrimitive(sline) }))
            }
            // Kept apart from the operator's own kardia_determination answer: this is what the export said,
            // read off the page, and it must not quietly fill in a CRF question the operator has to answer.
            g.deviceDetermination?.let { next = next + ("ecg_device_determination" to JsonPrimitive(it)) }
            g.deviceHrBpm?.let { next = next + ("ecg_device_hr" to JsonPrimitive(it)) }
            g.deviceMainsHz?.let { next = next + ("ecg_device_mains_hz" to JsonPrimitive(it)) }
            g.deviceEnhancedFilter?.let { next = next + ("ecg_device_enhanced_filter" to JsonPrimitive(it)) }
            // the grades pre-fill the operator's decision; the operator can still change it
            val bad = g.video?.level == "retake" || g.ecg?.level == "retake" ||
                bool(latest.value["phone_interrupted"]) == true
            next = next + ("quality" to JsonPrimitive(if (bad) "fail" else "pass"))
            set(JsonObject(next))
            notes = g.notes + if (reason.isEmpty()) emptyList() else listOf(reason)
            grading = false
        }
    }

    val recorder = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        if (r.resultCode == Activity.RESULT_OK) {
            val path = r.data?.getStringExtra(PalmRecorderActivity.EXTRA_MP4) ?: return@rememberLauncherForActivityResult
            val samples = r.data?.getIntExtra(PalmRecorderActivity.EXTRA_ECG_SAMPLES, 0) ?: 0
            val seconds = r.data?.getDoubleExtra(PalmRecorderActivity.EXTRA_ECG_SECONDS, 0.0) ?: 0.0
            // the recorder captures the Kardia itself, so this is measured rather than self-reported
            var next = latest.value + ("phone_file" to JsonPrimitive(path)) + ("ecg_samples" to JsonPrimitive(samples))
            if (samples > 0) {
                next = next + ("kardia_on" to JsonPrimitive(true)) + ("ecg_seconds" to JsonPrimitive(seconds))
            }
            // the recorder reports when the clip rolled and stopped, and whether it stopped early
            r.data?.getStringExtra(PalmRecorderActivity.EXTRA_STARTED_AT)?.let { next = next + ("started_at" to JsonPrimitive(it)) }
            r.data?.getStringExtra(PalmRecorderActivity.EXTRA_ENDED_AT)?.let { next = next + ("ended_at" to JsonPrimitive(it)) }
            val dur = r.data?.getDoubleExtra(PalmRecorderActivity.EXTRA_DURATION_S, -1.0) ?: -1.0
            if (dur >= 0) next = next + ("phone_duration_s" to JsonPrimitive(dur))
            val interrupted = r.data?.getBooleanExtra(PalmRecorderActivity.EXTRA_INTERRUPTED, false) ?: false
            next = next + ("phone_interrupted" to JsonPrimitive(interrupted))
            if (interrupted) next = next + ("quality" to JsonPrimitive("fail"))
            set(JsonObject(next))
            grade("")
        }
    }

    val importEcg = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val id = pid
        if (uri == null || id == null) return@rememberLauncherForActivityResult
        scope.launch {
            grading = true
            try {
                withContext(Dispatchers.IO) { QualityRunner.importEcg(ctx, uri, id, q.id) }
                grading = false
                grade("Kardia recording imported.")
            } catch (e: Exception) {
                notes = listOf("The Kardia file could not be imported: ${e.message}")
                grading = false
            }
        }
    }

    // files shared in from the Kardia app land in the inbox; the survey is the only writer of the answers
    val inbox by remember(visitUuid) { c.repo.observeEcgInbox(visitUuid) }.collectAsState(initial = emptyList())
    LaunchedEffect(inbox, q.id) {
        val mine = inbox.filter { it.clipId == q.id }
        if (mine.isEmpty()) return@LaunchedEffect
        mine.forEach { c.repo.consumeEcgInbox(it.id) }
        grade("Kardia recording attached from the Kardia app.")
    }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Button(enabled = !readOnly && o["started_at"] == null, onClick = { put("started_at", SurveyNavigator.nowIso()) }) { Text("Clip started") }
            Button(enabled = !readOnly && o["started_at"] != null && o["ended_at"] == null, onClick = { put("ended_at", SurveyNavigator.nowIso()) }) { Text("Clip ended") }
            if (!readOnly && (o["started_at"] != null || o["ended_at"] != null)) {
                TextButton(onClick = { set(JsonObject(o - "started_at" - "ended_at")) }) { Text("Reset times") }
            }
        }
        Text("Start ${str(o["started_at"])?.substring(11, 19) ?: "-"} · end ${str(o["ended_at"])?.substring(11, 19) ?: "-"}", style = MaterialTheme.typography.bodySmall)
        // The recorder runs the Kardia over BLE at the same time as the video and writes the ECG itself, so
        // whether the Kardia was recording is measured, not asked. The checkbox is only for a clip recorded
        // some other way, where there is nothing to count.
        val ecgSamples = (o["ecg_samples"] as? JsonPrimitive)?.content?.toIntOrNull() ?: 0
        val ecgSeconds = num(o["ecg_seconds"]) ?: 0.0
        if (ecgSamples > 0) {
            Text(
                "Kardia ECG recorded by this app alongside the video: $ecgSamples samples" +
                    if (ecgSeconds > 0) ", %.1f s".format(ecgSeconds) else "",
                style = MaterialTheme.typography.bodyMedium,
            )
        } else {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = bool(o["kardia_on"]) == true,
                    onCheckedChange = { put("kardia_on", JsonPrimitive(it)) }, enabled = !readOnly)
                Text("Kardia was recording during the clip")
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = bool(o["beep_heard"]) == true,
                onCheckedChange = { put("beep_heard", JsonPrimitive(it)) }, enabled = !readOnly)
            Text("Sync beeps heard (start and end)")
        }

        if (!readOnly) {
            OutlinedButton(enabled = pid != null, onClick = {
                recorder.launch(Intent(ctx, PalmRecorderActivity::class.java)
                    .putExtra(PalmRecorderActivity.EXTRA_STUDY_ID, pid)
                    .putExtra(PalmRecorderActivity.EXTRA_CLIP_ID, q.id)
                    .putExtra(PalmRecorderActivity.EXTRA_CAPTURE_MODE, c.prefs.captureMode)
                    .putExtra(PalmRecorderActivity.EXTRA_SECONDS, clipSeconds.toInt()))
            }) { Text("Record phone clip on this device") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(enabled = pid != null, onClick = {
                    importEcg.launch(arrayOf("application/pdf", "application/octet-stream", "*/*"))
                }) { Text("Import Kardia ECG") }
                OutlinedButton(enabled = pid != null && !grading, onClick = { grade("") }) { Text("Re-check quality") }
                OutlinedButton(onClick = onOpenQuality) { Text("Past recordings") }
            }
        }
        str(o["phone_file"])?.let { Text("Phone clip: $it", style = MaterialTheme.typography.bodySmall) }
        if (bool(o["phone_interrupted"]) == true) {
            Text("Recording stopped early (${num(o["phone_duration_s"])?.let { "%.0f s".format(it) } ?: "?"}): re-shoot this clip.",
                color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        if (grading) Text("Checking the recording…", style = MaterialTheme.typography.bodySmall)
        GradeLine("Palm video", str(o["video_grade"]), o["video_reasons"])
        GradeLine("ECG", str(o["ecg_grade"]), o["ecg_reasons"])
        for (line in EcgReadout.lines(
            metrics = o["ecg_metrics"] as? JsonObject,
            level = str(o["ecg_grade"]),
            rhythmSentences = o["rhythm_sentences"],
            deviceDetermination = str(o["ecg_device_determination"]),
            deviceHrBpm = num(o["ecg_device_hr"])?.toInt(),
        )) Text(line, style = MaterialTheme.typography.bodySmall)
        for (n in notes) Text(n, style = MaterialTheme.typography.bodySmall)

        // Only for a strip that was also run through the AliveCor app. The ordinary path records the ECG in
        // this app, and the rhythm on it is the study clinician's read, not something the operator types.
        Text("If the AliveCor app was also used, what it showed (optional)")
        val kardiaChoices = remember { engine.choices(JsonObject(mapOf("choices" to JsonPrimitive("kardia")))) }
        for ((value, label) in kardiaChoices) {
            Row(Modifier.fillMaxWidth().clickable(enabled = !readOnly) { put("kardia_determination", JsonPrimitive(value)) },
                verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = str(o["kardia_determination"]) == value, enabled = !readOnly,
                    onClick = { put("kardia_determination", JsonPrimitive(value)) })
                Text(label)
            }
        }
        var kardiaHr by remember(q.id) { mutableStateOf(num(o["kardia_hr"])?.let { "%.0f".format(it) } ?: "") }
        OutlinedTextField(
            value = kardiaHr,
            onValueChange = { t ->
                kardiaHr = t.filter { ch -> ch.isDigit() }
                val n = kardiaHr.toIntOrNull()
                if (n == null) set(JsonObject(latest.value - "kardia_hr")) else put("kardia_hr", JsonPrimitive(n))
            },
            label = { Text("Heart rate shown by the AliveCor app (bpm), optional") },
            singleLine = true, enabled = !readOnly,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth(),
        )

        Text("Live quality check")
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            for ((v, label) in listOf("pass" to "Pass", "fail" to "Fail (re-shoot once)")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = str(o["quality"]) == v, onClick = { put("quality", JsonPrimitive(v)) }, enabled = !readOnly)
                    Text(label)
                }
            }
        }
        var clipNotes by remember(q.id) { mutableStateOf(str(o["notes"]) ?: "") }
        OutlinedTextField(value = clipNotes, onValueChange = { clipNotes = it; put("notes", JsonPrimitive(it)) }, label = { Text("Notes") },
            enabled = !readOnly, modifier = Modifier.fillMaxWidth())

        if (pid != null && (o["ecg_grade"] != null || o["kardia_determination"] != null)) {
            OutlinedButton(onClick = {
                scope.launch {
                    try {
                        val f = withContext(Dispatchers.IO) {
                            ParticipantSummary.write(ctx, pid, latest.value, clinicianReviewed = false)
                        }
                        ctx.startActivity(Intent.createChooser(ParticipantSummary.shareIntent(ctx, f), "Share the summary"))
                    } catch (e: Exception) {
                        notes = listOf("The summary could not be made: ${e.message}")
                    }
                }
            }) { Text("ECG summary for participant") }
        }
        Spacer(Modifier.height(4.dp))
    }
}

/** One grade line with its plain-English reasons. */
@Composable
private fun GradeLine(what: String, level: String?, reasons: JsonElement?) {
    if (level == null) return
    val words = when (level) {
        "good" -> "Good"
        "borderline" -> "Borderline"
        "retake" -> "Retake"
        else -> level
    }
    val colour = when (level) {
        "retake" -> MaterialTheme.colorScheme.error
        "borderline" -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.onSurface
    }
    Text("$what: $words", color = colour, style = MaterialTheme.typography.bodyMedium)
    (reasons as? JsonArray)?.forEach { r -> str(r)?.let { Text("· $it", style = MaterialTheme.typography.bodySmall) } }
}

private fun formatDerived(id: String, v: JsonElement?, restSeconds: Int): String {
    if (v == null || v is JsonNull) return when (id) {
        "rest_elapsed" -> "BP1 not recorded yet"
        else -> "-"
    }
    return when (id) {
        "bmi" -> "${str(v) ?: (v as JsonPrimitive).content} kg/m²"
        "rest_elapsed" -> {
            val s = num(v)?.toLong() ?: 0L
            val left = restSeconds - s
            "${s / 60} min ${s % 60} s since BP1" + if (left > 0) " (target ${restSeconds / 60} min: ${left / 60} min ${left % 60} s to go)" else " (rest target reached)"
        }
        "bracket_flag" -> if (bool(v) == true) "Yes: readings differ by more than the limit" else "No"
        "recovery" -> when (str(v)) { "pass" -> "Rest target met before the first clip"; "short_rest" -> "Rest was shorter than the target"; else -> "-" }
        else -> (v as? JsonPrimitive)?.content ?: v.toString()
    }
}
