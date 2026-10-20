package org.samahealth.onboarding.ui

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.samahealth.crf.Conditions
import org.samahealth.crf.CrfEngine
import org.samahealth.crf.CrfJson
import org.samahealth.crf.Issue
import org.samahealth.crf.SurveyNavigator
import org.samahealth.crf.bool
import org.samahealth.crf.str
import org.samahealth.onboarding.container
import org.samahealth.onboarding.sync.SyncScheduler

data class QuestionUi(
    val id: String,
    val type: String,
    val label: String,
    val help: String?,
    val required: Boolean,
    val q: JsonObject,
    val value: JsonElement?,
    val errors: List<Issue>,
    val warning: String?,
    val derived: JsonElement?,
)

data class SurveyUi(
    val screenId: String,
    val title: String,
    val index: Int,
    val total: Int,
    val questions: List<QuestionUi>,
    val showErrors: Boolean,
    val stopped: Issue?,
    val isFirst: Boolean,
    val isLast: Boolean,
    val submissionStatus: String?,
    val errorCountByScreen: Map<String, Int>,
    val screenTitles: List<Pair<String, String>>,
    val warnings: List<Issue>,
    val status: String,
    val message: String?,
    val restSeconds: Int,
    val pid: String?,
)

/** Holds one participant's survey: the shared engine, the navigator, autosave, PID checks and submission. */
class SurveyViewModel(app: Application, private val visitUuid: String) : ViewModel() {
    private val c = app.container
    val engine: CrfEngine = c.engine()
    private var nav: SurveyNavigator? = null
    private var showErrors = false
    private var message: String? = null
    private var status = "draft"
    private var ticker: Job? = null
    private val _ui = MutableStateFlow<SurveyUi?>(null)
    val ui: StateFlow<SurveyUi?> = _ui
    private val _done = MutableStateFlow(false)
    val done: StateFlow<Boolean> = _done

    /** Latest unsaved state. One collector writes it, so saves never run concurrently or land out of order. */
    private class Draft(val answers: Map<String, JsonElement>, val log: JsonElement, val screen: String)
    private val pendingDraft = MutableStateFlow<Draft?>(null)

    init {
        viewModelScope.launch {
            val v = c.repo.visit(visitUuid)
            val saved = c.repo.loadAnswers(visitUuid)
            val n = SurveyNavigator(engine, if (saved.isEmpty()) engine.initialAnswers() else saved)
            if (v != null && saved.isNotEmpty()) {
                n.resume(v.currentScreen, SurveyNavigator.parseLog(CrfJson.parseToJsonElement(v.screenLogJson)))
            }
            status = v?.status ?: "draft"
            nav = n
            refresh()
            launch(Dispatchers.IO) {
                pendingDraft.filterNotNull().collect { d -> c.repo.saveDraft(visitUuid, engine, d.answers, d.log, d.screen) }
            }
            ticker = viewModelScope.launch {
                while (isActive) { delay(1000); if (_ui.value?.questions?.any { it.type == "computed" } == true) refresh() }
            }
        }
    }

    private fun refresh() {
        val n = nav ?: return
        val ev = n.evaluation()
        val screen = engine.screens[n.current]!!
        val qs = ev.visibleQuestions[n.current].orEmpty().map { id ->
            val q = engine.question(id)
            val req = bool(q["required"]) == true || (q["required_if"]?.let { Conditions.eval(it, ev.effective, engine.settings, ev.derived) } ?: false)
            QuestionUi(id, engine.type(q), str(q["label"]) ?: id, str(q["help"]), req, q, n.answers[id],
                ev.errors.filter { it.q == id }, ev.warnings.firstOrNull { it.q == id }?.message,
                ev.derived[str(q["compute"]) ?: id])
        }
        val vis = ev.visibleScreens
        _ui.value = SurveyUi(
            screenId = n.current, title = str(screen["title"]) ?: n.current, index = vis.indexOf(n.current) + 1, total = vis.size,
            questions = qs, showErrors = showErrors, stopped = ev.stopped, isFirst = vis.firstOrNull() == n.current, isLast = n.isLast(),
            submissionStatus = n.submissionStatus(), errorCountByScreen = ev.errors.groupingBy { it.screen }.eachCount(),
            screenTitles = vis.map { it to (str(engine.screens[it]!!["title"]) ?: it) }, warnings = ev.warnings, status = status,
            message = message, restSeconds = c.prefs.restSeconds, pid = str(n.answers["study_id"]),
        )
    }

