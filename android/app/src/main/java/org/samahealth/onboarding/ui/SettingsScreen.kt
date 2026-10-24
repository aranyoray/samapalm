package org.samahealth.onboarding.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
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
    var error by remember { mutableStateOf<String?>(null) }

    Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Tablet settings", style = MaterialTheme.typography.headlineSmall)
        OutlinedTextField(url, { url = it }, label = { Text("Supabase project URL (https://xxxx.supabase.co)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(key, { key = it }, label = { Text("Supabase anon key") }, singleLine = true, modifier = Modifier.fillMaxWidth())
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
            Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(plan == v, { plan = v }); Text(label) }
        }
        OutlinedTextField(rest, { rest = it }, label = { Text("Seated rest before the first clip (seconds)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
        Text("Default stream")
        for (v in listOf("pilot", "development", "model_selection", "test")) {
            Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(stream == v, { stream = v }); Text(v) }
        }
        Text("Capture mode")
        for (v in listOf("simultaneous", "sequential")) {
            Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(mode == v, { mode = v }); Text(v) }
        }
        Text("Station on this phone")
        for ((v, label) in listOf(
            Prefs.STATION_ENROL to "Enrol and history only",
            Prefs.STATION_SCAN to "Scan only",
            Prefs.STATION_BOTH to "Both on this phone",
        )) {
            Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(station == v, { station = v }); Text(label) }
        }
        Text("The station chooses which tab opens first, and whether this phone hands out new PIDs.",
            style = MaterialTheme.typography.bodySmall)
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = {
            val s = start.toIntOrNull()
            val e = end.toIntOrNull()
            val r = rest.toIntOrNull()
            error = when {
                !url.trim().startsWith("https://") -> "The project URL must start with https://"
                key.isBlank() -> "The anon key is required"
                s == null || e == null || s < 1 || e > 9999 || s > e -> "PID block must satisfy 1 <= start <= end <= 9999"
                r == null || r < 0 -> "Rest must be a whole number of seconds"
                device.isBlank() -> "Device code is required"
                else -> null
            }
            if (error == null) {
                p.supabaseUrl = url; p.supabaseAnonKey = key; p.deviceCode = device; p.unitId = unit
                p.pidBlockStart = s!!; p.pidBlockEnd = e!!; p.clipPlan = plan; p.restSeconds = r!!
                p.defaultStream = stream; p.captureMode = mode; p.station = station
                onDone()
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("Save") }
    }
}
