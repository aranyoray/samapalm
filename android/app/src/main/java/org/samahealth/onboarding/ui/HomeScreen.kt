package org.samahealth.onboarding.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.Prefs
import org.samahealth.onboarding.data.VisitEntity
import org.samahealth.onboarding.sync.SyncScheduler

private fun syncLabel(v: VisitEntity): String = when (v.syncState) {
    "local" -> "draft on this phone"
    "pending" -> "waiting to upload"
    "synced" -> "uploaded"
    "duplicate" -> "PID already used on the server: open and change the PID"
    "error" -> "upload error: ${v.syncError ?: ""}"
    else -> v.syncState
}

/** Shown when the server refused the sign-in: uploads stop until the operator signs in again. */
@Composable
fun SignInBanner(onSignIn: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Signed out by the server. Records are safe on this phone but will not upload until you sign in.",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            Button(onClick = onSignIn) { Text("Sign in again") }
        }
    }
}

/**
 * One station's records: the enrol tab lists enrolments (and any read-only v1 records left on the phone), the scan
 * tab lists scans. A new scan starts from a PID that was already enrolled.
 */
@Composable
fun RecordsScreen(
    part: String,
    onOpen: (String) -> Unit,
    onSettings: () -> Unit,
    onSignedOut: () -> Unit,
) {
    val ctx = LocalContext.current
    val c = ctx.container
    // one Flow instance for the screen's lifetime; a new Flow per recomposition would re-collect endlessly
    val visitsFlow = remember { c.repo.observeVisits() }
    val all by visitsFlow.collectAsState(initial = emptyList())
    val scope = rememberCoroutineScope()
    var signInRequired by remember { mutableStateOf(c.prefs.signInRequired) }
    var picking by remember { mutableStateOf(false) }
    LaunchedEffect(all) { signInRequired = c.prefs.signInRequired }

    val enrolTab = part == VisitEntity.PART_ENROL
    val rows = all.filter { it.part == part || (enrolTab && it.isLegacy) }
    val waiting = all.count { it.syncState == "pending" || it.syncState == "error" }

    fun startEnrol() = scope.launch {
        val e = c.engine(VisitEntity.PART_ENROL)
        val v = c.repo.newVisit(VisitEntity.PART_ENROL, e.flow().first(), c.prefs.engineSettings(VisitEntity.PART_ENROL))
        onOpen(v.visitUuid)
    }

    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (enrolTab) "Enrol" else "Scan", style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { SyncScheduler.syncNow(ctx) }) { Text("Upload now") }
            TextButton(onClick = onSettings) { Text("Settings") }
            TextButton(onClick = { c.prefs.session = null; onSignedOut() }) { Text("Sign out") }
        }
        if (signInRequired) SignInBanner(onSignIn = { c.prefs.signInRequired = false; onSignedOut() })
        Text("Operator ${c.prefs.operatorCode ?: "?"} · device ${c.prefs.deviceCode} · clip plan ${c.prefs.clipPlan} · " +
            "$waiting waiting to upload", style = MaterialTheme.typography.bodySmall)

        if (enrolTab) {
            // only a phone that enrols hands out PIDs, so two phones cannot allocate the same one
            if (c.prefs.station != Prefs.STATION_SCAN) {
                Button(onClick = { startEnrol() }, modifier = Modifier.fillMaxWidth()) { Text("New participant") }
            } else {
                Text("This phone is set to the scan station, so it does not start enrolments.",
                    style = MaterialTheme.typography.bodySmall)
            }
        } else {
            Button(onClick = { picking = true }, modifier = Modifier.fillMaxWidth()) { Text("New scan") }
        }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(rows, key = { it.visitUuid }) { v ->
                Card(Modifier.fillMaxWidth().clickable(enabled = !v.isLegacy) { onOpen(v.visitUuid) }) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(v.pid ?: "(no PID yet)", style = MaterialTheme.typography.titleMedium)
                        Text("${v.status} · ${syncLabel(v)}", style = MaterialTheme.typography.bodySmall)
                        Text("updated ${v.updatedAt.take(16).replace('T', ' ')}",
                            style = MaterialTheme.typography.bodySmall)
                        if (v.isLegacy) {
                            Text("Recorded by the older version of the app: it can still be uploaded, not edited.",
                                style = MaterialTheme.typography.bodySmall)
                        }
                        if (v.syncState == "error") {
                            OutlinedButton(onClick = {
                                scope.launch { c.repo.markSync(v, "pending", null); SyncScheduler.syncNow(ctx) }
                            }) { Text("Retry upload") }
                        }
                    }
                }
            }
        }
    }

    if (picking) {
        ScanPidPicker(
            onDismiss = { picking = false },
            onPick = { pid ->
                picking = false
                scope.launch {
                    val e = c.engine(VisitEntity.PART_SCAN)
                    val v = c.repo.newVisit(
                        VisitEntity.PART_SCAN, e.flow().first(), c.prefs.engineSettings(VisitEntity.PART_SCAN),
                    )
                    // a blank pid means "start the scan, the number comes later"
                    val seed = if (pid.isBlank()) emptyMap() else mapOf("study_id" to JsonPrimitive(pid))
                    c.repo.saveDraft(v.visitUuid, seed,
                        kotlinx.serialization.json.JsonArray(emptyList()), e.flow().first())
                    onOpen(v.visitUuid)
                }
            },
        )
    }
}

