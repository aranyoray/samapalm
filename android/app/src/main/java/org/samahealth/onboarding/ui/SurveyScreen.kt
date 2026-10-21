package org.samahealth.onboarding.ui

import android.app.Activity
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
import org.samahealth.onboarding.container
import org.samahealth.onboarding.recorder.PalmRecorderActivity
import java.time.LocalDate

/** Monk Skin Tone scale reference colours (skintone.google). On-screen colour is a guide only; the band comes from the printed card. */
private val MST_COLOURS = listOf(0xFFF6EDE4, 0xFFF3E7DB, 0xFFF7EAD0, 0xFFEADABA, 0xFFD7BD96, 0xFFA07E56, 0xFF825C43, 0xFF604134, 0xFF3A312A, 0xFF292420)

@Composable
fun SurveyScreen(visitUuid: String, onExit: () -> Unit) {
    val app = LocalContext.current.applicationContext as Application
    val vm: SurveyViewModel = viewModel(key = visitUuid) { SurveyViewModel(app, visitUuid) }
    val ui by vm.ui.collectAsState()
    val done by vm.done.collectAsState()
    LaunchedEffect(done) { if (done) onExit() }
    val s = ui ?: run { Text("Loading...", Modifier.padding(24.dp)); return }
    val readOnly = s.status != "draft"

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
            if (readOnly) {
                Banner("Submitted on this tablet. Re-open only to correct an error; the server keeps every change in its audit log.",
                    MaterialTheme.colorScheme.secondaryContainer)
                OutlinedButton(onClick = vm::reopen) { Text("Re-open for correction") }
            }
            for (q in s.questions) {
                QuestionField(q, s.showErrors, readOnly, vm, s.restSeconds, s.pid)
            }
            if (s.screenId == "review") ReviewSummary(s, vm)
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

@Composable
private fun ReviewSummary(s: SurveyUi, vm: SurveyViewModel) {
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
private fun QuestionField(q: QuestionUi, showErrors: Boolean, readOnly: Boolean, vm: SurveyViewModel, restSeconds: Int, pid: String?) {
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
                if (!readOnly) OutlinedButton(onClick = vm::nextPid) { Text("Next PID from this tablet's block") }
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
            "clip" -> ClipInput(q, readOnly, pid, set)
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
private fun ClipInput(q: QuestionUi, readOnly: Boolean, pid: String?, set: (JsonElement?) -> Unit) {
    val ctx = LocalContext.current
    val o = (q.value as? JsonObject) ?: JsonObject(emptyMap())
    fun put(k: String, v: JsonElement) = set(JsonObject(o + (k to v)))
    val recorder = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        if (r.resultCode == Activity.RESULT_OK) {
            val path = r.data?.getStringExtra(PalmRecorderActivity.EXTRA_MP4) ?: return@rememberLauncherForActivityResult
            val samples = r.data?.getIntExtra(PalmRecorderActivity.EXTRA_ECG_SAMPLES, 0) ?: 0
            val seconds = r.data?.getDoubleExtra(PalmRecorderActivity.EXTRA_ECG_SECONDS, 0.0) ?: 0.0
            // the recorder captures the Kardia itself, so this is measured rather than self-reported
            var next = o + ("phone_file" to JsonPrimitive(path)) + ("ecg_samples" to JsonPrimitive(samples))
            if (samples > 0) {
                next = next + ("kardia_on" to JsonPrimitive(true)) + ("ecg_seconds" to JsonPrimitive(seconds))
            }
            set(JsonObject(next))
        }
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
        val ecgSamples = (o["ecg_samples"] as? JsonPrimitive)?.content?.toIntOrNull() ?: 0
        if (ecgSamples > 0) {
            Text("ECG captured on this device: $ecgSamples samples", style = MaterialTheme.typography.bodySmall)
        }
        for ((k, label) in listOf("kardia_on" to "Kardia recording during the clip", "beep_heard" to "Sync beeps heard (start and end)")) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = bool(o[k]) == true, onCheckedChange = { put(k, JsonPrimitive(it)) }, enabled = !readOnly)
                Text(label)
            }
        }
        Text("Live quality check")
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            for ((v, label) in listOf("pass" to "Pass", "fail" to "Fail (re-shoot once)")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = str(o["quality"]) == v, onClick = { put("quality", JsonPrimitive(v)) }, enabled = !readOnly)
                    Text(label)
                }
            }
        }
        var notes by remember(q.id) { mutableStateOf(str(o["notes"]) ?: "") }
        OutlinedTextField(value = notes, onValueChange = { notes = it; put("notes", JsonPrimitive(it)) }, label = { Text("Notes") },
            enabled = !readOnly, modifier = Modifier.fillMaxWidth())
        if (!readOnly) {
            OutlinedButton(enabled = pid != null, onClick = {
                recorder.launch(Intent(ctx, PalmRecorderActivity::class.java)
                    .putExtra(PalmRecorderActivity.EXTRA_STUDY_ID, pid)
                    .putExtra(PalmRecorderActivity.EXTRA_CLIP_ID, q.id)
                    .putExtra(PalmRecorderActivity.EXTRA_CAPTURE_MODE, ctx.container.prefs.captureMode))
            }) { Text("Record phone clip on this device (optional)") }
        }
        str(o["phone_file"])?.let { Text("Phone clip: $it", style = MaterialTheme.typography.bodySmall) }
        Spacer(Modifier.height(4.dp))
    }
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
