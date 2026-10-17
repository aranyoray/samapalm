/*
 * PalmRecorder.kt - SWHT-PP-003 custom Camera2 recorder for the OnePlus 12 (protocol section 4.6, optional
 * stretch; section 5 recording requirements).
 *
 * STATUS: THIS FILE HAS NOT BEEN COMPILED IN THIS ENVIRONMENT. It needs an Android Studio / Gradle project
 * (compileSdk 34, minSdk 29, Kotlin 1.9, permissions CAMERA and RECORD_AUDIO, a layout with a SurfaceView
 * `preview` and a Button `record`). See README.md next to it. It must pass the bench acceptance before use.
 *
 * What it does: CameraDevice + MediaRecorder surface at 1920x1080 / 30 fps / H.264 / 100 Mbit/s with AAC audio;
 * 2 s auto settle, then AE, AWB and AF locked; OIS and EIS off; scene modes, noise reduction and edge
 * enhancement off; torch per capture mode. The CaptureCallback writes one row per frame to
 * <clip_id>_frames.csv: frame_idx, sensor_ts_ns (SENSOR_TIMESTAMP = CLOCK_BOOTTIME ns), wall_ns, iso, exposure_ns
 * (CONTRACTS section 3.5). <clip_id>_meta.json records the locked values.
 */
package org.swht.palm

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.hardware.camera2.*
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.util.Range
import android.view.Surface
import android.view.SurfaceView
import android.widget.Button
import androidx.core.app.ActivityCompat
import org.json.JSONObject
import java.io.File
import java.io.FileWriter

class PalmRecorder : Activity() {
    private val studyId: String get() = intent.getStringExtra("study_id") ?: "SWHT-PP-003-0000"
    private val clipId: String get() = intent.getStringExtra("clip_id") ?: "clip1"
    private val captureMode: String get() = intent.getStringExtra("capture_mode") ?: "simultaneous"
    private val torchOn: Boolean get() = captureMode == "sequential"   // Q14.5: torch on only for the separate scan

