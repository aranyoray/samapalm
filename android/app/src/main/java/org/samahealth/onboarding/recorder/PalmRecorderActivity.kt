/*
 * PalmRecorderActivity: Camera2 recorder for the OnePlus 12 (protocol sections 4.6 and 5), launched from a clip
 * screen of the onboarding survey.
 *
 * Records a 60 s 1920x1080 / 30 fps / H.264 clip with AAC audio (the rig buzzer is the sync marker) and, at the same
 * time, the KardiaMobile 6L/Card ECG over BLE. It must pass the bench acceptance (protocol 4.5) before it is used
 * for study clips.
 *
 * The ECG is deliberately longer than the clip: it opens [ECG_LEAD_IN_MS] before the encoder and closes
 * [ECG_LEAD_OUT_MS] after it, so the clip is a window inside a continuous ECG record and the beats straddling
 * either boundary are whole rather than truncated. Where the clip sits inside that record is written out as
 * sample indices in `<clip>_sync.json`, so nothing downstream has to re-derive it.
 *
 * Two short tones mark the clip for an operator who is holding the rig rather than watching the screen: one
 * before the encoder opens, one after it closes. Both fall outside the recorded audio on purpose, so neither
 * can be mistaken for the rig buzzer when the track is read for the sync marker.
 *
 * Camera controls (D-033): the main sensor is opened by id so the logical camera cannot hand off to the ultrawide at
 * palm distance; focus is a fixed plane at the rig distance from the first frame (no autofocus to catch mid-hunt);
 * zoom pinned at 1.0; an explicit sRGB tone curve with lens shading and aberration correction off; AE metered on the
 * palm ROI during the settle, then manual exposure capped at 12 ms (light moved into ISO) after one proportional
 * ROI-luma correction, and the settled colour gains re-sent as manual white balance. Every control is read back per
 * frame into <clip>_controls.csv and the pre-encoder ROI colour into <clip>_roi.csv. The arithmetic is in
 * [PalmControls]; this class only sends it and reports what the camera did. Both streams are timestamped on CLOCK_BOOTTIME by the same device, so
 * aligning them is subtraction rather than a marker fit — the clip screen's "Kardia recording" question stops being a
 * self-report and becomes a measured sample count.
 *
 * Outputs under Android/data/org.samahealth.onboarding/files/<PID>/:
 *   <clip>.mp4, <clip>_frames.csv (frame_idx, sensor_ts_ns on the reference clock, wall_ns, iso, exposure_ns),
 *   <clip>_controls.csv, <clip>_roi.csv, <clip>_meta.json, and when a Kardia was streaming: <clip>_ecg.atc (CONTRACTS 3.6), <clip>_ecg_samples.csv,
 *   <clip>_ecg_packets.csv, <clip>_ecg_meta.json, <clip>_sync.json.
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
import android.hardware.camera2.params.ColorSpaceTransform
import android.hardware.camera2.params.MeteringRectangle
import android.hardware.camera2.params.RggbChannelVector
import android.hardware.camera2.params.TonemapCurve
import android.media.AudioManager
import android.media.ImageReader
import android.media.MediaMetadataRetriever
import android.media.MediaRecorder
import android.media.ToneGenerator
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
import android.widget.LinearLayout
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

        /** Lens-to-palm distance in cm; sets the fixed focus plane. Defaults to [PalmControls.DEFAULT_DISTANCE_CM]. */
        const val EXTRA_DISTANCE_CM = "distance_cm"
        /** Clip length in seconds (60 for the 1x60 plan, 30 for 2x30); the clip stops itself at this length. */
        const val EXTRA_SECONDS = "seconds"
        /** Roll as soon as the camera has settled, instead of waiting for the button. */
        const val EXTRA_AUTO_START = "auto_start"
        /** Result: ISO 8601 times the clip started rolling and stopped, its length, and whether it stopped early. */
        const val EXTRA_STARTED_AT = "started_at"
        const val EXTRA_ENDED_AT = "ended_at"
        const val EXTRA_DURATION_S = "duration_s"
        const val EXTRA_INTERRUPTED = "interrupted"
        /** OnePlus 12 main sensor (6.06 mm f/1.6, closest focus 13 cm). Logical camera 0 fuses it with the ultrawide. */
        const val PREFERRED_PHYSICAL_ID = "2"

        const val ROI_FRACTION = 0.40f
        private const val TAG = "PalmRecorder"
        private const val DEFAULT_RECORD_SECONDS = 60
        private const val SETTLE_MS = 2_000L
        /** After the lock request is sent, before the clip rolls: lets the HAL report what it did. */
        private const val LOCK_SETTLE_MS = 400L
        /** ECG runs this long before the encoder opens. Served inside the AE settle, which only helps it. */
        private const val ECG_LEAD_IN_MS = 10_000L
        /** ECG keeps running this long after the encoder closes. Skipped when the clip was interrupted. */
        private const val ECG_LEAD_OUT_MS = 10_000L
        private const val START_TONE_MS = 150
        private const val DONE_TONE_MS = 400
        private const val VIDEO_W = 1920
        private const val VIDEO_H = 1080
        private const val FPS = 30
        /** 16:9 like the clip, so the centred ROI is the same patch of palm in both streams. */
        private const val ANALYSIS_W = 640
        private const val ANALYSIS_H = 360
    }

    private val studyId: String get() = intent.getStringExtra(EXTRA_STUDY_ID) ?: "SWHT-PP-003-0000"
    private val clipId: String get() = intent.getStringExtra(EXTRA_CLIP_ID) ?: "clip1"
    private val captureMode: String get() = intent.getStringExtra(EXTRA_CAPTURE_MODE) ?: "simultaneous"
    private val torchOn: Boolean get() = captureMode == "sequential"
    private val distanceCm: Float get() = intent.getFloatExtra(EXTRA_DISTANCE_CM, PalmControls.DEFAULT_DISTANCE_CM)
    // An hour at 1080p30 is about 4 GB, which the phone can hold; the limit exists so a bad extra cannot
    // ask for something the encoder or the card will not survive.
    private val RECORD_SECONDS: Int get() = intent.getIntExtra(EXTRA_SECONDS, DEFAULT_RECORD_SECONDS).coerceIn(5, 3600)
    private val autoStart: Boolean get() = intent.getBooleanExtra(EXTRA_AUTO_START, false)
    private var autoStarted = false

    private lateinit var preview: SurfaceView
    private lateinit var overlay: RecorderOverlay
    private lateinit var statusView: TextView
    private lateinit var recordButton: Button
    private lateinit var nudgeButton: Button
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
    private var awbApplied = "none"
    private var manualSensor = false
    private var manualPost = false
    private var hardwareLevel = "unknown"
    private var cameraIdUsed = "?"
    private var minimumFocusDistance: Float? = null
    private var focusCalibration = "unknown"
    private var isoRange: IntRange = 100..6400
    private var exposureRange: LongRange = 100_000L..100_000_000L
    private var activeArray: android.graphics.Rect? = null
    private var focus = PalmControls.focusFor(PalmControls.DEFAULT_DISTANCE_CM, null)
    private var forceAeLock = false

    // latest capture result, so the lock and the metadata report what the camera did, not what was asked
    @Volatile private var lastLensState = -1
    @Volatile private var lastFlashState = -1
    @Volatile private var lastAeMode = -1
    @Volatile private var lastAfMode = -1
    @Volatile private var lastAwbMode = -1
    @Volatile private var lastTonemapMode = -1
    @Volatile private var lastShadingMode = -1
    @Volatile private var lastAberrationMode = -1
    @Volatile private var lastZoom = -1f
    @Volatile private var lastGains: RggbChannelVector? = null
    @Volatile private var lastTransform: ColorSpaceTransform? = null
    @Volatile private var resultFps = 0f
    private var lastResultTs = -1L

    private var settledExposure: PalmControls.Exposure? = null
    private var requestedExposure: PalmControls.Exposure? = null
    private var lockedGains: RggbChannelVector? = null
    private var lockedTransform: ColorSpaceTransform? = null
    private var preflight: PalmControls.Verdict? = null

    private var controlsCsv: FileWriter? = null
    private var roiCsv: FileWriter? = null
    @Volatile private var roiRows = 0L
    @Volatile private var roiLuma = Float.NaN
    @Volatile private var roiClipFraction = Float.NaN
    @Volatile private var analysisCount = 0L
    private var lockedSurfaces: List<Surface> = emptyList()
    private var surfaceReady = false
    private var startWallNs = 0L
    private var recordStartElapsedMs = 0L
    /** Reference-clock bounds of the clip itself, to locate it inside the longer ECG record. */
    private var recordStartRefNs = 0L
    private var recordStopRefNs = 0L
    /** Reference-clock time ECG buffering opened, i.e. the start of the lead-in. */
    private var ecgStartRefNs = 0L
    @Volatile private var ecgCapturing = false
    @Volatile private var leadOutPending = false
    private var leadOutEndsAtMs = 0L
    private var stopWasCancelled = false
    private var stopCompleted = false
    private var clipEndWallMs = 0L
    private var clipElapsedS = 0.0
    private var tones: ToneGenerator? = null

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
        // The lock screen backgrounds the activity and closes the camera, which cut clips short at the screen
        // timeout (a 15 s timeout minus the 2.4 s settle is the ~13 s cut-off seen in the field).
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

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
        // The Card is the part most likely to misbehave in the field, and the watchdog only acts after
        // three seconds of silence. This fires the same recovery ladder immediately.
        nudgeButton = Button(this).apply {
            text = "Nudge Kardia"
            setOnClickListener {
                Log.i(TAG, "operator nudge -> " + ble.nudge())
                updateStatus()
            }
        }
        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(recordButton)
            addView(nudgeButton)
        }

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
            buttons,
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
                else abortPendingStart("preview surface went away")
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
        if (recording) {
            stopRecording(cancelled = true)
        } else if (leadOutPending) {
            // the camera thread is about to be quit, so the deferred close has to happen here or the
            // whole ECG record is lost along with the clip that was already on disk
            Log.w(TAG, "destroyed during the ECG lead-out; closing it now")
            completeStop()
        } else {
            abortPendingStart("activity destroyed")
        }
        ble.stop()
        // let a tone that is still sounding finish; the generator outlives the activity by a moment
        val t = tones
        tones = null
        if (t != null) {
            Handler(Looper.getMainLooper()).postDelayed({
                try { t.release() } catch (_: RuntimeException) {}
            }, DONE_TONE_MS + 200L)
        }
        thread.quitSafely()
        super.onDestroy()
    }

    /**
     * Drops a start that was still in its lead-in. The clip has not rolled, so there is nothing to save,
     * but the ECG buffer and its packet log are open and would otherwise be left dangling: [BleKardia.finalise]
     * closes the writer, and its return value is discarded on purpose.
     */
    private fun abortPendingStart(reason: String) {
        if (!ecgCapturing || recording || finishing) return
        Log.w(TAG, "lead-in abandoned: $reason")
        ecgCapturing = false
        handler.removeCallbacksAndMessages(null)
        ble.finalise()
        ui.post {
            recordButton.isEnabled = true
            recordButton.text = "● REC ${RECORD_SECONDS}s"
        }
    }

    // ---- operator tones ----

    /**
     * STREAM_MUSIC rather than the notification stream: ringer-silent mutes notifications, and the whole
     * point is that an operator holding the rig hears the clip finish without looking at the phone. A
     * device that will not give us a tone generator is logged and ignored; it must not fail a clip.
     */
    private fun beep(tone: Int, ms: Int) {
        try {
            if (tones == null) tones = ToneGenerator(AudioManager.STREAM_MUSIC, 90)
            tones?.startTone(tone, ms)
        } catch (e: RuntimeException) {
            Log.w(TAG, "tone unavailable", e)
        }
    }

    // ---- camera ----

    /**
     * The main sensor by id when the HAL lists it. `cameraIdList.first { BACK }` is logical camera 0,
     * which fuses the main (closest focus 13 cm) with the ultrawide (4 cm); at palm distance the HAL
     * may hand off between them, and no result key says when it does.
     */
    private fun backCameraId(): String {
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        val ids = cm.cameraIdList
        if (PREFERRED_PHYSICAL_ID in ids) return PREFERRED_PHYSICAL_ID
        return ids.first { id ->
            cm.getCameraCharacteristics(id)
                .get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        }
    }

    /** Centre-ROI metering rectangle on the active array, for the 16:9 field the clip records. */
    private fun roiMeteringRegion(): MeteringRectangle? {
        val a = activeArray ?: return null
        val w = a.width().toFloat()
        val cropH = minOf(a.height().toFloat(), w * 9f / 16f)
        val cx = a.left + w / 2f
        val cy = a.top + a.height() / 2f
        val half = ROI_FRACTION / 2f
        val l = (cx - half * w).toInt()
        val t = (cy - half * cropH).toInt()
        return MeteringRectangle(
            l, t, (cx + half * w).toInt() - l, (cy + half * cropH).toInt() - t,
            MeteringRectangle.METERING_WEIGHT_MAX
        )
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
        val caps = ch.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES) ?: intArrayOf()
        manualSensor = caps.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR)
        manualPost = caps.contains(CameraMetadata.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_POST_PROCESSING)
        cameraIdUsed = id
        minimumFocusDistance = ch.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE)
        focusCalibration = when (ch.get(CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION)) {
            CameraMetadata.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_CALIBRATED -> "CALIBRATED"
            CameraMetadata.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_APPROXIMATE -> "APPROXIMATE"
            CameraMetadata.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_UNCALIBRATED -> "UNCALIBRATED"
            else -> "unknown"
        }
        ch.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)?.let { isoRange = it.lower..it.upper }
        ch.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)?.let { exposureRange = it.lower..it.upper }
        activeArray = ch.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)
        focus = PalmControls.focusFor(distanceCm, minimumFocusDistance)
        Log.i(TAG, "camera $id ($hardwareLevel): focus ${focus.appliedDiopters} D for $distanceCm cm" +
            (if (focus.clampedToLens) " (clamped to the lens's ${minimumFocusDistance} D)" else "") +
            ", manualSensor=$manualSensor manualPost=$manualPost")

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
                    val sensorTs = image.timestamp
                    val refNs = clock?.toReferenceNs(sensorTs) ?: sensorTs
                    val st = roiStats(image)
                    if (st != null) {
                        roiLuma = st.y
                        roiClipFraction = st.clipFraction
                        analysisCount++
                        val ac = pulse.push(refNs, st.y.toDouble())
                        ppgRing[ppgWriteIdx] = ac
                        peakRing[ppgWriteIdx] = pulse.lastSampleWasPeak
                        ppgWriteIdx = (ppgWriteIdx + 1) % ppgRing.size
                        if (recording) {
                            val rgb = PalmControls.yuvMeanToRgb(st.y, st.u, st.v)
                            roiCsv?.let { w ->
                                w.write(
                                    "$roiRows,$sensorTs,$refNs,${st.n}," +
                                        String.format(Locale.US, "%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.5f,",
                                            st.y, st.u, st.v, rgb[0], rgb[1], rgb[2], st.clipFraction) +
                                        st.grid.joinToString(",") { String.format(Locale.US, "%.2f", it) } + "\n"
                                )
                                roiRows++
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "analysis frame failed", e)
                } finally {
                    image.close()
                }
            }, handler)
        }

    private class RoiStats(val y: Float, val u: Float, val v: Float, val n: Int, val clipFraction: Float, val grid: FloatArray)

    /**
     * Mean Y, U, V over the centred ROI — the same fraction [RecorderOverlay] draws — at full analysis
     * resolution, with the fraction of clipped pixels and a 3x3 grid of Y means so motion and uneven
     * light are visible after the fact.
     */
    private fun roiStats(image: android.media.Image): RoiStats? {
        if (image.planes.size < 3) return null
        val w = image.width
        val h = image.height
        val half = ROI_FRACTION / 2f
        val x0 = ((0.5f - half) * w).toInt().coerceIn(0, w - 2)
        val x1 = ((0.5f + half) * w).toInt().coerceIn(x0 + 1, w)
        val y0 = ((0.5f - half) * h).toInt().coerceIn(0, h - 2)
        val y1 = ((0.5f + half) * h).toInt().coerceIn(y0 + 1, h)

        val yPlane = image.planes[0]
        val yBuf = yPlane.buffer
        val yStride = yPlane.rowStride
        val yPix = yPlane.pixelStride
        val gridSum = LongArray(9)
        val gridN = IntArray(9)
        val cellW = (x1 - x0) / 3f
        val cellH = (y1 - y0) / 3f
        var sum = 0L
        var n = 0
        var clipped = 0
        var y = y0
        while (y < y1) {
            val base = y * yStride
            val gy = ((y - y0) / cellH).toInt().coerceIn(0, 2)
            var x = x0
            while (x < x1) {
                val off = base + x * yPix
                if (off < yBuf.limit()) {
                    val v = yBuf.get(off).toInt() and 0xFF
                    sum += v; n++
                    if (v >= PalmControls.CLIP_LEVEL) clipped++
                    val gi = gy * 3 + ((x - x0) / cellW).toInt().coerceIn(0, 2)
                    gridSum[gi] += v; gridN[gi]++
                }
                x++
            }
            y++
        }
        if (n == 0) return null

        fun chromaMean(idx: Int): Float {
            val p = image.planes[idx]
            val buf = p.buffer
            val stride = p.rowStride
            val pix = p.pixelStride
            var s = 0L
            var c = 0
            var cy = y0 / 2
            while (cy < y1 / 2) {
                val base = cy * stride
                var cx = x0 / 2
                while (cx < x1 / 2) {
                    val off = base + cx * pix
                    if (off < buf.limit()) { s += (buf.get(off).toInt() and 0xFF); c++ }
                    cx++
                }
                cy++
            }
            return if (c == 0) 128f else s.toFloat() / c
        }
        val grid = FloatArray(9) { if (gridN[it] == 0) 0f else gridSum[it].toFloat() / gridN[it] }
        return RoiStats(sum.toFloat() / n, chromaMean(1), chromaMean(2), n, clipped.toFloat() / n, grid)
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
                // Hands-free: the operator is holding the rig and the palm, not the phone. Once only, so a
                // session rebuild part way through a visit does not start a second clip behind their back.
                if (autoStart && !autoStarted && !recording && !finishing) {
                    autoStarted = true
                    ui.post { startRecording() }
                }
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
        // The ingest inverts sRGB; the vendor FAST curve is not sRGB and cannot be recovered.
        if (manualPost) {
            val curve = PalmControls.srgbCurve()
            b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_CONTRAST_CURVE)
            b.set(CaptureRequest.TONEMAP_CURVE, TonemapCurve(curve, curve, curve))
            b.set(CaptureRequest.SHADING_MODE, CameraMetadata.SHADING_MODE_OFF)
            b.set(CaptureRequest.COLOR_CORRECTION_ABERRATION_MODE, CameraMetadata.COLOR_CORRECTION_ABERRATION_MODE_OFF)
        } else {
            b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_FAST)
        }
        if (Build.VERSION.SDK_INT >= 30) b.set(CaptureRequest.CONTROL_ZOOM_RATIO, 1.0f)
        roiMeteringRegion()?.let { b.set(CaptureRequest.CONTROL_AE_REGIONS, arrayOf(it)) }
        b.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(FPS, FPS))
        b.set(
            CaptureRequest.FLASH_MODE,
            if (torchOn) CameraMetadata.FLASH_MODE_TORCH else CameraMetadata.FLASH_MODE_OFF
        )
        // Fixed focus from the first frame: no hunt, nothing to catch mid-sweep. A soft palm that never
        // refocuses is a usable clip; a sharp one that refocuses halfway is not.
        b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_OFF)
        b.set(CaptureRequest.LENS_FOCUS_DISTANCE, focus.appliedDiopters)
        if (!lock) {
            b.set(CaptureRequest.CONTROL_AE_LOCK, false)
            b.set(CaptureRequest.CONTROL_AWB_LOCK, false)
            return
        }
        // Exposure: manual at the settled value, shutter capped at 12 ms with the light moved into ISO,
        // after one proportional correction if the pre-flight found the ROI dark or hot. Measured on a
        // OnePlus 12 (LEVEL_3): manual sensor control holds the exposure far better than CONTROL_AE_LOCK.
        val settled = PalmControls.Exposure(lockedExposureNs, lockedIso, capped = false, isoSaturated = false)
        settledExposure = settled
        var exp = PalmControls.capExposure(lockedExposureNs, lockedIso, isoRange, exposureRange)
        val luma = roiLuma
        val verdict = preflight
        if (verdict?.exposureCorrection != null && !luma.isNaN()) {
            exp = PalmControls.correctExposure(exp, luma, isoRange, exposureRange)
        }
        requestedExposure = exp
        lockApplied = if (manualSensor && !forceAeLock && exp.iso > 0 && exp.exposureNs > 0) {
            b.set(CaptureRequest.CONTROL_AE_MODE, CameraMetadata.CONTROL_AE_MODE_OFF)
            b.set(CaptureRequest.SENSOR_SENSITIVITY, exp.iso)
            b.set(CaptureRequest.SENSOR_EXPOSURE_TIME, exp.exposureNs)
            b.set(CaptureRequest.SENSOR_FRAME_DURATION, 1_000_000_000L / FPS)
            "manual_sensor" + (if (exp.capped) "+exposure_capped" else "") +
                (if (verdict?.exposureCorrection != null) "+roi_corrected" else "")
        } else {
            b.set(CaptureRequest.CONTROL_AE_LOCK, true)
            if (forceAeLock) "ae_lock(torch_fallback)" else "ae_lock"
        }
        // White balance: the settled gains and transform re-sent as numbers, so what the clip was
        // balanced to is known afterwards and comparable across sessions.
        val g = lastGains
        val t = lastTransform
        awbApplied = if (manualPost && g != null && t != null) {
            b.set(CaptureRequest.CONTROL_AWB_MODE, CameraMetadata.CONTROL_AWB_MODE_OFF)
            b.set(CaptureRequest.COLOR_CORRECTION_MODE, CameraMetadata.COLOR_CORRECTION_MODE_TRANSFORM_MATRIX)
            b.set(CaptureRequest.COLOR_CORRECTION_GAINS, g)
            b.set(CaptureRequest.COLOR_CORRECTION_TRANSFORM, t)
            lockedGains = g; lockedTransform = t
            "manual_gains_from_settle"
        } else {
            b.set(CaptureRequest.CONTROL_AWB_LOCK, true)
            "awb_lock"
        }
        lockApplied += "+af_off_fixed"
    }

    /** Snapshot of the settled state for [PalmControls.preflight]. */
    private fun reading(): PalmControls.Reading = PalmControls.Reading(
        roiLuma = roiLuma.takeIf { !it.isNaN() && analysisBound },
        clipFraction = roiClipFraction.takeIf { !it.isNaN() && analysisBound },
        fps = resultFps.takeIf { it > 0f },
        exposureNs = lockedExposureNs,
        iso = lockedIso,
        focusRequestedDiopters = focus.appliedDiopters,
        focusReportedDiopters = lockedFocusDistance.takeIf { it >= 0f },
        torchRequested = torchOn,
        torchLit = when (lastFlashState) {
            CameraMetadata.FLASH_STATE_FIRED -> true
            CameraMetadata.FLASH_STATE_READY, CameraMetadata.FLASH_STATE_UNAVAILABLE -> false
            else -> null
        },
        perfusionPct = pulse.perfusionPct.takeIf { analysisBound && analysisCount > FPS },
    )

    private val frameLogger = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(
            s: CameraCaptureSession, req: CaptureRequest, result: TotalCaptureResult
        ) {
            val iso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            val exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            val focusD = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            lastLensState = result.get(CaptureResult.LENS_STATE) ?: -1
            lastFlashState = result.get(CaptureResult.FLASH_STATE) ?: -1
            lastAeMode = result.get(CaptureResult.CONTROL_AE_MODE) ?: -1
            lastAfMode = result.get(CaptureResult.CONTROL_AF_MODE) ?: -1
            lastAwbMode = result.get(CaptureResult.CONTROL_AWB_MODE) ?: -1
            lastTonemapMode = result.get(CaptureResult.TONEMAP_MODE) ?: -1
            lastShadingMode = result.get(CaptureResult.SHADING_MODE) ?: -1
            lastAberrationMode = result.get(CaptureResult.COLOR_CORRECTION_ABERRATION_MODE) ?: -1
            if (Build.VERSION.SDK_INT >= 30) lastZoom = result.get(CaptureResult.CONTROL_ZOOM_RATIO) ?: -1f
            // Only the settle's own AWB output is worth remembering; under manual mode these echo our request.
            if (lastAwbMode != CameraMetadata.CONTROL_AWB_MODE_OFF) {
                result.get(CaptureResult.COLOR_CORRECTION_GAINS)?.let { lastGains = it }
                result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)?.let { lastTransform = it }
            }
            val ts = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            if (lastResultTs > 0L) {
                val dt = (ts - lastResultTs) / 1e9f
                if (dt > 0f) resultFps = if (resultFps == 0f) 1f / dt else 0.9f * resultFps + 0.1f / dt
            }
            lastResultTs = ts
            if (!recording) {
                lockedIso = iso; lockedExposureNs = exp; lockedFocusDistance = focusD
                return
            }
            lockedFocusDistance = focusD
            val refNs = clock?.toReferenceNs(ts) ?: ts
            val wallNs = System.currentTimeMillis() * 1_000_000L
            try {
                framesCsv?.write("$frameIdx,$refNs,$wallNs,$iso,$exp\n")
                val g = result.get(CaptureResult.COLOR_CORRECTION_GAINS)
                controlsCsv?.write(
                    "$frameIdx,$refNs,$iso,$exp,$focusD,$lastLensState,$lastZoom," +
                        (if (g == null) ",,," else String.format(Locale.US, "%.4f,%.4f,%.4f,%.4f", g.red, g.greenEven, g.greenOdd, g.blue)) +
                        ",$lastAwbMode,$lastAeMode,$lastAfMode,$lastTonemapMode,$lastShadingMode,$lastFlashState\n"
                )
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
        s.setRepeatingRequest(settle.build(), frameLogger, handler)
    }

    // ---- recording ----

    /**
     * Phase 1: open the ECG, then let AE meter the palm while the lead-in is served.
     *
     * The lead-in is spent in the settle rather than after the lock, because during the settle AE is still
     * metering the ROI: the extra seconds make the exposure decision better instead of leaving a locked
     * camera staring at the palm with the torch on.
     */
    private fun startRecording() {
        val dev = camera ?: return
        val s = session ?: return
        if (recording || finishing) return
        recordButton.isEnabled = false
        recordButton.text = "settling…"
        ble.startCapture(File(outDir, "${clipId}_ecg_packets.csv"))
        ecgStartRefNs = SystemClock.elapsedRealtimeNanos()
        ecgCapturing = true
        val settleMs = maxOf(SETTLE_MS, ECG_LEAD_IN_MS - LOCK_SETTLE_MS - START_TONE_MS - 100L)
        // Phase 2: pin everything at the settled values, then roll.
        handler.postDelayed({ lockAndRecord(dev, s) }, settleMs)
    }

    /**
     * Phase 2a: judge the settled state, send the locked request, then give the HAL [LOCK_SETTLE_MS] to
     * report what it did before the clip rolls. Nothing in the pre-flight refuses the operator; it is
     * shown, logged, and where a correction is arithmetic it is applied once.
     */
    private fun lockAndRecord(dev: CameraDevice, s: CameraCaptureSession) {
        val surfaces = mutableListOf(preview.holder.surface, recorder!!.surface)
        if (analysisBound) analysisReader?.surface?.let { surfaces += it }
        lockedSurfaces = surfaces
        preflight = PalmControls.preflight(reading())
        Log.i(TAG, preflight?.line ?: "no pre-flight")
        forceAeLock = false
        val locked = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
        surfaces.forEach { locked.addTarget(it) }
        applyFixedControls(locked, lock = true)
        s.setRepeatingRequest(locked.build(), frameLogger, handler)
        Log.i(TAG, "lock: $lockApplied / $awbApplied; exposure ${settledExposure?.exposureNs}ns@${settledExposure?.iso}" +
            " -> ${requestedExposure?.exposureNs}ns@${requestedExposure?.iso}")
        handler.postDelayed({ checkTorchThenRoll(dev, s) }, LOCK_SETTLE_MS)
    }

    /**
     * Camera2 lets FLASH_MODE_TORCH drive the LED with AE off, but a vendor HAL may not. If the flash
     * state says the torch went out when exposure went manual, fall back to AE lock (AE stays on, so the
     * torch does) and say so in `lock_applied`.
     */
    private fun checkTorchThenRoll(dev: CameraDevice, s: CameraCaptureSession) {
        if (finishing) return
        val torchOut = torchOn && lockApplied.startsWith("manual_sensor") &&
            lastFlashState >= 0 && lastFlashState != CameraMetadata.FLASH_STATE_FIRED
        if (torchOut) {
            Log.w(TAG, "torch not lit under manual exposure (flash_state=$lastFlashState); reverting to AE lock")
            forceAeLock = true
            val locked = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
            lockedSurfaces.forEach { locked.addTarget(it) }
            applyFixedControls(locked, lock = true)
            s.setRepeatingRequest(locked.build(), frameLogger, handler)
            handler.postDelayed({ roll() }, LOCK_SETTLE_MS)
        } else {
            roll()
        }
    }

    /**
     * Phase 2b: hold until the ECG lead-in has actually been served (the torch fallback can add a second
     * lock settle, so the wait is measured, not assumed), sound the start tone, and let the tone finish
     * before the encoder opens so it stays off the recorded audio track.
     */
    private fun roll() {
        if (finishing) return
        val remainingMs = ECG_LEAD_IN_MS - (SystemClock.elapsedRealtimeNanos() - ecgStartRefNs) / 1_000_000L
        if (remainingMs > 0) {
            handler.postDelayed({ roll() }, remainingMs)
            return
        }
        beep(ToneGenerator.TONE_PROP_BEEP, START_TONE_MS)
        handler.postDelayed({ if (!finishing) rollNow() }, START_TONE_MS + 100L)
    }

    /** Phase 2c: open the logs and start the clip under the locked request already running. */
    private fun rollNow() {
        if (finishing) return
        framesCsv = FileWriter(File(outDir, "${clipId}_frames.csv")).apply {
            write("frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns\n")
        }
        controlsCsv = FileWriter(File(outDir, "${clipId}_controls.csv")).apply {
            write("frame_idx,sensor_ts_ns,iso,exposure_ns,focus_diopters,lens_state,zoom_ratio," +
                "gain_r,gain_g_even,gain_g_odd,gain_b,awb_mode,ae_mode,af_mode,tonemap_mode,shading_mode,flash_state\n")
        }
        roiRows = 0
        roiCsv = if (analysisBound) FileWriter(File(outDir, "${clipId}_roi.csv")).apply {
            write("roi_idx,sensor_ts_ns_raw,t_ref_ns,n_px,y_mean,u_mean,v_mean,r_mean,g_mean,b_mean,clip_frac," +
                "g00,g01,g02,g10,g11,g12,g20,g21,g22\n")
        } else null
        frameIdx = 0
        droppedFrames = 0
        clock?.measure()
        startWallNs = System.currentTimeMillis() * 1_000_000L
        recordStartElapsedMs = SystemClock.elapsedRealtime()
        recordStartRefNs = SystemClock.elapsedRealtimeNanos()
        recorder?.start()
        recording = true

        ui.post {
            recordButton.isEnabled = true
            recordButton.text = "■ STOP"
        }
        handler.postDelayed({ if (recording) stopRecording(cancelled = false) },
            RECORD_SECONDS * 1000L)
    }

    /**
     * Closes the clip, then keeps the ECG running for the lead-out before anything is written.
     *
     * The tone is sounded after [MediaRecorder.stop], so it is not in the encoded audio and cannot be read
     * later as the rig buzzer. A cancelled clip (lock screen, surface gone, back, error) gets no lead-out:
     * the activity is on its way out and an ECG tail nobody will wait for is worth less than finishing
     * cleanly with what was captured.
     */
    private fun stopRecording(cancelled: Boolean) {
        if (!recording || finishing) return
        finishing = true
        recording = false
        stopWasCancelled = cancelled
        handler.removeCallbacksAndMessages(null)
        try { session?.stopRepeating() } catch (_: Exception) {}
        try { recorder?.stop() } catch (e: Exception) { Log.e(TAG, "recorder stop", e) }
        recorder?.release(); recorder = null
        recordStopRefNs = SystemClock.elapsedRealtimeNanos()
        clipEndWallMs = System.currentTimeMillis()
        clipElapsedS = (SystemClock.elapsedRealtime() - recordStartElapsedMs) / 1000.0
        try { framesCsv?.flush(); framesCsv?.close() } catch (_: Exception) {}
        framesCsv = null
        try { controlsCsv?.flush(); controlsCsv?.close() } catch (_: Exception) {}
        controlsCsv = null
        try { roiCsv?.flush(); roiCsv?.close() } catch (_: Exception) {}
        roiCsv = null

        // double beep for a clip that ran its length, the three-tone nack for one that did not
        beep(
            if (cancelled) ToneGenerator.TONE_PROP_NACK else ToneGenerator.TONE_PROP_BEEP2,
            DONE_TONE_MS
        )

        ui.post {
            recordButton.isEnabled = false
            recordButton.text = if (cancelled) "saving…" else "ECG lead-out…"
        }

        if (cancelled) {
            completeStop()
        } else {
            leadOutPending = true
            leadOutEndsAtMs = SystemClock.elapsedRealtime() + ECG_LEAD_OUT_MS
            handler.postDelayed({ completeStop() }, ECG_LEAD_OUT_MS)
        }
    }

    /** Closes the ECG record at the end of the lead-out, writes everything, and hands the result back. */
    private fun completeStop() {
        if (stopCompleted) return
        stopCompleted = true
        leadOutPending = false
        ecgCapturing = false

        val capture = ble.finalise()
        if (capture != null && capture.lead1.isNotEmpty()) writeEcgFiles(capture)
        writeMeta()
        writeSyncJson(capture)

        analysisReader?.close(); analysisReader = null
        session?.close(); session = null
        camera?.close(); camera = null

        val durationS = fileDurationS() ?: clipElapsedS
        val samples = capture?.lead1?.size ?: 0
        val seconds = if (capture != null && capture.measuredFsHz > 0)
            capture.lead1.size / capture.measuredFsHz else 0.0
        // An interrupted clip (lock screen, back, user stop, error) is still reported, with its real length, so
        // the survey and the quality check can flag it instead of the file sitting there unexplained.
        // The times reported are the clip's, not the ECG record's, which is longer at both ends by design.
        setResult(
            RESULT_OK,
            Intent()
                .putExtra(EXTRA_MP4, File(outDir, "$clipId.mp4").absolutePath)
                .putExtra(EXTRA_ECG_SAMPLES, samples)
                .putExtra(EXTRA_ECG_SECONDS, seconds)
                .putExtra(EXTRA_STARTED_AT, isoTime(startWallNs / 1_000_000L))
                .putExtra(EXTRA_ENDED_AT, isoTime(clipEndWallMs))
                .putExtra(EXTRA_DURATION_S, durationS)
                .putExtra(EXTRA_INTERRUPTED, stopWasCancelled || durationS < RECORD_SECONDS - 1.0)
        )
        ui.post { finish() }
    }

    // ---- outputs ----

    private fun isoTime(ms: Long): String = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSXXX", Locale.US).format(Date(ms))

    /** Length of the written clip from its container, or null when it cannot be read (e.g. not finalised). */
    private fun fileDurationS(): Double? {
        val f = File(outDir, "$clipId.mp4")
        if (!f.exists() || f.length() == 0L) return null
        val r = MediaMetadataRetriever()
        return try {
            r.setDataSource(f.absolutePath)
            r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()?.let { it / 1000.0 }
        } catch (e: Exception) { null } finally { try { r.release() } catch (_: Exception) {} }
    }

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
            .put(
                "channels",
                if (cap.channels == 1) "lead1 = the device's single lead; lead2 is unused and zero"
                else "lead1 = lead I (LA-RA), lead2 = lead II (LL-RA)"
            )
            .put("n_channels", cap.channels)
            .put("channel_layout_decision", cap.layoutDecision)
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
            .put("lead_in_s", leadInS(cap))
            .put("lead_out_s", leadOutS(cap))
            .put(
                "window_note",
                "this record is longer than the clip at both ends on purpose; " +
                    "${clipId}_sync.json gives the sample indices the clip spans"
            )
        File(outDir, "${clipId}_ecg_meta.json").writeText(meta.toString(2))
    }

    /** Sample index of a reference-clock instant in the ECG record; may fall outside it if the stream dropped. */
    private fun sampleIndexAt(cap: BleKardia.Capture, refNs: Long): Long =
        Math.round((refNs - cap.t0RefNs) / cap.samplePeriodNs)

    /** ECG actually captured before the encoder opened, in seconds. */
    private fun leadInS(cap: BleKardia.Capture): Double =
        if (recordStartRefNs == 0L) 0.0 else (recordStartRefNs - cap.t0RefNs) / 1e9

    /** ECG actually captured after the encoder closed, in seconds. */
    private fun leadOutS(cap: BleKardia.Capture): Double {
        if (recordStopRefNs == 0L || cap.lead1.isEmpty()) return 0.0
        return (cap.tRefNs(cap.lead1.size - 1) - recordStopRefNs) / 1e9
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
            .put("iso", requestedExposure?.iso ?: lockedIso)
            .put("exposure_ns", requestedExposure?.exposureNs ?: lockedExposureNs)
            .put("wb_locked", true)
            .put("focus_locked", true)
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
            .put("requested_ecg_lead_in_s", ECG_LEAD_IN_MS / 1000.0)
            .put("requested_ecg_lead_out_s", if (stopWasCancelled) 0.0 else ECG_LEAD_OUT_MS / 1000.0)
            .put("roi_fraction", ROI_FRACTION)
            .put("pulse_readout_bound", analysisBound)
            // --- D-033: what was asked of the camera and what it reported (CONTRACTS 3.5) ---
            .put("awb_applied", awbApplied)
            .put("distance_cm", distanceCm)
            .put("controls", controlsJson())
            .put("controls_file", "${clipId}_controls.csv")
            .put("roi_file", if (analysisBound) "${clipId}_roi.csv" else JSONObject.NULL)
            .put("roi_rows", roiRows)
            .put(
                "roi_trace",
                if (analysisBound) "pre-encoder ROI colour means written during the clip from the 16:9 YUV analysis stream"
                else "not written: the three-surface session failed and the clip kept only the preview"
            )
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
            .put("n_channels", cap.channels)
            .put("channel_layout_ratio", cap.layoutRatio)
            .put("channel_layout_decision", cap.layoutDecision)
            .put("n_samples", cap.lead1.size)
            .put("n_packets", cap.packetCount)
            .put("arrival_delay_median_ns", cap.arrivalJitterMedianNs)
            .put("arrival_delay_p95_ns", cap.arrivalJitterP95Ns)
            .put("gap_count", cap.gapCount)
            .put("missing_samples_zero_filled", cap.missingSamples)
        // The clip is a window inside a longer ECG record. Give the window in both clock and sample terms
        // so nothing downstream has to re-derive it from the lead-in constant, which may change.
        val clipWindow = JSONObject()
            .put("clip_start_ref_ns", recordStartRefNs)
            .put("clip_stop_ref_ns", recordStopRefNs)
            .put("requested_lead_in_s", ECG_LEAD_IN_MS / 1000.0)
            .put("requested_lead_out_s", if (stopWasCancelled) 0.0 else ECG_LEAD_OUT_MS / 1000.0)
            .put("interrupted", stopWasCancelled)
            .put("measured_lead_in_s", if (cap == null) JSONObject.NULL else leadInS(cap))
            .put("measured_lead_out_s", if (cap == null) JSONObject.NULL else leadOutS(cap))
            .put("clip_start_sample_idx", if (cap == null) JSONObject.NULL else sampleIndexAt(cap, recordStartRefNs))
            .put("clip_stop_sample_idx", if (cap == null) JSONObject.NULL else sampleIndexAt(cap, recordStopRefNs))
            .put(
                "note",
                "ECG opens before the encoder and closes after it so the beats either side of the clip " +
                    "boundary are whole. The measured lead is what was captured, which is shorter than " +
                    "requested if the stream started late or stalled."
            )
        val sync = JSONObject()
            .put("reference_clock", "CLOCK_BOOTTIME via SystemClock.elapsedRealtimeNanos")
            .put("camera", camera)
            .put("ecg", ecg)
            .put("clip_window", clipWindow)
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

    /** Requested versus reported, for `<clip>_meta.json`. Reported values are the last capture result. */
    private fun controlsJson(): JSONObject {
        val req = requestedExposure
        val set = settledExposure
        fun gains(g: RggbChannelVector?) =
            if (g == null) JSONObject.NULL else JSONArray(listOf(g.red, g.greenEven, g.greenOdd, g.blue))
        fun transform(t: ColorSpaceTransform?): Any {
            if (t == null) return JSONObject.NULL
            val arr = JSONArray()
            for (r in 0 until 3) for (c in 0 until 3) arr.put(t.getElement(c, r).toDouble())
            return arr
        }
        return JSONObject()
            .put("camera_id", cameraIdUsed)
            .put("preferred_physical_id", PREFERRED_PHYSICAL_ID)
            .put("manual_post_processing_supported", manualPost)
            .put("focus", JSONObject()
                .put("distance_cm", distanceCm)
                .put("requested_diopters", focus.requestedDiopters)
                .put("applied_diopters", focus.appliedDiopters)
                .put("clamped_to_lens", focus.clampedToLens)
                .put("lens_minimum_focus_distance_diopters", minimumFocusDistance ?: JSONObject.NULL)
                .put("lens_closest_focus_cm", minimumFocusDistance?.let { PalmControls.centimetres(it) } ?: JSONObject.NULL)
                .put("calibration", focusCalibration)
                .put("reported_diopters", lockedFocusDistance)
                .put("af_mode_reported", lastAfMode)
                .put("lens_state_reported", lastLensState))
            .put("exposure", JSONObject()
                .put("settled_ns", set?.exposureNs ?: JSONObject.NULL)
                .put("settled_iso", set?.iso ?: JSONObject.NULL)
                .put("requested_ns", req?.exposureNs ?: JSONObject.NULL)
                .put("requested_iso", req?.iso ?: JSONObject.NULL)
                .put("capped_to_ns", PalmControls.MAX_EXPOSURE_NS)
                .put("was_capped", req?.capped ?: false)
                .put("iso_saturated", req?.isoSaturated ?: false)
                .put("reported_ns", lockedExposureNs)
                .put("reported_iso", lockedIso)
                .put("ae_mode_reported", lastAeMode)
                .put("metered_on_roi", activeArray != null)
                .put("mains_hz", PalmControls.MAINS_HZ)
                .put("mains_half_cycle_ns", PalmControls.FLICKER_STEP_NS)
                // whether the shutter the camera actually reported is a whole number of half-cycles, which
                // is what decides if tube lighting rides on the ROI trace
                .put("flicker_free", lockedExposureNs > 0 && lockedExposureNs % PalmControls.FLICKER_STEP_NS == 0L)
                .put("flicker_free_requested", (req?.exposureNs ?: 0L) % PalmControls.FLICKER_STEP_NS == 0L))
            .put("white_balance", JSONObject()
                .put("applied", awbApplied)
                .put("awb_mode_reported", lastAwbMode)
                .put("gains_rggb", gains(lockedGains))
                .put("transform_row_major", transform(lockedTransform)))
            .put("tonemap_mode_requested", if (manualPost) "CONTRAST_CURVE(sRGB,64pt)" else "FAST")
            .put("tonemap_mode_reported", lastTonemapMode)
            .put("shading_mode_reported", lastShadingMode)
            .put("aberration_mode_reported", lastAberrationMode)
            .put("zoom_ratio_reported", lastZoom)
            .put("flash_state_reported", lastFlashState)
            .put("result_fps", resultFps)
            .put("analysis_resolution", "${ANALYSIS_W}x${ANALYSIS_H}")
            .put("yuv_to_rgb", "BT.601 full range (JFIF), applied to ROI means")
            .put("preflight", preflight?.let { v ->
                JSONObject().put("ok", v.ok).put("warnings", JSONArray(v.warnings))
                    .put("exposure_correction_factor", v.exposureCorrection ?: JSONObject.NULL)
            } ?: JSONObject.NULL)
    }

    // ---- status ----

    private fun updateStatus() {
        val sb = StringBuilder()
        if (recording) {
            val left = RECORD_SECONDS - (SystemClock.elapsedRealtime() - recordStartElapsedMs) / 1000
            sb.append("● REC  ${left.coerceAtLeast(0)}s left   frames $frameIdx\n")
        } else if (leadOutPending) {
            val left = (leadOutEndsAtMs - SystemClock.elapsedRealtime()) / 1000
            sb.append("clip done · ECG lead-out ${left.coerceAtLeast(0)}s\n")
        } else if (finishing) {
            sb.append("saving…\n")
        } else if (ecgCapturing) {
            val left = (ECG_LEAD_IN_MS - (SystemClock.elapsedRealtimeNanos() - ecgStartRefNs) / 1_000_000L) / 1000
            sb.append("ECG lead-in ${left.coerceAtLeast(0)}s · settling\n")
        } else {
            sb.append("$studyId · $clipId · $captureMode · torch ${if (torchOn) "on" else "off"}\n")
        }
        sb.append(ble.statusLine)
        if (ble.streaming) sb.append("  pkts ${ble.packetCount}  samples ${ble.loggedSamples}")
        if (ble.nudgeCount > 0) sb.append("  nudged ${ble.nudgeCount}x (${ble.lastNudge})")
        sb.append('\n')
        val hr = ble.heartRateBpm
        sb.append(if (hr > 0) "ECG HR ~%.0f bpm   ".format(hr) else "ECG HR --   ")
        sb.append(
            if (!analysisBound) "palm readout unavailable"
            else if (pulse.bpm > 0) "palm ~%.0f bpm  perfusion %.2f%%".format(pulse.bpm, pulse.perfusionPct)
            else "palm -- no pulse  perfusion %.2f%%".format(pulse.perfusionPct)
        )
        val luma = roiLuma
        if (analysisBound && !luma.isNaN()) {
            sb.append(
                when {
                    luma < PalmControls.MIN_ROI_LUMA -> "   ROI Y %.0f DARK — palm not over the box?".format(luma)
                    luma > PalmControls.MAX_ROI_LUMA -> "   ROI Y %.0f HOT".format(luma)
                    else -> "   ROI Y %.0f".format(luma)
                }
            )
        }
        sb.append(
            "\ncam $cameraIdUsed $hardwareLevel  focus %.0fcm=%.2fD rep %.2fD%s  %.1f fps".format(
                distanceCm, focus.appliedDiopters, lockedFocusDistance,
                if (focus.clampedToLens) " (lens limit)" else "", resultFps
            )
        )
        sb.append("\nlock $lockApplied / $awbApplied  iso $lockedIso  exp ${lockedExposureNs / 1000}us  clock ${clock?.sourceName ?: "?"}")
        preflight?.let { if (recording || finishing) sb.append('\n').append(it.line) }
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
