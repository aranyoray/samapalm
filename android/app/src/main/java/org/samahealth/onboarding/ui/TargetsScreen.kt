package org.samahealth.onboarding.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import org.samahealth.crf.CrfJson
import org.samahealth.crf.Priority
import org.samahealth.crf.Strata
import org.samahealth.crf.Targets
import org.samahealth.crf.str
import org.samahealth.onboarding.container
import org.samahealth.onboarding.data.VisitEntity

private val MST_BANDS = (1..10).toList()
private val SEXES = listOf("F" to "Female", "M" to "Male", "Other" to "Other")

/**
 * How full each recruitment cell is, and a quick check of where one candidate would count. Counts come from the
 * server plus this phone's submitted enrolments that have not uploaded yet, so a run of offline enrolments does
 * not make a cell look emptier than it is.
 */
@Composable
fun TargetsScreen() {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var targets by remember { mutableStateOf<Targets?>(null) }
    var counts by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    var updated by remember { mutableStateOf<String?>(null) }
    var note by remember { mutableStateOf<String?>(null) }
    var sex by remember { mutableStateOf<String?>(null) }
    var mst by remember { mutableStateOf<Int?>(null) }
    var conditions by remember { mutableStateOf<Set<String>>(emptySet()) }

    suspend fun load(fromServer: Boolean) {
        val t = withContext(Dispatchers.IO) {
            val fromNet = if (fromServer) {
                val client = c.client()
                val session = c.prefs.session
                if (client == null || session == null) null
                else runCatching { client.targets(session.accessToken) }.getOrNull()
            } else {
                null
            }
            Strata.parseTargets(fromNet ?: c.targetsText)
        }
        targets = t
        val local = withContext(Dispatchers.IO) { localCounts(c) }
        val server = if (fromServer) {
            withContext(Dispatchers.IO) {
                val client = c.client()
                val session = c.prefs.session
                if (client == null || session == null) null
                else runCatching { client.strataCounts(session.accessToken, c.prefs.defaultStream) }.getOrNull()
            }
        } else {
            null
        }
        if (fromServer && server == null) note = "Could not reach the server; showing this phone's records only."
        else if (fromServer) { note = null; updated = c.repo.now().take(16).replace('T', ' ') }
        counts = merge(server ?: emptyMap(), local)
    }

    LaunchedEffect(Unit) { load(fromServer = true) }

    val t = targets
    val quick: Priority? = t?.let {
        val keys = quickKeys(c, sex, mst, conditions)
        if (keys.isEmpty()) null else Strata.priority(keys, counts, it)
    }

    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Targets", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { scope.launch { load(fromServer = true) } }) { Text("Refresh") }
        }
        updated?.let { Text("Counts as of $it", style = MaterialTheme.typography.bodySmall) }
        note?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        t?.note?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item {
                Card {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Quick check", style = MaterialTheme.typography.titleMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            for ((v, label) in SEXES) {
                                FilterChip(sex == v, { sex = if (sex == v) null else v }, { Text(label) })
                            }
                        }
                        Text("Skin tone band", style = MaterialTheme.typography.labelLarge)
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            for (b in MST_BANDS.take(5)) {
                                FilterChip(mst == b, { mst = if (mst == b) null else b }, { Text("$b") })
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            for (b in MST_BANDS.drop(5)) {
                                FilterChip(mst == b, { mst = if (mst == b) null else b }, { Text("$b") })
                            }
                        }
                        Text("Conditions", style = MaterialTheme.typography.labelLarge)
                        for (chunk in conditionValues(c).chunked(3)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                for ((v, label) in chunk) {
                                    FilterChip(v in conditions, {
                                        conditions = if (v in conditions) conditions - v else conditions + v
                                    }, { Text(label, style = MaterialTheme.typography.bodySmall) })
                                }
                            }
                        }
                        if (quick == null) {
                            Text("Pick at least one of the above.", style = MaterialTheme.typography.bodySmall)
                        } else {
                            Text(levelWords(quick.level), style = MaterialTheme.typography.titleMedium)
                            for (r in quick.reasons) {
                                Text("${r.label}: ${r.n} of ${r.target}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
            if (t != null) {
                item {
                    Card {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("Most needed now", style = MaterialTheme.typography.titleMedium)
                            for (r in Strata.mostNeeded(counts, t)) {
                                Text("${r.label}: ${r.n} of ${r.target}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
                items(Strata.cellTable(counts, t), key = { it.key }) { row ->
                    Card(colors = CardDefaults.cardColors()) {
                        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("${row.group} · ${row.label}", style = MaterialTheme.typography.bodyMedium)
                            LinearProgressIndicator(
                                progress = { row.fill.toFloat().coerceIn(0f, 1f) },
                                modifier = Modifier.fillMaxWidth(),
                            )
                            Text("${row.n} of ${row.target}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}

private fun levelWords(level: String): String = when (level) {
    "high" -> "High priority"
    "medium" -> "Medium priority"
    "low" -> "Low priority"
    "met" -> "These cells are already full"
    else -> "No recruitment cell matches"
}

/** Server counts plus this phone's submitted-but-not-uploaded enrolments. */
private fun merge(server: Map<String, Int>, local: Map<String, Int>): Map<String, Int> {
    val out = LinkedHashMap(server)
    for ((k, n) in local) out[k] = (out[k] ?: 0) + n
    return out
}

/** Strata keys of this phone's submitted enrol parts that have not reached the server yet. */
private suspend fun localCounts(c: org.samahealth.onboarding.AppContainer): Map<String, Int> {
    val out = HashMap<String, Int>()
    for (v in c.repo.unsyncedEnrolments()) {
        val crf = v.crfJson ?: continue
        val strata = runCatching {
            CrfJson.parseToJsonElement(crf).jsonObject["strata"] as? JsonArray
        }.getOrNull() ?: continue
        for (e in strata) str(e)?.let { out[it] = (out[it] ?: 0) + 1 }
    }
    return out
}

/** The condition choice list, read from the schema so the chips never drift from the survey. */
private fun conditionValues(c: org.samahealth.onboarding.AppContainer): List<Pair<String, String>> =
    runCatching {
        val schema = CrfJson.parseToJsonElement(c.schemaText).jsonObject
        val choices = schema["choices"]!!.jsonObject["conditions"] as JsonArray
        choices.mapNotNull { e ->
            val o = e.jsonObject
            val v = str(o["value"]) ?: return@mapNotNull null
            if (v == "none") null else v to (str(o["label"]) ?: v)
        }
    }.getOrDefault(emptyList())

/**
 * Builds the strata keys for the quick check by running the real engine over a partial enrol record, so the
 * chips and the survey always agree on what a candidate counts towards.
 */
private fun quickKeys(
    c: org.samahealth.onboarding.AppContainer,
    sex: String?,
    mst: Int?,
    conditions: Set<String>,
): List<String> {
    if (sex == null && mst == null && conditions.isEmpty()) return emptyList()
    val answers = HashMap<String, JsonElement>()
    sex?.let { answers["sex"] = JsonPrimitive(it) }
    mst?.let { answers["mst_band"] = JsonPrimitive(it) }
    if (conditions.isNotEmpty()) {
        answers["conditions"] = JsonArray(conditions.map { JsonPrimitive(it) })
    }
    return runCatching {
        val engine = c.engine(VisitEntity.PART_ENROL)
        val derived = engine.evaluate(answers).derived["strata"] as? JsonArray ?: return emptyList()
        derived.mapNotNull { str(it) }
    }.getOrDefault(emptyList())
}
