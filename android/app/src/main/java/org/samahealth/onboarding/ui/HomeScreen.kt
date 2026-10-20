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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.VisitEntity
import org.samahealth.onboarding.sync.SyncScheduler

private fun syncLabel(v: VisitEntity): String = when (v.syncState) {
    "local" -> "draft on this tablet"
    "pending" -> "waiting to upload"
    "synced" -> "uploaded"
    "duplicate" -> "PID already used on server: open and change the PID"
    "error" -> "upload error: ${v.syncError ?: ""}"
    else -> v.syncState
}

/** Participant list for this tablet with upload status; new participant; manual sync. */
@Composable
fun HomeScreen(onOpen: (String) -> Unit, onSettings: () -> Unit, onSignedOut: () -> Unit) {
    val ctx = LocalContext.current
    val c = ctx.container
    // one Flow instance for the screen's lifetime; a new Flow per recomposition would re-collect endlessly
    val visitsFlow = remember { c.repo.observeVisits() }
    val visits by visitsFlow.collectAsState(initial = emptyList())
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Participants", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { SyncScheduler.syncNow(ctx) }) { Text("Upload now") }
            TextButton(onClick = onSettings) { Text("Settings") }
            TextButton(onClick = { c.prefs.session = null; onSignedOut() }) { Text("Sign out") }
        }
        Text("Operator ${c.prefs.operatorCode ?: "?"} · device ${c.prefs.deviceCode} · clip plan ${c.prefs.clipPlan} · " +
            "${visits.count { it.syncState == "pending" || it.syncState == "error" }} waiting to upload", style = MaterialTheme.typography.bodySmall)
        Button(onClick = {
            scope.launch {
                val v = c.repo.newVisit(c.engine().flow().first())
                onOpen(v.visitUuid)
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("New participant") }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(visits, key = { it.visitUuid }) { v ->
                Card(Modifier.fillMaxWidth().clickable { onOpen(v.visitUuid) }) {
                    Column(Modifier.padding(12.dp)) {
                        Text(v.pid ?: "(no PID yet)", style = MaterialTheme.typography.titleMedium)
                        Text("${v.status} · ${syncLabel(v)}", style = MaterialTheme.typography.bodySmall)
                        Text("updated ${v.updatedAt.take(16).replace('T', ' ')}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}
