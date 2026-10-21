package org.swht.palm

import android.Manifest
import android.content.ContentValues
import android.content.pm.PackageManager
import android.media.MediaMetadataRetriever
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.MediaStore
import android.util.Log
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import android.widget.ToggleButton
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * One button, one minute: a locked 1080p30 palm clip and a simultaneous KardiaMobile 6L/Card ECG,
 * both timestamped on CLOCK_BOOTTIME so they need no cross-device sync marker to be aligned.
 *
 * Both streams come off the same phone, so there is exactly one clock in play and the alignment is
 * arithmetic rather than a fit. What remains is a constant bias: ECG samples are stamped when their
 * BLE packet arrives, which is later than the heartbeat by the minimum transport delay. That delay
 * is measured and reported in sync.json rather than being quietly absorbed.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "SamaPalm"
        private const val RECORD_SECONDS = 60
        private const val SETTLE_MS = 2000L
        private const val LOCK_SETTLE_MS = 400L
        private const val CLIP_ID = "clip1"
        private const val APP_VERSION = "SamaPalmRecorder 1.0"
    }

    private lateinit var previewView: PreviewView
    private lateinit var statusView: TextView
    private lateinit var traceView: TraceView
    private lateinit var btnRecord: Button
    private lateinit var btnTorch: ToggleButton
    private lateinit var studyIdField: EditText

    private var rig: CameraRig? = null
    private var ble: BleKardia? = null

    private enum class State { STARTING, READY, SETTLING, RECORDING, SAVING }
    @Volatile private var state = State.STARTING

    private var sessionDir: File? = null
    private var phoneDir: File? = null
    private var ecgDir: File? = null
    private var studyId = "SWHT-PP-003-0001"
    private var recordStartElapsedMs = 0L
    private var startWallNs = 0L
    private var videoFinalized = false
    private var lastSaved: String? = null

    private val ui = Handler(Looper.getMainLooper())

    private val tick = object : Runnable {
        override fun run() {
            updateStatus()
            traceView.invalidate()
            ui.postDelayed(this, 100)
        }
    }

    private val permLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { res ->
            if (res[Manifest.permission.CAMERA] == true &&
                res[Manifest.permission.RECORD_AUDIO] == true
            ) {
                onPermissionsGranted()
            } else {
                statusView.text = "Camera and Microphone are required.\n" +
                    "Enable them in Settings > Apps > SamaPalm, then reopen."
            }
        }

    private fun requiredPermissions(): Array<String> {
        val need = mutableListOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 31) {
            need += Manifest.permission.BLUETOOTH_SCAN
            need += Manifest.permission.BLUETOOTH_CONNECT
        }
        return need.toTypedArray()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        previewView = findViewById(R.id.preview)
        statusView = findViewById(R.id.status)
        traceView = findViewById(R.id.trace)
        btnRecord = findViewById(R.id.btnRecord)
        btnTorch = findViewById(R.id.btnTorch)
        studyIdField = findViewById(R.id.studyId)

        // targetSdk 36 draws edge to edge, so without this the control row sits underneath the
        // gesture navigation bar and the buttons are only half tappable.
        val controls = findViewById<android.view.View>(R.id.controls)
        ViewCompat.setOnApplyWindowInsetsListener(controls) { v, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            v.updatePadding(left = bars.left, right = bars.right, bottom = bars.bottom)
            insets
        }

        // Show the whole camera frame. FILL_CENTER (the default) scales a landscape sensor frame
        // to fill a portrait view and crops the sides away, so the operator would be framing the
        // palm against a view that is not what gets recorded.
        previewView.scaleType = PreviewView.ScaleType.FIT_CENTER

        btnRecord.setOnClickListener { onRecordPressed() }
        btnTorch.setOnCheckedChangeListener { _, checked ->
            if (state == State.READY) rig?.setTorch(checked)
        }

        val need = requiredPermissions()
        if (need.all {
                ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
            }) onPermissionsGranted() else permLauncher.launch(need)

        ui.post(tick)
    }

    private fun onPermissionsGranted() {
        val rigInstance = CameraRig(this, previewView)
        rig = rigInstance
        traceView.camera = rigInstance
        findViewById<RoiOverlay>(R.id.roi).rig = rigInstance
        rigInstance.bind(this, CameraRig.Mode.MONITOR) { ok ->
            if (ok) {
                state = State.READY
                rigInstance.setTorch(btnTorch.isChecked)
            } else {
                statusView.text = "Camera failed to start."
            }
        }
        val bleInstance = BleKardia(this)
        ble = bleInstance
        traceView.ecg = bleInstance
        bleInstance.start()
    }

    // ---- session ----

    private fun onRecordPressed() {
        when (state) {
            State.READY -> startSession()
            State.SETTLING, State.RECORDING -> stopSession(aborted = true)
            else -> {}
        }
    }

    private fun startSession() {
        val rigInstance = rig ?: return
        studyId = studyIdField.text.toString().trim().ifEmpty { "SWHT-PP-003-0000" }
        if (ble?.streaming != true) {
            Toast.makeText(
                this, "No ECG stream — recording video only", Toast.LENGTH_LONG
            ).show()
        }

        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val root = File(getExternalFilesDir(null), "sessions/${studyId}_$stamp")
        val phone = File(root, "phone").apply { mkdirs() }
        val ecg = File(root, "ecg").apply { mkdirs() }
        sessionDir = root
        phoneDir = phone
        ecgDir = ecg
        videoFinalized = false

        // Torch is set first: it changes the scene, so the settle must happen after it, not before.
        rigInstance.setTorch(btnTorch.isChecked)
        state = State.SETTLING
        btnRecord.text = "settling…"
        studyIdField.isEnabled = false

        // Swap to the video binding before settling: the exposure that gets locked must be the
        // one the encoder will actually see, and the two bindings do not share a configuration.
        rigInstance.bind(this, CameraRig.Mode.RECORD) { ok ->
            if (!ok || state != State.SETTLING) {
                Toast.makeText(this, "Camera failed to switch to recording", Toast.LENGTH_LONG).show()
                abortToReady()
                return@bind
            }
            rigInstance.setTorch(btnTorch.isChecked)
            ui.postDelayed({
                if (state != State.SETTLING) return@postDelayed
                val lock = rigInstance.lockControls()
                Log.i(TAG, "controls locked: $lock")
                ui.postDelayed({
                    if (state != State.SETTLING) return@postDelayed
                    beginRecording()
                }, LOCK_SETTLE_MS)
            }, SETTLE_MS)
        }
    }

    private fun beginRecording() {
        val rigInstance = rig ?: return
        val phone = phoneDir ?: return
        val ecg = ecgDir ?: return

        rigInstance.clock?.measure()
        ble?.startCapture(File(ecg, "kardia_0001_packets.csv"))
        startWallNs = System.currentTimeMillis() * 1_000_000L
        recordStartElapsedMs = SystemClock.elapsedRealtime()

        val ok = rigInstance.startRecording(
            File(phone, "$CLIP_ID.mp4"),
            File(phone, "${CLIP_ID}_frames.csv"),
        ) { event -> onVideoEvent(event) }

        if (!ok) {
            Toast.makeText(this, "Video failed to start", Toast.LENGTH_LONG).show()
            abortToReady()
            return
        }
        state = State.RECORDING
        btnRecord.text = "■ STOP"
        ui.postDelayed({ if (state == State.RECORDING) stopSession(aborted = false) },
            RECORD_SECONDS * 1000L)
    }

    private fun onVideoEvent(event: VideoRecordEvent) {
        if (event is VideoRecordEvent.Finalize) {
            if (event.hasError()) {
                Log.e(TAG, "video finalize error ${event.error}")
                Toast.makeText(this, "Video error ${event.error}", Toast.LENGTH_LONG).show()
            }
            if (!videoFinalized) {
                videoFinalized = true
                rig?.closeLogs()
                Thread { finaliseSession() }.start()
            }
        }
    }

    /** Returns to the monitoring binding and discards whatever the aborted session created. */
    private fun abortToReady() {
        state = State.READY
        btnRecord.isEnabled = true
        btnRecord.text = "● REC"
        studyIdField.isEnabled = true
        sessionDir?.deleteRecursively()
        rig?.bind(this, CameraRig.Mode.MONITOR) { rig?.setTorch(btnTorch.isChecked) }
    }

    private fun stopSession(aborted: Boolean) {
        if (state == State.SETTLING) {
            abortToReady()
            return
        }
        if (state != State.RECORDING) return
        state = State.SAVING
        btnRecord.isEnabled = false
        btnRecord.text = "SAVING…"
        if (aborted) Log.i(TAG, "session stopped early by operator")
        rig?.stopRecording()
        // Finalize normally arrives in well under a second; do not hang the session if it does not
        ui.postDelayed({
            if (!videoFinalized) {
                videoFinalized = true
                rig?.closeLogs()
                Thread { finaliseSession() }.start()
            }
        }, 5000)
    }

    /** Runs off the UI thread: recovers the ECG timeline, writes the contract files, exports. */
    private fun finaliseSession() {
        val root = sessionDir ?: return
        val phone = phoneDir ?: return
        val ecgDirLocal = ecgDir ?: return
        val rigInstance = rig
        val bleInstance = ble

        val clockDriftNs = rigInstance?.clock?.remeasureDriftNs() ?: 0L
        val capture = bleInstance?.finalise()

        if (capture != null && capture.lead1.isNotEmpty()) {
            writeEcgFiles(ecgDirLocal, capture, bleInstance)
        }
        writeClipMeta(phone, rigInstance, capture)
        writeSyncJson(root, rigInstance, capture, clockDriftNs)
        exportSession(root)
    }

    private fun writeEcgFiles(dir: File, cap: BleKardia.Capture, ble: BleKardia?) {
        val samplesFile = File(dir, "kardia_0001_samples.csv")
        FileWriter(samplesFile).buffered().use { w ->
            w.write("t_ref_ns,sample_idx,lead1_raw,lead2_raw,lead1_mv,lead2_mv\n")
            for (i in cap.lead1.indices) {
                val mv1 = cap.lead1[i] * BleKardia.MV_PER_COUNT
                val mv2 = cap.lead2[i] * BleKardia.MV_PER_COUNT
                w.write(
                    "${cap.tRefNs(i)},$i,${cap.lead1[i]},${cap.lead2[i]}," +
                        String.format(Locale.US, "%.5f,%.5f\n", mv1, mv2)
                )
            }
        }

        // wall clock of sample 0, back-calculated from the reference clock at this instant
        val nowRef = SystemClock.elapsedRealtimeNanos()
        val nowWallMs = System.currentTimeMillis()
        val t0WallMs = nowWallMs - (nowRef - cap.t0RefNs) / 1_000_000L
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date(t0WallMs))

        AtcWriter.write(
            file = File(dir, "kardia_0001.atc"),
            samples = cap.lead1,
            fsHz = Math.round(cap.measuredFsHz).toInt(),
            startIso = iso,
            info = mapOf(
                "phone_model" to "${Build.MANUFACTURER} ${Build.MODEL}",
                "recorder_sw" to APP_VERSION,
                "recorder_hw" to (ble?.deviceName ?: "KardiaMobile BLE"),
            ),
        )

        val meta = JSONObject()
            .put("start_wall_ts", iso)
            .put("duration_s", cap.lead1.size / cap.measuredFsHz)
            .put("fs", cap.measuredFsHz)
            .put("app_rhythm_label", JSONObject.NULL)
            .put("device_id", ble?.deviceAddress ?: JSONObject.NULL)
            .put("export_format", "atc")
            .put("source", "live BLE capture by $APP_VERSION, not an AliveCor app export")
            .put("ble_device_name", ble?.deviceName ?: JSONObject.NULL)
            .put("ble_mode", ble?.modeUsed ?: JSONObject.NULL)
            .put("channels", "lead1 = lead I (LA-RA), lead2 = lead II (LL-RA)")
            .put("nv_per_count_exact", AtcWriter.EXACT_NV_PER_COUNT)
            .put("atc_resolution_nv", AtcWriter.RESOLUTION_NV)
            .put(
                "scale_note",
                "counts are stored 1:1; the ATC integer resolution rounds " +
                    "${AtcWriter.EXACT_NV_PER_COUNT} nV/count to ${AtcWriter.RESOLUTION_NV}, so mV read " +
                    "back are 0.27 % high. The underlying 10 mV/65536 scale is itself provisional " +
                    "and electrically uncalibrated."
            )
            .put("t0_ref_ns", cap.t0RefNs)
            .put("sample_period_ns", cap.samplePeriodNs)
            .put("n_samples", cap.lead1.size)
            .put("gap_count", cap.gapCount)
            .put("missing_samples_zero_filled", cap.missingSamples)
        File(dir, "kardia_meta.json").writeText(meta.toString(2))
    }

    private fun writeClipMeta(
        dir: File, rig: CameraRig?, cap: BleKardia.Capture?
    ) {
        val mp4 = File(dir, "$CLIP_ID.mp4")
        var width = -1
        var height = -1
        var bitrate = -1L
        var durationMs = -1L
        var frameCount = -1
        if (mp4.exists()) {
            try {
                MediaMetadataRetriever().use { r ->
                    r.setDataSource(mp4.absolutePath)
                    width = r.extractMetadata(
                        MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH
                    )?.toIntOrNull() ?: -1
                    height = r.extractMetadata(
                        MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT
                    )?.toIntOrNull() ?: -1
                    bitrate = r.extractMetadata(
                        MediaMetadataRetriever.METADATA_KEY_BITRATE
                    )?.toLongOrNull() ?: -1L
                    durationMs = r.extractMetadata(
                        MediaMetadataRetriever.METADATA_KEY_DURATION
                    )?.toLongOrNull() ?: -1L
                    frameCount = r.extractMetadata(
                        MediaMetadataRetriever.METADATA_KEY_VIDEO_FRAME_COUNT
                    )?.toIntOrNull() ?: -1
                }
            } catch (e: Exception) {
                Log.w(TAG, "could not read back mp4 metadata", e)
            }
        }

        val meta = JSONObject()
            .put("app", "$APP_VERSION (CameraX + Camera2 interop)")
            .put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("os_build", Build.DISPLAY)
            .put("resolution", JSONArray(listOf(width, height)))
            .put("fps_nominal", 30)
            .put(
                "bitrate_mbps",
                if (bitrate > 0) bitrate / 1_000_000.0 else JSONObject.NULL
            )
            .put("iso", rig?.lastIso ?: -1)
            .put("exposure_ns", rig?.lastExposureNs ?: -1L)
            .put("wb_locked", true)
            .put("focus_locked", (rig?.lastFocusDistance ?: -1f) >= 0f)
            .put("stabilisation", false)
            .put("hdr", false)
            .put("torch", if (btnTorch.isChecked) "on" else "off")
            .put("capture_mode", "simultaneous")
            .put("start_wall_ns", startWallNs)
            .put("led_block", JSONObject.NULL)
            .put("study_id", studyId)
            .put("clip_id", CLIP_ID)
            // --- beyond CONTRACTS 3.5, recorded because the ingest cannot infer them ---
            .put("lock_applied", rig?.lockApplied ?: "none")
            .put("hardware_level", rig?.hardwareLevel ?: "unknown")
            .put("manual_sensor_supported", rig?.manualSensorSupported ?: false)
            .put("audio_track", "AAC mono, carries the rig buzzer markers")
            .put("roi_fraction", CameraRig.ROI_FRACTION)
            .put("negotiated_resolution", rig?.videoResolution ?: "unknown")
            .put(
                "roi_trace",
                "live operator aid only, not written: this device cannot bind ImageAnalysis " +
                    "alongside VideoCapture without the encoder dropping to 720p, so the palm " +
                    "readout runs between clips and the clip itself is recorded at full resolution"
            )
            .put("n_frames_logged", rig?.frameRows ?: 0L)
            .put("n_frames_in_container", frameCount)
            .put("container_duration_ms", durationMs)
            .put("requested_duration_s", RECORD_SECONDS)
            .put(
                "resolution_note",
                "read back from the written file, not the requested quality"
            )
        File(dir, "${CLIP_ID}_meta.json").writeText(meta.toString(2))
    }

    private fun writeSyncJson(
        root: File, rig: CameraRig?, cap: BleKardia.Capture?, clockDriftNs: Long
    ) {
        val clock = rig?.clock
        val camera = JSONObject()
            .put("timestamp_source", clock?.sourceName ?: "unknown")
            .put("on_reference_clock_natively", clock?.sourceIsRealtime ?: false)
            .put("offset_applied_ns", if (clock?.sourceIsRealtime == true) 0L else (clock?.offsetNs ?: 0L))
            .put("offset_uncertainty_ns", clock?.offsetUncertaintyNs ?: JSONObject.NULL)
            .put("offset_drift_during_session_ns", clockDriftNs)
            .put("n_frame_rows", rig?.frameRows ?: 0L)
            .put("n_capture_failures", rig?.droppedFrameRows ?: 0L)
            .put("n_roi_rows", rig?.ppgRows ?: 0L)
            .put("recording_start_ref_ns", rig?.recordingStartRefNs ?: 0L)

        val ecg = if (cap == null) JSONObject.NULL else JSONObject()
            .put("t0_ref_ns", cap.t0RefNs)
            .put("sample_period_ns", cap.samplePeriodNs)
            .put("measured_fs_hz", cap.measuredFsHz)
            .put("nominal_fs_hz", BleKardia.ECG_FS)
            .put("timeline_method", cap.envelopeFitUsed)
            .put("n_samples", cap.lead1.size)
            .put("n_packets", cap.packetCount)
            .put("arrival_delay_median_ns", cap.arrivalJitterMedianNs)
            .put("arrival_delay_p95_ns", cap.arrivalJitterP95Ns)
            .put("gap_count", cap.gapCount)
            .put("missing_samples_zero_filled", cap.missingSamples)

        val sync = JSONObject()
            .put("reference_clock", "CLOCK_BOOTTIME via SystemClock.elapsedRealtimeNanos")
            .put("camera", camera)
            .put("ecg", ecg)
            .put(
                "alignment",
                "phone/${CLIP_ID}_frames.csv sensor_ts_ns and ecg/kardia_0001_samples.csv t_ref_ns " +
                    "are both on the reference clock. Subtract them directly; no marker fit is " +
                    "needed because both streams were captured by one device."
            )
            .put(
                "known_bias",
                "ECG sample times are derived from the lower envelope of BLE packet arrivals, so " +
                    "they are late by the minimum transport delay of the link (not measurable from " +
                    "inside the phone). This is a constant within a session: it biases absolute PAT " +
                    "but not beat-to-beat variation. arrival_delay_p95_ns bounds the jitter above " +
                    "that floor."
            )
            .put(
                "caveat",
                "Clock arithmetic only. Nothing here has been verified against an external " +
                    "reference; the bench acceptance in palmppg/capture/README.md still applies."
            )
        File(root, "sync.json").writeText(sync.toString(2))
    }

    // ---- export ----

    /** App-private storage is not browsable, so mirror the tree into Download/SamaPalm/. */
    private fun exportSession(root: File) {
        val files = root.walkTopDown().filter { it.isFile }.toList()
        var ok = 0
        for (f in files) {
            val sub = f.parentFile?.relativeTo(root)?.path?.takeIf { it.isNotEmpty() }
            val rel = "${Environment.DIRECTORY_DOWNLOADS}/SamaPalm/${root.name}" +
                if (sub != null) "/$sub" else ""
            try {
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, f.name)
                    put(MediaStore.MediaColumns.MIME_TYPE, mimeFor(f.name))
                    put(MediaStore.MediaColumns.RELATIVE_PATH, rel)
                    put(MediaStore.MediaColumns.IS_PENDING, 1)
                }
                val uri = contentResolver.insert(
                    MediaStore.Downloads.EXTERNAL_CONTENT_URI, values
                ) ?: continue
                contentResolver.openOutputStream(uri)?.use { out ->
                    f.inputStream().use { it.copyTo(out) }
                }
                values.clear()
                values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                contentResolver.update(uri, values, null, null)
                ok++
            } catch (e: Exception) {
                Log.e(TAG, "export failed for ${f.name}", e)
            }
        }
        if (ok == files.size && files.isNotEmpty()) root.deleteRecursively()
        lastSaved = "Download/SamaPalm/${root.name} ($ok/${files.size})"
        runOnUiThread {
            state = State.READY
            btnRecord.isEnabled = true
            btnRecord.text = "● REC"
            studyIdField.isEnabled = true
            bumpClipSuffix()
            Toast.makeText(
                this, "Saved $ok/${files.size} files → Download/SamaPalm/${root.name}",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    /** Advances the trailing participant number so the next clip does not reuse the id. */
    private fun bumpClipSuffix() {
        val text = studyIdField.text.toString()
        val m = Regex("^(.*?)(\\d+)$").find(text) ?: return
        val width = m.groupValues[2].length
        val next = (m.groupValues[2].toLongOrNull() ?: return) + 1
        studyIdField.setText(m.groupValues[1] + next.toString().padStart(width, '0'))
    }

    private fun mimeFor(name: String) = when {
        name.endsWith(".mp4") -> "video/mp4"
        name.endsWith(".csv") -> "text/csv"
        name.endsWith(".json") -> "application/json"
        name.endsWith(".atc") -> "application/octet-stream"
        else -> "application/octet-stream"
    }

    // ---- status ----

    private fun updateStatus() {
        val sb = StringBuilder()
        val rigInstance = rig
        val bleInstance = ble

        when (state) {
            State.STARTING -> sb.append("starting…\n")
            State.READY -> sb.append("ready — ${RECORD_SECONDS}s clip\n")
            State.SETTLING -> sb.append("settling exposure, hold still…\n")
            State.RECORDING -> {
                val elapsed = (SystemClock.elapsedRealtime() - recordStartElapsedMs) / 1000
                val left = (RECORD_SECONDS - elapsed).coerceAtLeast(0)
                sb.append("● REC  ${left}s left\n")
            }
            State.SAVING -> sb.append("saving…\n")
        }

        if (bleInstance != null) {
            sb.append(bleInstance.statusLine)
            if (bleInstance.streaming) sb.append("  pkts ${bleInstance.packetCount}")
            sb.append('\n')
            val hr = bleInstance.heartRateBpm
            sb.append(if (hr > 0) "HR ~%.0f bpm".format(hr) else "HR --")
            sb.append("   ecg samples ${bleInstance.loggedSamples}\n")
        }

        if (rigInstance != null) {
            val clock = rigInstance.clock
            sb.append(
                "cam ${rigInstance.hardwareLevel} ${rigInstance.videoResolution} " +
                    "prev ${rigInstance.previewResolution}  " +
                    "lock ${rigInstance.lockApplied}  " +
                    "iso ${rigInstance.lastIso}  exp ${rigInstance.lastExposureNs / 1000}us\n"
            )
            sb.append(
                "clock ${clock?.sourceName ?: "?"}" +
                    (if (clock?.sourceIsRealtime == false) " (+offset applied)" else "") +
                    "   frames ${rigInstance.frameRows}  roi ${rigInstance.ppgRows}\n"
            )
            if (rigInstance.analysisBound) {
                val p = rigInstance.pulse
                sb.append(
                    if (p.bpm > 0) "palm ~%.0f bpm   perfusion %.2f%%   beats %d\n"
                        .format(p.bpm, p.perfusionPct, p.beats)
                    else "palm -- no pulse   perfusion %.2f%%  (cover the ROI)\n"
                        .format(p.perfusionPct)
                )
            } else {
                sb.append("palm readout paused — the clip needs the stream for 1080p\n")
            }
        }

        lastSaved?.let { if (state == State.READY) sb.append("last: $it") }
        statusView.text = sb.toString()
    }

    override fun onDestroy() {
        super.onDestroy()
        ui.removeCallbacksAndMessages(null)
        if (state == State.RECORDING) stopSession(aborted = true)
        rig?.shutdown()
        ble?.stop()
    }
}
