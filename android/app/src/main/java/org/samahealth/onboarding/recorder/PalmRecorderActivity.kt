/*
 * PalmRecorderActivity: Camera2 recorder for the OnePlus 12 (protocol sections 4.6 and 5), launched from a clip
 * screen of the onboarding survey.
 *
 * Records a 60 s 1920x1080 / 30 fps / H.264 clip with AAC audio (the rig buzzer is the sync marker) and, at the same
 * time, the KardiaMobile 6L/Card ECG over BLE. Both streams are timestamped on CLOCK_BOOTTIME by the same device, so
 * aligning them is subtraction rather than a marker fit — the clip screen's "Kardia recording" question stops being a
 * self-report and becomes a measured sample count.
 *
 * Outputs under Android/data/org.samahealth.onboarding/files/<PID>/:
 *   <clip>.mp4, <clip>_frames.csv (frame_idx, sensor_ts_ns on the reference clock, wall_ns, iso, exposure_ns),
 *   <clip>_meta.json, and when a Kardia was streaming: <clip>_ecg.atc (CONTRACTS 3.6), <clip>_ecg_samples.csv,
 *   <clip>_ecg_packets.csv, <clip>_ecg_meta.json, <clip>_sync.json.
 *
 * It must pass the bench acceptance (protocol 4.5) before it is used for study clips.
 */