/**
 * Picks the PID for a scan: today's enrolments from the server that have no scan yet, this phone's own enrolments,
 * or a typed PID. A PID that is not on either list is allowed with a warning: the paper form is the record.
 */
@Composable
fun ScanPidPicker(onDismiss: () -> Unit, onPick: (String) -> Unit) {
    val c = LocalContext.current.container
    var typed by remember { mutableStateOf("") }
    var local by remember { mutableStateOf<List<String>>(emptyList()) }
    var queue by remember { mutableStateOf<List<String>>(emptyList()) }
    var note by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        local = withContext(Dispatchers.IO) { c.repo.submittedEnrolments().mapNotNull { it.pid } }
        val client = c.client()
        val session = c.prefs.session
        if (client != null && session != null) {
            queue = withContext(Dispatchers.IO) {
                try {
                    client.scanQueue(session.accessToken, 2).map { it.pid }
                } catch (e: Exception) {
                    note = "Could not reach the server; showing this phone's enrolments only."
                    emptyList()
                }
            }
        } else {
            note = "Offline: showing this phone's enrolments only."
        }
    }

    val offered = (queue + local).distinct()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Which participant?") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                note?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                if (offered.isEmpty()) {
                    Text("No enrolments waiting for a scan. Type the PID from the paper form.",
                        style = MaterialTheme.typography.bodySmall)
                } else {
                    Text("Enrolled, no scan yet", style = MaterialTheme.typography.labelLarge)
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(offered, key = { it }) { pid ->
                            Card(Modifier.fillMaxWidth().clickable { onPick(pid) }) {
                                Text(pid, Modifier.padding(10.dp))
                            }
                        }
                    }
                }
                OutlinedTextField(typed, { typed = it.trim() }, label = { Text("Or type the PID") },
                    singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                    modifier = Modifier.fillMaxWidth())
                if (typed.isNotEmpty() && typed !in offered) {
                    Text("This PID has no enrolment on this phone. Check the paper form before you go on.",
                        style = MaterialTheme.typography.bodySmall)
                }
                // enrolment may be happening on another phone, or only on paper; the recording need not wait
                TextButton(onClick = { onPick("") }, modifier = Modifier.fillMaxWidth()) {
                    Text("Start without a PID, add it later")
                }
            }
        },
        confirmButton = { TextButton(onClick = { if (typed.isNotEmpty()) onPick(typed) }, enabled = typed.isNotEmpty()) { Text("Use this PID") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