    private lateinit var preview: SurfaceView
    private lateinit var recordButton: Button
    private lateinit var outDir: File
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var recorder: MediaRecorder? = null
    private var framesCsv: FileWriter? = null
    private var frameIdx = 0L
    private var recording = false
    private var lockedIso = -1
    private var lockedExposureNs = -1L
    private var lockedFocusDistance = -1f
    private val thread = HandlerThread("camera").apply { start() }
    private val handler = Handler(thread.looper)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(resources.getIdentifier("activity_recorder", "layout", packageName))
        preview = findViewById(resources.getIdentifier("preview", "id", packageName))
        recordButton = findViewById(resources.getIdentifier("record", "id", packageName))
        outDir = File(getExternalFilesDir(null), studyId).apply { mkdirs() }
        val perms = arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (perms.any { ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }) {
            ActivityCompat.requestPermissions(this, perms, 1)
        }
        recordButton.setOnClickListener { if (recording) stopRecording() else startRecording() }
    }

    private fun backCameraId(): String {
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        return cm.cameraIdList.first { id ->
            cm.getCameraCharacteristics(id).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
        }
    }

    private fun buildRecorder(): MediaRecorder {
        val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)              // audio ON: the buzzer beep is a sync marker
        r.setVideoSource(MediaRecorder.VideoSource.SURFACE)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setOutputFile(File(outDir, "$clipId.mp4").absolutePath)
        r.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
        r.setVideoSize(1920, 1080)
        r.setVideoFrameRate(30)
        r.setVideoEncodingBitRate(100_000_000)                       // highest bitrate the encoder accepts
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioSamplingRate(48_000)
        r.setAudioChannels(1)
        r.setAudioEncodingBitRate(128_000)
        r.prepare()
        return r
    }

    private fun applyFixedControls(b: CaptureRequest.Builder, lock: Boolean) {
        b.set(CaptureRequest.CONTROL_MODE, CameraMetadata.CONTROL_MODE_AUTO)
        b.set(CaptureRequest.CONTROL_SCENE_MODE, CameraMetadata.CONTROL_SCENE_MODE_DISABLED)
        b.set(CaptureRequest.CONTROL_VIDEO_STABILIZATION_MODE, CameraMetadata.CONTROL_VIDEO_STABILIZATION_MODE_OFF)
        b.set(CaptureRequest.LENS_OPTICAL_STABILIZATION_MODE, CameraMetadata.LENS_OPTICAL_STABILIZATION_MODE_OFF)
        b.set(CaptureRequest.NOISE_REDUCTION_MODE, CameraMetadata.NOISE_REDUCTION_MODE_OFF)
        b.set(CaptureRequest.EDGE_MODE, CameraMetadata.EDGE_MODE_OFF)
        b.set(CaptureRequest.TONEMAP_MODE, CameraMetadata.TONEMAP_MODE_FAST)
        b.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, Range(30, 30))   // constant frame rate
        b.set(CaptureRequest.FLASH_MODE, if (torchOn) CameraMetadata.FLASH_MODE_TORCH else CameraMetadata.FLASH_MODE_OFF)
        b.set(CaptureRequest.CONTROL_AE_LOCK, lock)                          // ISO + shutter locked after settle
        b.set(CaptureRequest.CONTROL_AWB_LOCK, lock)                         // white balance locked
        if (lock && lockedFocusDistance >= 0f) {
            b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_OFF)   // focus locked
            b.set(CaptureRequest.LENS_FOCUS_DISTANCE, lockedFocusDistance)
        } else {
            b.set(CaptureRequest.CONTROL_AF_MODE, CameraMetadata.CONTROL_AF_MODE_AUTO)
        }
    }

    private val frameLogger = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(s: CameraCaptureSession, req: CaptureRequest, result: TotalCaptureResult) {
            val ts = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return         // CLOCK_BOOTTIME ns (phone clock)
            val iso = result.get(CaptureResult.SENSOR_SENSITIVITY) ?: -1
            val exp = result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1L
            val focus = result.get(CaptureResult.LENS_FOCUS_DISTANCE) ?: -1f
            if (!recording) { lockedIso = iso; lockedExposureNs = exp; lockedFocusDistance = focus; return }
            val wallNs = System.currentTimeMillis() * 1_000_000L
            framesCsv?.write("$frameIdx,$ts,$wallNs,$iso,$exp\n")
            frameIdx += 1
        }
    }

    private fun startRecording() {
        val id = backCameraId()
        val cm = getSystemService(CAMERA_SERVICE) as CameraManager
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return
        cm.openCamera(id, object : CameraDevice.StateCallback() {
            override fun onOpened(dev: CameraDevice) { camera = dev; configureSession(dev) }
            override fun onDisconnected(dev: CameraDevice) { dev.close(); camera = null }
            override fun onError(dev: CameraDevice, error: Int) { dev.close(); camera = null }
        }, handler)
    }

    private fun configureSession(dev: CameraDevice) {
        val rec = buildRecorder().also { recorder = it }
        val surfaces = listOf(preview.holder.surface, rec.surface)
        dev.createCaptureSession(surfaces, object : CameraCaptureSession.StateCallback() {
            override fun onConfigured(s: CameraCaptureSession) {
                session = s
                // Phase 1: 2 s auto settle with the palm in view (AE, AWB, AF free), frames logged into the lock values.
                val settle = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
                surfaces.forEach { settle.addTarget(it) }
                applyFixedControls(settle, lock = false)
                settle.set(CaptureRequest.CONTROL_AF_TRIGGER, CameraMetadata.CONTROL_AF_TRIGGER_START)
                s.setRepeatingRequest(settle.build(), frameLogger, handler)
                handler.postDelayed({ lockAndRecord(dev, s, surfaces) }, 2_000L)
            }
            override fun onConfigureFailed(s: CameraCaptureSession) { s.close() }
        }, handler)
    }

    private fun lockAndRecord(dev: CameraDevice, s: CameraCaptureSession, surfaces: List<Surface>) {
        // Phase 2: lock everything at the settled values, then record with the same locked request.
        val locked = dev.createCaptureRequest(CameraDevice.TEMPLATE_RECORD)
        surfaces.forEach { locked.addTarget(it) }
        applyFixedControls(locked, lock = true)
        framesCsv = FileWriter(File(outDir, "${clipId}_frames.csv")).apply { write("frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns\n") }
        frameIdx = 0
        val startWallNs = System.currentTimeMillis() * 1_000_000L
        recorder?.start()
        recording = true
        s.setRepeatingRequest(locked.build(), frameLogger, handler)
        writeMeta(startWallNs)
        runOnUiThread { recordButton.text = "STOP" }
    }

    private fun writeMeta(startWallNs: Long) {
        val meta = JSONObject()
            .put("app", "PalmRecorder.kt (custom Camera2)")
            .put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("os_build", Build.DISPLAY)
            .put("resolution", org.json.JSONArray(listOf(1920, 1080)))
            .put("fps_nominal", 30)
            .put("bitrate_mbps", 100)
            .put("iso", lockedIso)
            .put("exposure_ns", lockedExposureNs)
            .put("wb_locked", true)
            .put("focus_locked", lockedFocusDistance >= 0f)
            .put("stabilisation", false)
            .put("hdr", false)
            .put("torch", if (torchOn) "on" else "off")
            .put("capture_mode", captureMode)
            .put("start_wall_ns", startWallNs)
            .put("led_block", JSONObject.NULL)          // filled by the operator once the LED position is known
            .put("study_id", studyId)
            .put("clip_id", clipId)
        File(outDir, "${clipId}_meta.json").writeText(meta.toString(2))
    }

    private fun stopRecording() {
        recording = false
        try { session?.stopRepeating() } catch (_: Exception) {}
        try { recorder?.stop() } catch (_: Exception) {}
        recorder?.release(); recorder = null
        framesCsv?.flush(); framesCsv?.close(); framesCsv = null
        session?.close(); session = null
        camera?.close(); camera = null
        runOnUiThread { recordButton.text = "RECORD" }
    }

    override fun onDestroy() {
        if (recording) stopRecording()
        thread.quitSafely()
        super.onDestroy()
    }
}
