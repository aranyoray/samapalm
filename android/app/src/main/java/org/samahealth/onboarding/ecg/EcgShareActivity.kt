package org.samahealth.onboarding.ecg

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.VisitEntity
import org.samahealth.onboarding.quality.QualityRunner
import org.samahealth.onboarding.ui.MainActivity

private val CLIP_IDS = listOf("clip1", "clip1b", "clip2", "clip2b")

/**
 * Receives a recording shared from the Kardia app and attaches it to a clip of an open scan record. The file is
 * copied next to the clip and left in the inbox; the survey screen is the only thing that writes a visit's
 * answers, so it picks the file up when the visit opens.
 */
class EcgShareActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val uri: Uri? = if (Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(Intent.EXTRA_STREAM)
        }
        setContent {
            MaterialTheme {
                Surface { Picker(uri) }
            }
        }
    }

    @Composable
    private fun Picker(uri: Uri?) {
        val c = container
        val scope = rememberCoroutineScope()
        var drafts by remember { mutableStateOf<List<VisitEntity>>(emptyList()) }
        var error by remember { mutableStateOf<String?>(null) }
        LaunchedEffect(Unit) { drafts = withContext(Dispatchers.IO) { c.repo.activeScanDrafts() } }

        Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Attach this ECG", style = MaterialTheme.typography.headlineSmall)
            if (uri == null) {
                Text("No file was shared.", style = MaterialTheme.typography.bodyMedium)
            } else if (drafts.isEmpty()) {
                Text("No scan is open on this phone. Start the scan record first, then share the ECG again.",
                    style = MaterialTheme.typography.bodyMedium)
            } else {
                Text("Pick the participant and the clip it belongs to.", style = MaterialTheme.typography.bodySmall)
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(drafts, key = { it.visitUuid }) { v ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(v.pid ?: "(no PID yet)", style = MaterialTheme.typography.titleMedium)
                            for (clip in CLIP_IDS) {
                                Text(
                                    clip,
                                    Modifier.fillMaxWidth().clickable {
                                        val pid = v.pid
                                        if (uri == null || pid == null) {
                                            error = "This record has no PID yet."
                                            return@clickable
                                        }
                                        scope.launch {
                                            try {
                                                val rel = withContext(Dispatchers.IO) {
                                                    QualityRunner.importEcg(this@EcgShareActivity, uri, pid, clip)
                                                }
                                                c.repo.addEcgInbox(v.visitUuid, clip, rel)
                                                startActivity(
                                                    Intent(this@EcgShareActivity, MainActivity::class.java)
                                                        .putExtra(MainActivity.EXTRA_OPEN_VISIT, v.visitUuid)
                                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                                                )
                                                finish()
                                            } catch (e: Exception) {
                                                error = "The file could not be saved: ${e.message}"
                                            }
                                        }
                                    }.padding(vertical = 6.dp),
                                    style = MaterialTheme.typography.bodyLarge,
                                )
                            }
                        }
                    }
                }
            }
            TextButton(onClick = { finish() }) { Text("Cancel") }
        }
    }
}