    private fun save() {
        val n = nav ?: return
        pendingDraft.value = Draft(LinkedHashMap(n.answers), n.screenLogJson(), n.current)
    }

    fun set(id: String, value: JsonElement?) {
        if (status != "draft") return
        nav?.set(id, value)
        message = null
        refresh(); save()
    }

    fun next() {
        val n = nav ?: return
        if (n.current == "enrolment") {
            val pid = str(n.answers["study_id"])
            if (pid != null) {
                viewModelScope.launch {
                    val clash = withContext(Dispatchers.IO) { c.repo.pidUsedLocally(pid, visitUuid) }
                    if (clash) {
                        message = "PID $pid is already used by another participant on this tablet."
                        showErrors = true; refresh()
                    } else {
                        advance(n)
                        checkPidOnServer(pid)
                    }
                }
                return
            }
        }
        advance(n)
    }

    private fun advance(n: SurveyNavigator) {
        showErrors = !n.next()
        if (!showErrors) message = null
        refresh(); save()
    }

    /** Best-effort online check; the server's unique PID constraint is the final word at upload. */
    private fun checkPidOnServer(pid: String) {
        val client = c.client() ?: return
        val session = c.prefs.session ?: return
        viewModelScope.launch {
            val taken = withContext(Dispatchers.IO) {
                try { client.pidTakenElsewhere(session.accessToken, pid, visitUuid) } catch (e: Exception) { false }
            }
            if (taken) { message = "PID $pid already exists on the server. Go back and correct it before submitting."; refresh() }
        }
    }

    fun back() { nav?.back(); showErrors = false; refresh(); save() }

    fun goTo(screen: String) { nav?.goTo(screen); showErrors = false; refresh(); save() }

    fun nextPid() {
        viewModelScope.launch {
            val pid = withContext(Dispatchers.IO) { c.repo.nextPid() }
            if (pid == null) { message = "This tablet's PID block is used up. Ask the admin for a new block."; refresh() }
            else set("study_id", JsonPrimitive(pid))
        }
    }

    fun submit() {
        val n = nav ?: return
        val st = n.submissionStatus()
        if (st == null) { showErrors = true; message = "Some screens still have problems (listed above)."; refresh(); return }
        val ctx = mapOf(
            "operator" to JsonPrimitive(c.prefs.operatorCode ?: "unknown"), "unit_id" to JsonPrimitive(c.prefs.unitId),
            "app_ver" to JsonPrimitive(c.appVersion), "device_code" to JsonPrimitive(c.prefs.deviceCode),
            "capture_mode" to JsonPrimitive(c.prefs.captureMode),
        )
        val ex = n.export(ctx)
        val reason = if (st == "screen_fail") n.stopped()?.message else null
        viewModelScope.launch {
            withContext(Dispatchers.IO) {
                c.repo.saveDraft(visitUuid, engine, n.answers, n.screenLogJson(), n.current)
                c.repo.submit(visitUuid, st, ex.crf, reason)
            }
            SyncScheduler.syncNow(c.context)
            status = st
            _done.value = true
        }
    }

    fun reopen() {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { c.repo.reopen(visitUuid) }
            status = "draft"; refresh()
        }
    }

    fun discardDraft() {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { c.repo.deleteDraft(visitUuid) }
            _done.value = true
        }
    }

    override fun onCleared() { ticker?.cancel() }
}