package org.samahealth.onboarding.recorder

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.media.ImageReader
import android.media.MediaMetadataRetriever
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.util.Range
import android.view.Gravity
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class PalmRecorderActivity : Activity() {

    companion object {
        const val EXTRA_STUDY_ID = "study_id"
        const val EXTRA_CLIP_ID = "clip_id"
        const val EXTRA_CAPTURE_MODE = "capture_mode"
        const val EXTRA_MP4 = "mp4_path"
        /** Lead-I samples actually captured, so the survey records fact rather than a tick box. */
        const val EXTRA_ECG_SAMPLES = "ecg_samples"
        const val EXTRA_ECG_SECONDS = "ecg_seconds"

        const val ROI_FRACTION = 0.40f
        private const val TAG = "PalmRecorder"
        private const val RECORD_SECONDS = 60
        private const val SETTLE_MS = 2_000L
        private const val VIDEO_W = 1920
        private const val VIDEO_H = 1080
        private const val FPS = 30
        private const val ANALYSIS_W = 640
        private const val ANALYSIS_H = 480
    }

    private val studyId: String get() = intent.getStringExtra(EXTRA_STUDY_ID) ?: "SWHT-PP-003-0000"
    private val clipId: String get() = intent.getStringExtra(EXTRA_CLIP_ID) ?: "clip1"
    private val captureMode: String get() = intent.getStringExtra(EXTRA_CAPTURE_MODE) ?: "simultaneous"
    private val torchOn: Boolean get() = captureMode == "sequential"

    private lateinit var preview: SurfaceView
    private lateinit var overlay: RecorderOverlay
    private lateinit var statusView: TextView
    private lateinit var recordButton: Button
    private lateinit var outDir: File

    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var recorder: MediaRecorder? = null
    private var analysisReader: ImageReader? = null
    private var framesCsv: FileWriter? = null
    private var frameIdx = 0L
    private var droppedFrames = 0L

    @Volatile private var recording = false
    @Volatile private var finishing = false
    private var lockedIso = -1
    private var lockedExposureNs = -1L
    private var lockedFocusDistance = -1f
    private var lockApplied = "none"
    private var manualSensor = false
    private var hardwareLevel = "unknown"
    private var surfaceReady = false
    private var startWallNs = 0L
    private var recordStartElapsedMs = 0L

    private var clock: ClockBridge? = null
    private val ble by lazy { BleKardia(this) }
    private val pulse = PulseMeter()
    private val ppgRing = FloatArray(6 * FPS)
    private val peakRing = BooleanArray(6 * FPS)
    @Volatile private var ppgWriteIdx = 0
    @Volatile private var analysisBound = false

    private val thread = HandlerThread("camera").apply { start() }
    private val handler = Handler(thread.looper)
    private val ui = Handler(Looper.getMainLooper())

    private val tick = object : Runnable {
        override fun run() {
            updateStatus()
            overlay.ppgWriteIdx = ppgWriteIdx
            overlay.invalidate()
            ui.postDelayed(this, 100)
        }
    }

    // ---- lifecycle ----

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        preview = SurfaceView(this)
        overlay = RecorderOverlay(this).apply {
            ecg = ble
            pulse = this@PalmRecorderActivity.pulse
            ppgRing = this@PalmRecorderActivity.ppgRing
            peakRing = this@PalmRecorderActivity.peakRing
        }
        statusView = TextView(this).apply {
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.argb(150, 0, 0, 0))
            textSize = 11f
            typeface = android.graphics.Typeface.MONOSPACE
            setPadding(16, 12, 16, 12)
        }
        recordButton = Button(this).apply { text = "● REC ${RECORD_SECONDS}s" }

        // The camera frame is 16:9. A MATCH_PARENT SurfaceView would stretch it to whatever shape
        // the screen is, which both looks wrong and makes the ROI box point somewhere other than
        // the pixels being averaged, so the preview is held at the sensor's aspect ratio.
        val stage = AspectFrame(this, VIDEO_W.toFloat() / VIDEO_H)
        stage.addView(preview, FrameLayout.LayoutParams(MATCH, MATCH))
        stage.addView(overlay, FrameLayout.LayoutParams(MATCH, MATCH))

        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        root.addView(stage, FrameLayout.LayoutParams(MATCH, MATCH, Gravity.CENTER))
        root.addView(
            statusView,
            FrameLayout.LayoutParams(MATCH, WRAP, Gravity.TOP)
        )
        root.addView(
            recordButton,
            FrameLayout.LayoutParams(WRAP, WRAP, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL)
        )
        setContentView(root)

        preview.holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) {
                surfaceReady = true
                openCamera()
            }

            override fun surfaceChanged(h: SurfaceHolder, f: Int, w: Int, ht: Int) {}
            override fun surfaceDestroyed(holder: SurfaceHolder) {
                surfaceReady = false
                if (recording) stopRecording(cancelled = true)
            }
        })

        outDir = File(getExternalFilesDir(null), studyId).apply { mkdirs() }

        val perms = mutableListOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 31) {
            perms += Manifest.permission.BLUETOOTH_SCAN
            perms += Manifest.permission.BLUETOOTH_CONNECT
        }
        if (perms.any { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }) {
            requestPermissions(perms.toTypedArray(), 1)
        } else {
            ble.start()
        }

        recordButton.setOnClickListener {
            if (recording) stopRecording(cancelled = false) else startRecording()
        }
        ui.post(tick)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            ble.start()
            if (surfaceReady && camera == null) openCamera()
        }
    }

    override fun onDestroy() {
        ui.removeCallbacksAndMessages(null)
        handler.removeCallbacksAndMessages(null)
        if (recording) stopRecording(cancelled = true)
        ble.stop()
        thread.quitSafely()
        super.onDestroy()
    }

    // ---- camera ----

    private fun backCameraId(): String {
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        return cm.cameraIdList.first { id ->
            cm.getCameraCharacteristics(id)
                .get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        }
    }

    private fun openCamera() {
        if (!surfaceReady || camera != null) return
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        val id = backCameraId()
        val ch = cm.getCameraCharacteristics(id)

        // The reference clock is CLOCK_BOOTTIME. SENSOR_TIMESTAMP is only on it when the sensor
        // says REALTIME; otherwise it is CLOCK_MONOTONIC and must be offset, or every frame time
        // is wrong by however long the phone has been asleep since boot.
        clock = ClockBridge(ch.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE))
            .also { it.measure() }
        hardwareLevel = when (ch.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL)) {
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_LEGACY -> "LEGACY"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_LIMITED -> "LIMITED"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_FULL -> "FULL"
            CameraMetadata.INFO_SUPPORTED_HARDWARE_LEVEL_3 -> "LEVEL_3"
            else -> "unknown"
        }
        manualSensor = ch.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES)
            ?.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR) == true

        cm.openCamera(id, object : CameraDevice.StateCallback() {
            override fun onOpened(dev: CameraDevice) {
                camera = dev
                configureSession(dev)
            }

            override fun onDisconnected(dev: CameraDevice) { dev.close(); camera = null }
            override fun onError(dev: CameraDevice, error: Int) {
                Log.e(TAG, "camera error $error"); dev.close(); camera = null
            }
        }, handler)
    }

    private fun buildRecorder(): MediaRecorder {
        val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this)
        else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setVideoSource(MediaRecorder.VideoSource.SURFACE)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setOutputFile(File(outDir, "$clipId.mp4").absolutePath)
        r.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
        r.setVideoSize(VIDEO_W, VIDEO_H)
        r.setVideoFrameRate(FPS)
        // asking for 100 Mbit/s and recording what the encoder actually produced are different
        // things; the achieved rate is read back from the file at stop
        r.setVideoEncodingBitRate(100_000_000)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioSamplingRate(48_000)
        r.setAudioChannels(1)
        r.setAudioEncodingBitRate(128_000)
        r.prepare()
        return r
    }

    private fun buildAnalysisReader(): ImageReader =
        ImageReader.newInstance(
            ANALYSIS_W, ANALYSIS_H, android.graphics.ImageFormat.YUV_420_888, 2
        ).apply {
            setOnImageAvailableListener({ reader ->
                val image = try { reader.acquireLatestImage() } catch (_: Exception) { null }
                    ?: return@setOnImageAvailableListener
                try {
                    val refNs = clock?.toReferenceNs(image.timestamp) ?: image.timestamp
                    val mean = roiMeanLuma(image)
                    if (mean != null) {
                        val ac = pulse.push(refNs, mean)
                        ppgRing[ppgWriteIdx] = ac
                        peakRing[ppgWriteIdx] = pulse.lastSampleWasPeak
                        ppgWriteIdx = (ppgWriteIdx + 1) % ppgRing.size
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "analysis frame failed", e)
                } finally {
                    image.close()
                }
            }, handler)
        }

    /** Mean luma over the centred ROI — the same fraction [RecorderOverlay] draws. */
    private fun roiMeanLuma(image: android.media.Image): Double? {
        val plane = image.planes.firstOrNull() ?: return null
        val buf = plane.buffer
        val stride = plane.rowStride
        val pix = plane.pixelStride
        val w = image.width
        val h = image.height
        val half = ROI_FRACTION / 2f
        val x0 = ((0.5f - half) * w).toInt().coerceIn(0, w - 2)
        val x1 = ((0.5f + half) * w).toInt().coerceIn(x0 + 1, w)
        val y0 = ((0.5f - half) * h).toInt().coerceIn(0, h - 2)
        val y1 = ((0.5f + half) * h).toInt().coerceIn(y0 + 1, h)
        var sum = 0L
        var n = 0
        var y = y0
        while (y < y1) {
            val base = y * stride
            var x = x0
            while (x < x1) {
                val off = base + x * pix
                if (off < buf.limit()) { sum += (buf.get(off).toInt() and 0xFF); n++ }
                x += 2
            }
            y += 2
        }
        return if (n == 0) null else sum.toDouble() / n
    }

    private fun configureSession(dev: CameraDevice) {
        val rec = buildRecorder().also { recorder = it }
        val reader = buildAnalysisReader().also { analysisReader = it }
        val withAnalysis = listOf(preview.holder.surface, rec.surface, reader.surface)
        val withoutAnalysis = listOf(preview.holder.surface, rec.surface)

        val cb = object : CameraCaptureSession.StateCallback() {
            override fun onConfigured(s: CameraCaptureSession) {
                session = s
                startSettle(dev, s, if (analysisBound) withAnalysis else withoutAnalysis)
            }

            override fun onConfigureFailed(s: CameraCaptureSession) {
                s.close()
                if (analysisBound) {
                    // the pulse readout is the expendable stream, never the clip
                    Log.w(TAG, "3-surface session failed, retrying without the analysis stream")
                    analysisBound = false
                    analysisReader?.close(); analysisReader = null
                    @Suppress("DEPRECATION")
                    dev.createCaptureSession(withoutAnalysis, this, handler)
                } else {
                    Log.e(TAG, "capture session could not be configured")
                }
            }
        }
        analysisBound = true
        @Suppress("DEPRECATION")
        dev.createCaptureSession(withAnalysis, cb, handler)
    }

    private fun applyFixedControls(b: CaptureRequest.Builder, lock: Boolean) {
        b.set(CaptureRequest.CONTROL_MODE, CameraMetadata.CONTROL_MODE_AUTO)
        b.set(CaptureRequest.CONTROL_SCENE_MODE, CameraMetadata.CONTROL_SCENE_MODE_DISABLED)
        b.set(
            CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE,
            CameraMetadata.CONTROL_VIDEO_STABILIZATION_MODE_OFF
        )
        b.set(
            CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE,
            CameraMetadata.LENS_OPTICAL_STABILIZATION_MODE_OFF
        )
        b.set(CaptureRequest.NOISE_REDUCTION_MODE, CameraMetadata.NOISE_REDUCTION_MODE_OFF)
        b.set(CaptureRequest.EDGE_MODE, CameraMetadata.EDGE_MODE_OFF)
        b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_FAST)
        b.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(FPS, FPS))
        b.set(
            CaptureRequest.FLASH_MODE,
            if (torchOn) CameraMetadata.FLASH_MODE_TORCH else CameraMetadata.FLASH_MODE_OFF
        )
        if (!lock) {
            b.set(CaptureRequest.CONTROL_AE_LOCK, false)
            b.set(CaptureRequest.CONTROL_AWB_LOCK, false)
            b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_AUTO)
            return
        }
        // Measured on a OnePlus 12 (LEVEL_3): true manual sensor control holds the exposure far
        // better than CONTROL_AE_LOCK, which some OEM pipelines still nudge. Fall back to the lock
        // where MANUAL_SENSOR is not offered, and record which was used.
        lockApplied = if (manualSensor && lockedIso > 0 && lockedExposureNs > 0) {
            b.set(CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_OFF)
            b.set(CaptureRequest.SENSOR_SENSITIVITY, lockedIso)
            b.set(CaptureRequest.SENSOR_EXPOSURE_TIME, lockedExposureNs)
            b.set(CaptureRequest.SENSOR_FRAME_DURATION, 1_000_000_000L / FPS)
            "manual_sensor"
        } else {
            b.set(CaptureRequest.CONTROL_AE_LOCK, true)
            "ae_lock"
        }
        b.set(CaptureRequest.CONTROL_AWB_LOCK, true)
        if (lockedFocusDistance >= 0f) {
            b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_OFF)
            b.set(CaptureRequest.LENS_FOCUS_DISTANCE, lockedFocusDistance)
            lockApplied += "+af_off"
        }
    }

    private val frameLogger = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(
            s: CameraCaptureSession, req: CaptureRequest, result: TotalCaptureResult
        ) {
            val iso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            val exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            val focus = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            if (!recording) {
                lockedIso = iso; lockedExposureNs = exp; lockedFocusDistance = focus
                return
            }
            val ts = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            val refNs = clock?.toReferenceNs(ts) ?: ts
            val wallNs = System.currentTimeMillis() * 1_000_000L
            try {
                framesCsv?.write("$frameIdx,$refNs,$wallNs,$iso,$exp\n")
                frameIdx += 1
            } catch (_: Exception) {
                droppedFrames++
            }
        }
    }

    /** Phase 1: let exposure, white balance and focus settle on the palm with the torch already set. */
    private fun startSettle(dev: CameraDevice, s: CameraCaptureSession, surfaces: List<Surface>) {
        val settle = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
        surfaces.forEach { settle.addTarget(it) }
        applyFixedControls(settle, lock = false)
        settle.set(CaptureRequest.CONTROL_AF_TRIGGER, CameraMetadata.CONTROL_AF_TRIGGER_START)
        s.setRepeatingRequest(settle.build(), frameLogger, handler)
    }

    // ---- recording ----

    private fun startRecording() {
        val dev = camera ?: return
        val s = session ?: return
        if (recording || finishing) return
        recordButton.isEnabled = false
        recordButton.text = "settling…"
        // Phase 2: pin everything at the settled values, then roll.
        handler.postDelayed({ lockAndRecord(dev, s) }, SETTLE_MS)
    }

    private fun lockAndRecord(dev: CameraDevice, s: CameraCaptureSession) {
        val surfaces = mutableListOf(preview.holder.surface, recorder!!.surface)
        if (analysisBound) analysisReader?.surface?.let { surfaces += it }
        val locked = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
        surfaces.forEach { locked.addTarget(it) }
        applyFixedControls(locked, lock = true)

        framesCsv = FileWriter(File(outDir, "${clipId}_frames.csv")).apply {
            write("frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns\n")
        }
        frameIdx = 0
        droppedFrames = 0
        clock?.measure()
        ble.startCapture(File(outDir, "${clipId}_ecg_packets.csv"))
        startWallNs = System.currentTimeMillis() * 1_000_000L
        recordStartElapsedMs = SystemClock.elapsedRealtime()
        recorder?.start()
        recording = true
        s.setRepeatingRequest(locked.build(), frameLogger, handler)

        ui.post {
            recordButton.isEnabled = true
            recordButton.text = "■ STOP"
        }
        handler.postDelayed({ if (recording) stopRecording(cancelled = false) },
            RECORD_SECONDS * 1000L)
    }

    private fun stopRecording(cancelled: Boolean) {
        if (!recording || finishing) return
        finishing = true
        recording = false
        handler.removeCallbacksAndMessages(null)
        try { session?.stopRepeating() } catch (_: Exception) {}
        try { recorder?.stop() } catch (e: Exception) { Log.e(TAG, "recorder stop", e) }
        recorder?.release(); recorder = null
        try { framesCsv?.flush(); framesCsv?.close() } catch (_: Exception) {}
        framesCsv = null

        val capture = ble.finalise()
        if (capture != null && capture.lead1.isNotEmpty()) writeEcgFiles(capture)
        writeMeta()
        writeSyncJson(capture)

        analysisReader?.close(); analysisReader = null
        session?.close(); session = null
        camera?.close(); camera = null

        if (cancelled) {
            ui.post { finish() }
            return
        }
        val samples = capture?.lead1?.size ?: 0
        val seconds = if (capture != null && capture.measuredFsHz > 0)
            capture.lead1.size / capture.measuredFsHz else 0.0
        setResult(
            RESULT_OK,
            Intent()
                .putExtra(EXTRA_MP4, File(outDir, "$clipId.mp4").absolutePath)
                .putExtra(EXTRA_ECG_SAMPLES, samples)
                .putExtra(EXTRA_ECG_SECONDS, seconds)
        )
        ui.post { finish() }
    }

    // ---- outputs ----

    private fun writeEcgFiles(cap: BleKardia.Capture) {
        FileWriter(File(outDir, "${clipId}_ecg_samples.csv")).buffered().use { w ->
            w.write("t_ref_ns,sample_idx,lead1_raw,lead2_raw,lead1_mv,lead2_mv\n")
            for (i in cap.lead1.indices) {
                w.write(
                    "${cap.tRefNs(i)},$i,${cap.lead1[i]},${cap.lead2[i]}," +
                        String.format(
                            Locale.US, "%.5f,%.5f\n",
                            cap.lead1[i] * BleKardia.MV_PER_COUNT,
                            cap.lead2[i] * BleKardia.MV_PER_COUNT
                        )
                )
            }
        }
        val nowRef = SystemClock.elapsedRealtimeNanos()
        val t0WallMs = System.currentTimeMillis() - (nowRef - cap.t0RefNs) / 1_000_000L
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date(t0WallMs))

        AtcWriter.write(
            file = File(outDir, "${clipId}_ecg.atc"),
            samples = cap.lead1,
            fsHz = Math.round(cap.measuredFsHz).toInt(),
            startIso = iso,
            info = mapOf(
                "phone_model" to "${Build.MANUFACTURER} ${Build.MODEL}",
                "recorder_sw" to "SamaHealth onboarding PalmRecorder",
                "recorder_hw" to (ble.deviceName ?: "KardiaMobile BLE"),
            ),
        )
        val meta = JSONObject()
            .put("start_wall_ts", iso)
            .put("duration_s", cap.lead1.size / cap.measuredFsHz)
            .put("fs", cap.measuredFsHz)
            .put("app_rhythm_label", JSONObject.NULL)
            .put("device_id", ble.deviceAddress ?: JSONObject.NULL)
            .put("export_format", "atc")
            .put("source", "live BLE capture by the onboarding app, not an AliveCor app export")
            .put("ble_device_name", ble.deviceName ?: JSONObject.NULL)
            .put("channels", "lead1 = lead I (LA-RA), lead2 = lead II (LL-RA)")
            .put("nv_per_count_exact", AtcWriter.EXACT_NV_PER_COUNT)
            .put("atc_resolution_nv", AtcWriter.RESOLUTION_NV)
            .put(
                "scale_note",
                "counts stored 1:1; the integer ATC resolution rounds " +
                    "${AtcWriter.EXACT_NV_PER_COUNT} nV/count to ${AtcWriter.RESOLUTION_NV}, so mV " +
                    "read back are 0.27 % high. The 10 mV/65536 scale is itself uncalibrated."
            )
            .put("t0_ref_ns", cap.t0RefNs)
            .put("sample_period_ns", cap.samplePeriodNs)
            .put("n_samples", cap.lead1.size)
            .put("gap_count", cap.gapCount)
            .put("missing_samples_zero_filled", cap.missingSamples)
        File(outDir, "${clipId}_ecg_meta.json").writeText(meta.toString(2))
    }

    private fun writeMeta() {
        val mp4 = File(outDir, "$clipId.mp4")
        var width = -1; var height = -1; var bitrate = -1L
        var durationMs = -1L; var frameCount = -1
        if (mp4.exists()) {
            try {
                MediaMetadataRetriever().use { r ->
                    r.setDataSource(mp4.absolutePath)
                    width = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)
                        ?.toIntOrNull() ?: -1
                    height = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)
                        ?.toIntOrNull() ?: -1
                    bitrate = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_BITRATE)
                        ?.toLongOrNull() ?: -1L
                    durationMs = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                        ?.toLongOrNull() ?: -1L
                    frameCount = r.extractMetadata(
                        MediaMetadataRetriever.METADATA_KEY_VIDEO_FRAME_COUNT
                    )?.toIntOrNull() ?: -1
                }
            } catch (e: Exception) {
                Log.w(TAG, "could not read back mp4 metadata", e)
            }
        }
        val meta = JSONObject()
            .put("app", "PalmRecorderActivity (SamaHealth onboarding app, Camera2)")
            .put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("os_build", Build.DISPLAY)
            .put("resolution", JSONArray(listOf(width, height)))
            .put("fps_nominal", FPS)
            .put("bitrate_mbps", if (bitrate > 0) bitrate / 1_000_000.0 else JSONObject.NULL)
            .put("iso", lockedIso)
            .put("exposure_ns", lockedExposureNs)
            .put("wb_locked", true)
            .put("focus_locked", lockedFocusDistance >= 0f)
            .put("stabilisation", false)
            .put("hdr", false)
            .put("torch", if (torchOn) "on" else "off")
            .put("capture_mode", captureMode)
            .put("start_wall_ns", startWallNs)
            .put("led_block", JSONObject.NULL)
            .put("study_id", studyId)
            .put("clip_id", clipId)
            .put("lock_applied", lockApplied)
            .put("hardware_level", hardwareLevel)
            .put("manual_sensor_supported", manualSensor)
            .put("n_frames_logged", frameIdx)
            .put("n_frames_in_container", frameCount)
            .put("container_duration_ms", durationMs)
            .put("requested_duration_s", RECORD_SECONDS)
            .put("roi_fraction", ROI_FRACTION)
            .put("pulse_readout_bound", analysisBound)
            .put(
                "resolution_note",
                "read back from the written file, not the requested size or bitrate"
            )
        File(outDir, "${clipId}_meta.json").writeText(meta.toString(2))
    }

    private fun writeSyncJson(cap: BleKardia.Capture?) {
        val c = clock
        val camera = JSONObject()
            .put("timestamp_source", c?.sourceName ?: "unknown")
            .put("on_reference_clock_natively", c?.sourceIsRealtime ?: false)
            .put("offset_applied_ns", if (c?.sourceIsRealtime == true) 0L else (c?.offsetNs ?: 0L))
            .put("offset_uncertainty_ns", c?.offsetUncertaintyNs ?: JSONObject.NULL)
            .put("n_frame_rows", frameIdx)
            .put("n_frame_write_failures", droppedFrames)
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
                "${clipId}_frames.csv sensor_ts_ns and ${clipId}_ecg_samples.csv t_ref_ns are both " +
                    "on the reference clock. Subtract them directly; no marker fit is needed " +
                    "because one device captured both."
            )
            .put(
                "known_bias",
                "ECG sample times come from the lower envelope of BLE packet arrivals, so they are " +
                    "late by the link's minimum transport delay. That is constant within a session: " +
                    "it biases absolute PAT but not beat-to-beat variation."
            )
            .put(
                "caveat",
                "Clock arithmetic only, not verified against an external reference; the bench " +
                    "acceptance in the protocol still applies."
            )
        File(outDir, "${clipId}_sync.json").writeText(sync.toString(2))
    }

    // ---- status ----

    private fun updateStatus() {
        val sb = StringBuilder()
        if (recording) {
            val left = RECORD_SECONDS - (SystemClock.elapsedRealtime() - recordStartElapsedMs) / 1000
            sb.append("● REC  ${left.coerceAtLeast(0)}s left   frames $frameIdx\n")
        } else if (finishing) {
            sb.append("saving…\n")
        } else {
            sb.append("$studyId · $clipId · $captureMode · torch ${if (torchOn) "on" else "off"}\n")
        }
        sb.append(ble.statusLine)
        if (ble.streaming) sb.append("  pkts ${ble.packetCount}  samples ${ble.loggedSamples}")
        sb.append('\n')
        val hr = ble.heartRateBpm
        sb.append(if (hr > 0) "ECG HR ~%.0f bpm   ".format(hr) else "ECG HR --   ")
        sb.append(
            if (!analysisBound) "palm readout unavailable"
            else if (pulse.bpm > 0) "palm ~%.0f bpm  perfusion %.2f%%".format(pulse.bpm, pulse.perfusionPct)
            else "palm -- no pulse  perfusion %.2f%%".format(pulse.perfusionPct)
        )
        sb.append("\ncam $hardwareLevel  lock $lockApplied  clock ${clock?.sourceName ?: "?"}")
        statusView.text = sb.toString()
    }
}

private const val MATCH = FrameLayout.LayoutParams.MATCH_PARENT
private const val WRAP = FrameLayout.LayoutParams.WRAP_CONTENT

/** Holds its children at a fixed aspect ratio so the preview is never anamorphically stretched. */
private class AspectFrame(context: android.content.Context, private val aspect: Float) :
    FrameLayout(context) {
    override fun onMeasure(widthSpec: Int, heightSpec: Int) {
        var w = MeasureSpec.getSize(widthSpec)
        var h = MeasureSpec.getSize(heightSpec)
        if (w > 0 && h > 0) {
            if (w.toFloat() / h > aspect) w = (h * aspect).toInt() else h = (w / aspect).toInt()
        }
        super.onMeasure(
            MeasureSpec.makeMeasureSpec(w, MeasureSpec.EXACTLY),
            MeasureSpec.makeMeasureSpec(h, MeasureSpec.EXACTLY)
        )
    }
}
