package org.samahealth.onboarding.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.Prefs

/** Per-tablet configuration, entered once by the study admin. */
@Composable
fun SettingsScreen(onDone: () -> Unit) {
    val p = LocalContext.current.container.prefs
    var url by remember { mutableStateOf(p.supabaseUrl ?: "") }
    var key by remember { mutableStateOf(p.supabaseAnonKey ?: "") }
    var device by remember { mutableStateOf(p.deviceCode) }
    var unit by remember { mutableStateOf(p.unitId) }
    var start by remember { mutableStateOf(p.pidBlockStart.toString()) }
    var end by remember { mutableStateOf(p.pidBlockEnd.toString()) }
    var plan by remember { mutableStateOf(p.clipPlan) }
    var rest by remember { mutableStateOf(p.restSeconds.toString()) }
    var stream by remember { mutableStateOf(p.defaultStream) }
    var mode by remember { mutableStateOf(p.captureMode) }
    var station by remember { mutableStateOf(p.station) }
    var localOnly by remember { mutableStateOf(p.localOnly) }
    var clipLen by remember { mutableStateOf(p.clipSecondsOverride.takeIf { it > 0 }?.toString() ?: "") }
    var autoStart by remember { mutableStateOf(p.autoStartRecording) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Tablet settings", style = MaterialTheme.typography.headlineSmall)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(checked = localOnly, onCheckedChange = { localOnly = it })
            Spacer(Modifier.width(12.dp))
            Text("Work on this device only")
        }
        Text(
            if (localOnly)
                "No sign-in and no upload. Everything stays on this phone, and nothing recorded carries an " +
                    "operator, so it is for trying the recorder out, not for study visits."
            else "Turn this on to use the recorder and the quality checks without a Supabase project.",
            style = MaterialTheme.typography.bodySmall,
        )
        if (!localOnly) {
            OutlinedTextField(url, { url = it }, label = { Text("Supabase project URL (https://xxxx.supabase.co)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(key, { key = it }, label = { Text("Supabase anon key") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        }
        OutlinedTextField(device, { device = it }, label = { Text("Device code (must match the devices table)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(unit, { unit = it }, label = { Text("Unit id (Pi box)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(start, { start = it }, label = { Text("PID block start") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f))
            OutlinedTextField(end, { end = it }, label = { Text("PID block end") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.weight(1f))
        }
        Text("Clip plan")
        for ((v, label) in listOf("1x60" to "One 60 s clip (BP1, rest, BP2, clip, BP3)", "2x30" to "Two 30 s clips (BP1, rest, clip 1, BP2, clip 2, BP3)")) {
            ChoiceRow(plan == v, label) { plan = v }
        }
        OutlinedTextField(clipLen, { clipLen = it.filter { ch -> ch.isDigit() } },
            label = { Text("Clip length in seconds (blank = the plan's 60 or 30)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(checked = autoStart, onCheckedChange = { autoStart = it })
            Spacer(Modifier.width(12.dp))
            Text("Start recording automatically")
        }
        Text(
            "The recorder rolls as soon as the camera has settled, so the operator can hold the rig and the " +
                "palm instead of the phone.",
            style = MaterialTheme.typography.bodySmall,
        )
        OutlinedTextField(rest, { rest = it }, label = { Text("Seated rest before the first clip (seconds)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
        Text("Default stream")
        for (v in listOf("pilot", "development", "model_selection", "test")) {
            ChoiceRow(stream == v, v) { stream = v }
        }
        Text("Capture mode")
        for (v in listOf("simultaneous", "sequential")) {
            ChoiceRow(mode == v, v) { mode = v }
        }
        Text("Station on this phone")
        for ((v, label) in listOf(
            Prefs.STATION_ENROL to "Enrol and history only",
            Prefs.STATION_SCAN to "Scan only",
            Prefs.STATION_BOTH to "Both on this phone",
        )) {
            ChoiceRow(station == v, label) { station = v }
        }
        Text("The station chooses which tab opens first, and whether this phone hands out new PIDs.",
            style = MaterialTheme.typography.bodySmall)
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = {
            val s = start.toIntOrNull()
            val e = end.toIntOrNull()
            val r = rest.toIntOrNull()
            error = when {
                !localOnly && !url.trim().startsWith("https://") -> "The project URL must start with https://"
                !localOnly && key.isBlank() -> "The anon key is required"
                s == null || e == null || s < 1 || e > 9999 || s > e -> "PID block must satisfy 1 <= start <= end <= 9999"
                r == null || r < 0 -> "Rest must be a whole number of seconds"
                clipLen.isNotBlank() && (clipLen.toIntOrNull() ?: 0) !in 5..3600 ->
                    "Clip length must be between 5 and 3600 seconds, or blank for the plan's own length"
                device.isBlank() -> "Device code is required"
                else -> null
            }
            if (error == null) {
                p.localOnly = localOnly
                if (!localOnly) { p.supabaseUrl = url; p.supabaseAnonKey = key }
                p.deviceCode = device; p.unitId = unit
                p.pidBlockStart = s!!; p.pidBlockEnd = e!!; p.clipPlan = plan; p.restSeconds = r!!
                p.defaultStream = stream; p.captureMode = mode; p.station = station
                p.clipSecondsOverride = clipLen.toIntOrNull()?.takeIf { it in 5..3600 } ?: 0
                p.autoStartRecording = autoStart
                onDone()
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("Save") }
    }
}

/**
 * A radio and its label as one target. The label used to be inert, so every choice on this screen could only
 * be changed by hitting the button itself, which is a small target for a gloved hand on a field phone.
 */
@Composable
private fun ChoiceRow(selected: Boolean, label: String, onSelect: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onSelect),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = onSelect)
        Text(label)
    }
}
